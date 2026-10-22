"""`spel machine`: show, check, print and set up the machine configuration."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from spel.machines.e3sm_machines import E3SMMachinesError
from spel.machines.machine import (
    ENV_VAR,
    TEMPLATE,
    Machine,
    MachineError,
    detect_machine,
    expand,
    load_machines,
    machine_files,
    user_machines_dir,
)


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "machine",
        help="Show, check or set up SPEL's configuration for this machine "
        "(toolchains, scratch, cprnc; see spel/machines/template.toml)",
    )
    sub = p.add_subparsers(dest="machine_cmd")
    sub.add_parser("show", help="what SPEL knows about this machine (default)")
    sub.add_parser("list", help="all machine files (bundled and ~/.config/spel/machines)")
    env = sub.add_parser(
        "env", help="print the shell script that sets up a toolchain (source <(spel machine env))"
    )
    env.add_argument("--fc", default=None, help="toolchain (default: $SPEL_FC or the machine default)")
    chk = sub.add_parser("check", help="set up each toolchain and verify compiler, cmake and netcdf-fortran")
    chk.add_argument("--fc", default=None, help="only this toolchain")
    sub.add_parser("vars", help="shell assignments (SPEL_E3SM_MACHINE, SPEL_SCRATCH, ...) for scripts")
    init = sub.add_parser("init", help="write a machine file for a new machine from the template")
    init.add_argument("name")
    init.add_argument("--from", dest="base", default=None, help="copy this machine's file instead of the template")
    init.add_argument("--force", action="store_true", help="overwrite an existing file")
    setup = sub.add_parser(
        "setup", help="put unit-tests/ and unit-tests/input-data on the machine's scratch (symlinks)"
    )
    setup.add_argument("--move", action="store_true", help="move existing cases/data to scratch first")
    p.set_defaults(func=main)


def main(args: argparse.Namespace) -> None:
    cmd = args.machine_cmd or "show"
    try:
        {
            "show": cmd_show,
            "list": cmd_list,
            "env": cmd_env,
            "check": cmd_check,
            "vars": cmd_vars,
            "init": cmd_init,
            "setup": cmd_setup,
        }[cmd](args)
    except (MachineError, E3SMMachinesError) as err:
        raise SystemExit(f"spel machine: {err}")


def _spel_root() -> Path:
    from spel.scripts.config import spel_dir

    return Path(spel_dir)


def _current(required: bool = True) -> Optional[Machine]:
    m = detect_machine()
    if m is None and required:
        raise MachineError(
            "no machine file matches this host. `spel machine list` shows the known ones; "
            f"select one with {ENV_VAR}=<name>, or create one with `spel machine init <name>` "
            "(see spel/machines/template.toml)"
        )
    return m


def _unit_tests_status(machine: Machine) -> str:
    ut = _spel_root() / "unit-tests"
    if ut.is_symlink():
        target = ut.resolve()
        want = machine.unit_tests_dir()
        note = "" if want is None or target == want.resolve() else f" (machine scratch: {want})"
        return f"{ut} -> {target}{note}"
    if ut.is_dir():
        want = machine.unit_tests_dir()
        hint = f" (`spel machine setup` moves it to {want})" if want else ""
        return f"{ut} (inside the SPEL tree){hint}"
    return f"{ut} (missing; `spel create` makes it, `spel machine setup` puts it on scratch)"


def cmd_show(args: argparse.Namespace) -> None:
    forced = os.environ.get(ENV_VAR)
    m = _current(required=False)
    if m is None:
        print("Machine     : none" + (f" ({ENV_VAR}={forced})" if forced is not None else " detected"))
        print("  SPEL uses the current shell environment as the toolchain. "
              f"`spel machine list` / `spel machine init NAME` ({ENV_VAR}=NAME selects one).")
        return
    how = f"{ENV_VAR}={forced}" if forced is not None else "detected"
    print(f"Machine     : {m.name} ({how}) -- {m.description}")
    print(f"  file      : {m.path}")
    e3sm_line = m.e3sm_machine or "none"
    try:
        e3sm = m.e3sm()
        if e3sm:
            e3sm_line += f"  ({e3sm.path})"
    except E3SMMachinesError as err:
        e3sm_line += f"  (NOT FOUND: {err})"
    print(f"  E3SM      : {e3sm_line}")
    print(f"  scratch   : {m.scratch_dir() or 'none (unit tests stay in the SPEL tree)'}")
    print(f"  unit-tests: {_unit_tests_status(m)}")
    print(f"  cprnc     : {m.cprnc_path() or 'unknown'}")
    print(f"  toolchains: default {m.default_fc} (override with SPEL_FC)")
    for tc in m.toolchains.values():
        print(f"    {tc.fc:<10} {tc.source()}" + (f" -- {tc.description}" if tc.description else ""))
    if m.casegen:
        print("  casegen   : " + ", ".join(f"{k}={v!r}" for k, v in m.casegen.items()))
    print("`spel machine check` verifies the toolchains; `spel machine env --fc X` prints one.")


def cmd_list(args: argparse.Namespace) -> None:
    current = _current(required=False)
    print(f"user machine files: {user_machines_dir()} (${'{'}{ 'SPEL_MACHINES_DIR' }{'}'})")
    for path in machine_files():
        try:
            m = Machine.from_toml(path)
        except MachineError as err:
            print(f"  {path}: ERROR {err}")
            continue
        mark = "*" if current and current.name == m.name else " "
        print(f"{mark} {m.name:<12} {', '.join(m.toolchains) or '-':<28} {path}")
    print("(* = this machine)")


def cmd_env(args: argparse.Namespace) -> None:
    m = _current()
    fc = args.fc or os.environ.get("SPEL_FC") or m.default_fc
    sys.stdout.write(m.toolchain_script(fc))


def _which(env: dict, name: str) -> Optional[str]:
    return shutil.which(name, path=env.get("PATH", ""))


def _pkg_config(env: dict, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["pkg-config", *args], env=env, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def check_toolchain(m: Machine, fc: str) -> list[tuple[bool, str]]:
    """[(ok, message)] for one toolchain: environment, compiler, cmake, pkg-config, netcdf-fortran."""
    out: list[tuple[bool, str]] = []
    try:
        env = m.toolchain_environ(fc)
    except MachineError as err:
        return [(False, f"environment: {err}")]
    out.append((True, "environment set up"))
    exe = _which(env, fc)
    out.append((bool(exe), f"{fc}: {exe or 'not found on PATH'}"))
    cmake = _which(env, "cmake")
    out.append((bool(cmake), f"cmake: {cmake or 'not found'}"))
    if _which(env, "pkg-config") is None:
        out.append((False, "pkg-config: not found"))
        return out
    code, msg = _pkg_config(env, "--exists", "--print-errors", "netcdf-fortran")
    if code == 0:
        _, cflags = _pkg_config(env, "--cflags", "netcdf-fortran")
        out.append((True, f"netcdf-fortran: {cflags or 'found'}"))
    else:
        out.append((False, f"netcdf-fortran: {msg.splitlines()[0] if msg else 'not found by pkg-config'}"
                           " (add its lib/pkgconfig to the toolchain's pkg_config_path)"))
    return out


def cmd_check(args: argparse.Namespace) -> None:
    m = _current()
    print(f"machine {m.name} ({m.path})")
    ok_all = True
    scratch = m.scratch_dir()
    if scratch:
        ok = scratch.is_dir() and os.access(scratch, os.W_OK)
        ok_all &= ok
        print(f"  [{'ok' if ok else 'XX'}] scratch {scratch}{'' if ok else ' (missing or not writable)'}")
    cprnc = m.cprnc_path()
    if cprnc:
        ok = os.access(cprnc, os.X_OK)
        print(f"  [{'ok' if ok else '--'}] cprnc {cprnc}{'' if ok else ' (not executable here)'}")
    fcs = [args.fc] if args.fc else list(m.toolchains)
    for fc in fcs:
        print(f"  toolchain {fc}:")
        for ok, msg in check_toolchain(m, fc):
            ok_all &= ok
            print(f"    [{'ok' if ok else 'XX'}] {msg}")
    print("all checks passed" if ok_all else "some checks FAILED")
    if not ok_all:
        raise SystemExit(1)


def cmd_vars(args: argparse.Namespace) -> None:
    m = _current(required=False)
    if m is None:
        return
    values = {
        "SPEL_MACHINE": m.name,
        "SPEL_E3SM_MACHINE": m.e3sm_machine or "",
        "SPEL_SCRATCH": str(m.scratch_dir() or ""),
        "SPEL_CPRNC": m.cprnc_path() or "",
        "SPEL_DEFAULT_FC": m.default_fc or "",
        "SPEL_MAKE_JOBS": str(m.make_jobs or ""),
    }
    for key, value in m.casegen.items():
        values["SPEL_CASEGEN_" + key.upper()] = str(value)
    for key, value in values.items():
        print(f"{key}={shlex.quote(value)}")


def cmd_init(args: argparse.Namespace) -> None:
    name = args.name
    if not name.replace("-", "").replace("_", "").isalnum():
        raise MachineError(f"machine name '{name}' should be letters, digits, '-' or '_'")
    dest = user_machines_dir() / f"{name}.toml"
    if dest.exists() and not args.force:
        raise MachineError(f"{dest} exists (--force overwrites it)")
    if args.base:
        machines = load_machines()
        if args.base not in machines or machines[args.base].path is None:
            raise MachineError(f"--from {args.base}: no such machine (see `spel machine list`)")
        text = machines[args.base].path.read_text()
        text = text.replace(f'name = "{args.base}"', f'name = "{name}"', 1)
    else:
        text = TEMPLATE.read_text().replace('name = "NAME"', f'name = "{name}"', 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    print(f"wrote {dest}")
    print(
        "next:\n"
        f"  1. edit it (toolchains: commands/env_file + pkg_config_path; [detect] for auto-selection)\n"
        f"  2. {ENV_VAR}={name} spel machine check      (or export {ENV_VAR}={name} in .spel.env)\n"
        f"  3. spel machine setup                 (optional: unit tests on scratch)"
    )


def _replace_with_symlink(link: Path, target: Path, move: bool) -> None:
    """Make `link` a symlink to `target` (a directory), moving existing content there if asked."""
    target.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        if link.resolve() == target.resolve():
            print(f"  {link} -> {target} (already)")
            return
        print(f"  {link} -> {target} (was -> {os.readlink(link)})")
        link.unlink()
    elif link.is_dir():
        entries = [p for p in link.iterdir()]
        if entries and not move:
            raise MachineError(
                f"{link} is a directory with {len(entries)} entries; "
                "`spel machine setup --move` moves them to scratch first"
            )
        for p in entries:
            dest = target / p.name
            if dest.exists():
                raise MachineError(f"cannot move {p}: {dest} exists")
            shutil.move(str(p), str(dest))
        if entries:
            print(f"  moved {len(entries)} entries from {link} to {target}")
        link.rmdir()
        print(f"  {link} -> {target}")
    elif link.exists():
        raise MachineError(f"{link} exists and is not a directory")
    else:
        print(f"  {link} -> {target}")
    link.symlink_to(target)


def cmd_setup(args: argparse.Namespace) -> None:
    m = _current()
    scratch = m.scratch_dir()
    if scratch is None:
        raise MachineError(f"machine {m.name} has no `scratch`; nothing to set up")
    if not scratch.is_dir():
        raise MachineError(f"scratch {scratch} does not exist")
    root = _spel_root()
    print(f"machine {m.name}: unit tests on {scratch}")
    ut_link, ut_target = root / "unit-tests", m.unit_tests_dir()
    in_link, in_target = ut_link / "input-data", m.input_data_dir()
    # input-data first: it lives inside unit-tests, which may be about to move
    if ut_link.is_dir() and not ut_link.is_symlink():
        _replace_with_symlink(in_link, in_target, args.move)
    _replace_with_symlink(ut_link, ut_target, args.move)
    _replace_with_symlink(in_link, in_target, args.move)
    print("done; `spel machine` shows the layout")
