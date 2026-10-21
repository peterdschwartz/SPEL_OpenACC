"""
Prognostic/diagnostic classification of module variables and instance fields.

A variable carries state across time steps when the step reads it before it
(re)writes it for every element: a read occurs before the first *unconditional*
write (one outside any plain `if`, in a routine not called under one), or it is
read and only ever written conditionally. Registration (restart/history) is
recorded as a fact; disagreements with the carried-state rule are findings.
"""

from __future__ import annotations

from collections import defaultdict


def _truthy(v) -> bool:
    return v in (True, 1, "1", "True", "true")


def categorize(accesses: list[tuple[str, bool]], history: bool) -> str:
    """
    accesses: (status, conditional) in step order.
    prognostic: read before the first unconditional write (or read, and never written
    unconditionally); input: read, never written; diagnostic/intermediate: an unconditional
    write precedes every read (history-registered or not); unused: no access.
    """
    if not accesses:
        return "unused"
    written = any(s in ("w", "rw") for s, _ in accesses)
    if not written:
        return "input"
    for status, conditional in accesses:
        if status in ("r", "rw"):
            return "prognostic"
        if status == "w" and not conditional:
            break
    else:
        return "prognostic"  # only conditional writes: elements not written keep their value
    return "diagnostic" if history else "intermediate"


def _key(row: dict):
    if row.get("instance"):
        if not row.get("member"):
            return None  # whole-instance access: not a field
        return ("inst", row["inst_module"], row["instance"], row["member"])
    if row.get("var_name"):
        return ("glob", row["var_module"], row["var_name"])
    return None


def derive(trace_rows: list[dict], applied_regs: list[dict], node_subs: dict[int, str]) -> list[dict]:
    """
    trace_rows:   trace_access rows (status r/w/rw, order, node_order, ln)
    applied_regs: {"inst_module", "instance", "member" | "var_module", "var_name", "kind", "inactive"}
                  with type-level registrations already applied to each instance
    node_subs:    trace node order -> sub_id (to count distinct routines)
    """
    acc: dict[tuple, list[dict]] = defaultdict(list)
    for row in trace_rows:
        k = _key(row)
        if k is not None:
            acc[k].append(row)
    regs: dict[tuple, dict] = defaultdict(lambda: {"restart": False, "history": False, "history_active": False})
    for r in applied_regs:
        k = _key(r)
        if k is None:
            continue
        if r["kind"] == "restart":
            regs[k]["restart"] = True
        elif r["kind"] == "hist":
            regs[k]["history"] = True
            if not r.get("inactive"):
                regs[k]["history_active"] = True

    out = []
    for k in sorted(set(acc) | set(regs), key=str):
        rows = sorted(acc.get(k, []), key=lambda r: int(r["order"]))
        flags = regs.get(k, {"restart": False, "history": False, "history_active": False})
        read = any(r["status"] in ("r", "rw") for r in rows)
        written = any(r["status"] in ("w", "rw") for r in rows)
        first = rows[0] if rows else None
        first_status = "" if first is None else ("r" if first["status"] in ("r", "rw") else "w")
        category = categorize([(r["status"], _truthy(r.get("conditional"))) for r in rows], flags["history"])
        row = {
            "inst_module": k[1] if k[0] == "inst" else "",
            "instance": k[2] if k[0] == "inst" else "",
            "member": k[3] if k[0] == "inst" else "",
            "var_module": k[1] if k[0] == "glob" else "",
            "var_name": k[2] if k[0] == "glob" else "",
            "restart": flags["restart"],
            "history": flags["history"],
            "history_active": flags["history_active"],
            "first_status": first_status,
            "first_node_order": first["node_order"] if first is not None else "",
            "first_ln": first["ln"] if first is not None else "",
            "read_in_step": read,
            "written_in_step": written,
            "n_reads": sum(r["status"] in ("r", "rw") for r in rows),
            "n_writes": sum(r["status"] in ("w", "rw") for r in rows),
            "n_routines": len({node_subs.get(int(r["node_order"]), r["node_order"]) for r in rows}),
            "category": category,
            "restart_unneeded": flags["restart"] and category != "prognostic",
            "restart_missing": category == "prognostic" and not flags["restart"],
        }
        out.append(row)
    return out


def apply_registrations(reg_rows: list[dict], instances: list[dict], type_parents: dict[str, str], applies_to) -> list[dict]:
    """
    Registrations per instance: a `this` registration of a type applies to every
    instance of that type (or of a type extending it) its guards admit
    (`applies_to(reg_row, instance_name) -> bool`); others are already per variable.
    """
    by_type: dict[str, list[dict]] = defaultdict(list)
    for inst in instances:
        t = inst["user_type_name"]
        while t:
            by_type[t].append(inst)
            t = type_parents.get(t, "")
    out = []
    for r in reg_rows:
        if r["user_type"]:
            if not r["member"]:
                continue
            for inst in by_type.get(r["user_type"], []):
                if applies_to(r, inst["instance_name"]):
                    out.append(
                        {"inst_module": inst["module"], "instance": inst["instance_name"],
                         "member": r["member"], "kind": r["kind"], "inactive": r["inactive"]}
                    )
        elif r["instance"] or r["var_name"]:
            out.append(
                {"inst_module": r["inst_module"], "instance": r["instance"], "member": r["member"],
                 "var_module": r["var_module"], "var_name": r["var_name"],
                 "kind": r["kind"], "inactive": r["inactive"]}
            )
    return out
