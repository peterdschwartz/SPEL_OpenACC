"""
Namelist configurations applied to a snapshot.

A configuration is a dict {namelist variable: Fortran literal}; its hash
identifies it. `ensure_if_evals` evaluates every namelist-gated FlatIf of a
snapshot under it once (IfEvaluationByHash). `inactive_ranges` and `reachable`
turn that into line ranges to hide and the set of trace nodes / routines the
time step still reaches; both are cached per (snapshot, hash).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from spel.scripts.fortran_parser import lexer
from spel.scripts.fortran_parser.evaluate_ifs import eval_if_condition
from spel.scripts.fortran_parser.spel_ast import PrefixExpression, expr_from_dict
from spel.scripts.fortran_parser.spel_parser import Parser
from spel.scripts.types import LineTuple, LogicalLineIterator

from ..models import CascadePair, FlatIf, IfEvaluationByHash, IntrinsicGlobals, Snapshot, TraceNode

MAX_CONFIG_HASHES = 100
EVICT_OLDER_THAN_MINUTES = 60
CACHE_SECONDS = 600


def namelist_defaults(snapshot: Snapshot) -> dict[str, str]:
    """Namelist variable -> default literal (the declaration's initializer), for the snapshot."""
    rows = IntrinsicGlobals.objects.filter(snapshot=snapshot).exclude(namelist_group="").values_list("var_name", "value")
    return {name: (value or "") for name, value in rows}


def build_env(snapshot: Snapshot, overrides: dict) -> dict[str, str]:
    """Variable -> literal text: defaults, then the configuration's values, then cascades."""
    env = {}
    for name, default in namelist_defaults(snapshot).items():
        env[name] = str(overrides.get(name, default)).lower()
    for name, value in overrides.items():
        env.setdefault(name.lower(), str(value).lower())
    rows = CascadePair.objects.filter(dependence__snapshot=snapshot).values_list(
        "dependence__cascade_var", "dependence__trigger_var__active_var_id__var_name", "nml_val", "cascade_val"
    )
    for cascade_var, trigger, nml_val, cascade_val in rows:
        if env.get(trigger, "") == str(nml_val).lower():
            env[cascade_var] = str(cascade_val).lower()
    return env


def _literal_value(expr):
    if isinstance(expr, PrefixExpression):
        value = getattr(expr.right_expr, "value", None)
        return -value if expr.operator == "-" and value is not None else value
    return getattr(expr, "value", None)


def parse_literal(text: str):
    """One Fortran literal -> Python value, through SPEL's parser; simple fallbacks if it cannot."""
    text = (text or "").strip()
    if text == "":
        return None
    try:
        lex = lexer.Lexer(LogicalLineIterator([LineTuple(line=f"x = {text}", ln=0)]))
        program = Parser(lex=lex).parse_program()
        expr = getattr(program.statements[0], "expression", None)
        if expr is not None and hasattr(expr, "right_expr"):
            value = _literal_value(expr.right_expr)
            if value is not None:
                return value
    except (Exception, SystemExit):
        pass
    low = text.lower()
    if low in (".true.", "t", "true"):
        return True
    if low in (".false.", "f", "false"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text.lower().replace("d", "e").split("_")[0])
    except ValueError:
        pass
    return text.strip("'\"")


def parse_env(env: dict[str, str]) -> dict:
    """Variable -> Python value for the if evaluator."""
    out = {}
    for name, text in env.items():
        value = parse_literal(text)
        if value is not None:
            out[name.lower()] = value
    return out


def ensure_if_evals(snapshot: Snapshot, config_hash: str, data: dict) -> int:
    """
    Evaluate the snapshot's namelist-gated ifs under `data` (once per hash). Returns rows written.
    Read requests stay write-free: the last-used time is touched at most once per CACHE_SECONDS.
    """
    touched_key = f"ifeval-touched:{snapshot.pk}:{config_hash}"
    if cache.get(touched_key):
        return 0
    qs = IfEvaluationByHash.objects.filter(snapshot=snapshot, config_hash=config_hash)
    if qs.exists():
        try:
            qs.update(last_used_at=timezone.now())
        except Exception:  # a concurrent writer on SQLite: the touch is not worth failing a page for
            pass
        cache.set(touched_key, True, CACHE_SECONDS)
        return 0
    eval_env = parse_env(build_env(snapshot, data))
    batch = []
    gated = FlatIf.objects.filter(subroutine__snapshot=snapshot, nml_gated=True).only(
        "flatif_id", "subroutine_id", "start_ln", "end_ln", "condition"
    )
    for fi in gated.iterator(chunk_size=1000):
        if not fi.condition:
            continue
        try:
            is_active = eval_if_condition(expr_from_dict(fi.condition), eval_env)
        except Exception:
            is_active = True  # unknown stays active (conservative)
        batch.append(IfEvaluationByHash(
            snapshot=snapshot, config_hash=config_hash, flatif_id=fi.pk, subroutine_id=fi.subroutine_id,
            start_ln=fi.start_ln, end_ln=fi.end_ln, is_active=is_active))
    with transaction.atomic():
        IfEvaluationByHash.objects.bulk_create(batch, ignore_conflicts=True, batch_size=2000)
        evict_cold_hashes(snapshot)
    cache.set(touched_key, True, CACHE_SECONDS)
    return len(batch)


def evict_cold_hashes(snapshot: Snapshot) -> None:
    hashes = list(
        IfEvaluationByHash.objects.filter(snapshot=snapshot).values_list("config_hash", flat=True).distinct()
    )
    if len(hashes) <= MAX_CONFIG_HASHES:
        return
    cutoff = timezone.now() - timedelta(minutes=EVICT_OLDER_THAN_MINUTES)
    cold = (IfEvaluationByHash.objects.filter(snapshot=snapshot, last_used_at__lt=cutoff)
            .values_list("config_hash", flat=True).distinct())
    IfEvaluationByHash.objects.filter(snapshot=snapshot, config_hash__in=list(cold)[: len(hashes) - MAX_CONFIG_HASHES]).delete()


def inactive_ranges(snapshot_id: int, config_hash: str) -> dict[int, list[tuple[int, int]]]:
    """subroutine pk -> [(start_ln, end_ln)] of its inactive if branches under the configuration."""
    key = f"inactive:{snapshot_id}:{config_hash}"
    out = cache.get(key)
    if out is None:
        out = {}
        rows = IfEvaluationByHash.objects.filter(snapshot_id=snapshot_id, config_hash=config_hash, is_active=False)
        for sub_id, start, end in rows.values_list("subroutine_id", "start_ln", "end_ln"):
            out.setdefault(sub_id, []).append((start, end))
        cache.set(key, out, CACHE_SECONDS)
    return out


def is_inactive(ranges: dict[int, list[tuple[int, int]]], sub_id: int, ln: int) -> bool:
    return any(a <= ln <= b for a, b in ranges.get(sub_id, ()))


@dataclass
class Reach:
    """Trace nodes and routines the time step reaches under a configuration."""

    node_ids: set = field(default_factory=set)
    sub_ids: set = field(default_factory=set)
    orders: set = field(default_factory=set)


def reachable(snapshot_id: int, config_hash: str) -> Reach:
    key = f"reach:{snapshot_id}:{config_hash}"
    out = cache.get(key)
    if out is not None:
        return out
    ranges = inactive_ranges(snapshot_id, config_hash)
    nodes = list(
        TraceNode.objects.filter(snapshot_id=snapshot_id).order_by("order")
        .values_list("pk", "order", "size", "subroutine_id", "parent__subroutine_id", "call_site__lineno")
    )
    out = Reach()
    skip_until = -1
    for pk, order, size, sub_id, caller_id, call_ln in nodes:
        if order < skip_until:
            continue
        if caller_id is not None and call_ln is not None and is_inactive(ranges, caller_id, call_ln):
            skip_until = order + size
            continue
        out.node_ids.add(pk)
        out.orders.add(order)
        out.sub_ids.add(sub_id)
    cache.set(key, out, CACHE_SECONDS)
    return out


def filter_access_lns_by_hash(qs, sub_field: str, lineno_field: str, snapshot_id: int, config_hash: str):
    """Drop rows whose line falls inside an inactive if range of `sub_field` under the configuration."""
    inactive = IfEvaluationByHash.objects.filter(
        snapshot_id=snapshot_id,
        config_hash=config_hash,
        subroutine_id=OuterRef(sub_field),
        is_active=False,
        start_ln__lte=OuterRef(lineno_field),
        end_ln__gte=OuterRef(lineno_field),
    )
    return qs.annotate(in_inactive=Exists(inactive)).filter(in_inactive=False)
