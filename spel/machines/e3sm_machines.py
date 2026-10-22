"""
The parts of E3SM's ``cime_config/machines/config_machines.xml`` that SPEL needs.

E3SM already describes every machine it runs on: how to recognise it (``NODENAME_REGEX``),
where ``cprnc`` and the input data are, and which modules and environment variables a
compiler needs. SPEL reads that file instead of keeping its own copies of module lists, so a
unit-test toolchain stays in step with the E3SM checkout it is used with.

Only the subset needed for building unit tests on a login node is implemented: the
``<modules>`` and ``<environment_variables>`` blocks are matched on their ``compiler`` /
``mpilib`` (and a few other) attributes the way CIME does, blocks with attributes SPEL does
not know are skipped, and ``$ENV{X}`` / ``$SHELL{cmd}`` values become ``${X}`` / ``$(cmd)``
in the generated shell script.
"""

from __future__ import annotations

import os
import re
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

CONFIG_MACHINES = Path("cime_config/machines/config_machines.xml")

# Values the attribute matcher knows about when no case exists. Anything else
# (queue, PIO_VERSION, ...) makes the block not apply.
DEFAULT_MATCH_VALUES = {
    "DEBUG": "FALSE",
    "BUILD_THREADED": "FALSE",
    "unit_testing": "FALSE",
}

_ENV_RE = re.compile(r"\$ENV\{([^}]+)\}")
_SHELL_RE = re.compile(r"\$SHELL\{([^}]+)\}")
_CIME_VAR_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*")


class E3SMMachinesError(Exception):
    pass


def config_machines_path(srcroot: Path | str) -> Path:
    return Path(srcroot).expanduser() / CONFIG_MACHINES


def match_attrib(value: object, xml_value: str) -> bool:
    """CIME's rule: ``!x`` negates, otherwise the attribute is a regex matching the whole value."""
    if xml_value.startswith("!"):
        return re.match(xml_value[1:] + "$", str(value)) is None
    if isinstance(value, bool):
        return xml_value == ("TRUE" if value else "FALSE")
    return re.match(xml_value + "$", str(value)) is not None


@dataclass
class ShellEnv:
    """The shell lines of one toolchain, in the order CIME would write them."""

    init: Optional[str] = None  # `. /path/to/lmod/init/sh`
    module_lines: list[str] = field(default_factory=list)
    env_lines: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # env entries that need CIME case variables

    def lines(self) -> list[str]:
        out = []
        if self.init:
            out.append(self.init)
        out += self.module_lines
        out += self.env_lines
        return out


class E3SMMachine:
    def __init__(self, name: str, node: ET.Element, path: Path):
        self.name = name
        self.node = node
        self.path = path

    def value(self, tag: str, default: Optional[str] = None) -> Optional[str]:
        child = self.node.find(tag)
        if child is None or child.text is None:
            return default
        return child.text.strip()

    def compilers(self) -> list[str]:
        return [c.strip() for c in (self.value("COMPILERS") or "").split(",") if c.strip()]

    def default_compiler(self) -> Optional[str]:
        comps = self.compilers()
        return comps[0] if comps else None

    def mpilibs(self, compiler: Optional[str] = None) -> list[str]:
        """MPILIBS for the compiler (a `<MPILIBS compiler=...>` entry wins over the plain one)."""
        plain: list[str] = []
        for node in self.node.findall("MPILIBS"):
            libs = [m.strip() for m in (node.text or "").split(",") if m.strip()]
            attr = node.get("compiler")
            if attr is None:
                plain = libs
            elif compiler is not None and match_attrib(compiler, attr):
                return libs
        return plain

    def default_mpilib(self, compiler: Optional[str] = None) -> Optional[str]:
        libs = self.mpilibs(compiler)
        return libs[0] if libs else None

    def cprnc(self) -> Optional[str]:
        return self.value("CCSM_CPRNC")

    def inputdata(self) -> Optional[str]:
        return self.value("DIN_LOC_ROOT")

    def nodename_regex(self) -> Optional[str]:
        return self.value("NODENAME_REGEX")

    def matches_host(self, hostnames: Iterable[str], environ: Mapping[str, str]) -> bool:
        regex = self.nodename_regex()
        if not regex:
            return False
        if regex.startswith("$ENV{"):
            # "$ENV{VAR}:pattern" compares the pattern with the environment variable
            try:
                var, pattern = regex.split(":", 1)
            except ValueError:
                return False
            var = var[len("$ENV{") : -1]
            value = environ.get(var)
            return value is not None and re.match(pattern + "$", value) is not None
        return any(re.match(regex, h) is not None for h in hostnames if h)

    def module_init_sh(self) -> Optional[str]:
        ms = self.node.find("module_system")
        if ms is None:
            return None
        for init in ms.findall("init_path"):
            if init.get("lang") == "sh" and init.text:
                return init.text.strip()
        return None

    def module_system_type(self) -> Optional[str]:
        ms = self.node.find("module_system")
        return ms.get("type") if ms is not None else None

    # --- toolchain environment ------------------------------------------------------------

    def _block_matches(self, attribs: Mapping[str, str], values: Mapping[str, object]) -> bool:
        for attr, xml_value in attribs.items():
            if attr in ("name", "source"):
                continue
            key = attr if attr in values else attr.upper()
            if key not in values:
                return False  # a case variable SPEL does not have: not for us
            if not match_attrib(values[key], xml_value):
                return False
        return True

    def shell_env(
        self,
        compiler: str,
        mpilib: Optional[str] = None,
        values: Optional[Mapping[str, object]] = None,
    ) -> ShellEnv:
        """Module and environment lines for (compiler, mpilib), as `.env_mach_specific.sh` has them."""
        mpilib = mpilib or self.default_mpilib(compiler) or "mpich"
        vals: dict[str, object] = dict(DEFAULT_MATCH_VALUES)
        vals.update({"COMPILER": compiler, "MPILIB": mpilib})
        if values:
            vals.update(values)
        env = ShellEnv()
        init = self.module_init_sh()
        if init:
            env.init = f". {init}"
        ms = self.node.find("module_system")
        if ms is not None:
            for block in ms.findall("modules"):
                if not self._block_matches(block.attrib, vals):
                    continue
                pending_name, pending_args = None, []
                for cmd in block.findall("command"):
                    if not self._block_matches(cmd.attrib, vals):
                        continue
                    name = cmd.get("name") or "load"
                    arg = (cmd.text or "").strip()
                    arg = arg.replace("$COMPILER", compiler).replace("$MPILIB", mpilib)
                    if name != pending_name:
                        if pending_name:
                            env.module_lines.append(_module_line(pending_name, pending_args))
                        pending_name, pending_args = name, []
                    if arg:
                        pending_args.append(arg)
                if pending_name:
                    env.module_lines.append(_module_line(pending_name, pending_args))
        for block in self.node.findall("environment_variables"):
            if not self._block_matches(block.attrib, vals):
                continue
            for item in block.findall("env"):
                if not self._block_matches(item.attrib, vals):
                    continue
                name = item.get("name")
                raw = (item.text or "").strip()
                if name is None:
                    src = item.get("source")
                    if src and raw:
                        env.env_lines.append(f"source {raw}")
                    continue
                if not raw:
                    env.env_lines.append(f"unset {name}")
                    continue
                raw = raw.replace("$COMPILER", compiler).replace("$MPILIB", mpilib)
                if _needs_cime_variable(raw):
                    env.skipped.append(f"{name}={raw}")
                    env.env_lines.append(f"# skipped {name}: needs a CIME case variable ({raw})")
                    continue
                env.env_lines.append(f"export {name}={expand_cime_value(raw)}")
        return env


def _module_line(name: str, args: list[str]) -> str:
    return ("module " + name + " " + " ".join(args)).rstrip()


def _needs_cime_variable(raw: str) -> bool:
    """True when the value refers to a `$CIME_VAR` outside `$ENV{}`/`$SHELL{}` (unresolvable here)."""
    stripped = _SHELL_RE.sub("", _ENV_RE.sub("", raw))
    return _CIME_VAR_RE.search(stripped) is not None


def expand_cime_value(raw: str) -> str:
    """`$ENV{X}` -> `${X}`, `$SHELL{cmd}` -> `$(cmd)`; the result is a shell word."""
    value = _ENV_RE.sub(lambda m: "${" + m.group(1) + "}", raw)
    value = _SHELL_RE.sub(lambda m: "$(" + m.group(1) + ")", value)
    if re.search(r"\s", value) and not value.startswith("$("):
        return '"' + value.replace('"', '\\"') + '"'
    return value


class E3SMMachines:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if not self.path.is_file():
            raise E3SMMachinesError(f"no config_machines.xml at {self.path}")
        try:
            root = ET.parse(self.path).getroot()
        except ET.ParseError as err:
            raise E3SMMachinesError(f"{self.path}: {err}") from err
        self.machines: dict[str, E3SMMachine] = {}
        for node in root.iter("machine"):
            name = node.get("MACH")
            if name:
                self.machines[name] = E3SMMachine(name, node, self.path)

    @classmethod
    def from_srcroot(cls, srcroot: Path | str) -> "E3SMMachines":
        return cls(config_machines_path(srcroot))

    def names(self) -> list[str]:
        return list(self.machines)

    def get(self, name: str) -> E3SMMachine:
        try:
            return self.machines[name]
        except KeyError:
            raise E3SMMachinesError(
                f"E3SM machine '{name}' is not in {self.path} (known: {', '.join(self.names())})"
            ) from None

    def probe(
        self, hostnames: Optional[Iterable[str]] = None, environ: Optional[Mapping[str, str]] = None
    ) -> Optional[str]:
        """The E3SM machine whose NODENAME_REGEX matches this host, like CIME's probe."""
        hosts = list(hostnames) if hostnames is not None else local_hostnames()
        env = environ if environ is not None else os.environ
        for name, mach in self.machines.items():
            if mach.matches_host(hosts, env):
                return name
        return None


def local_hostnames() -> list[str]:
    names = []
    for fn in (socket.getfqdn, socket.gethostname):
        try:
            names.append(fn())
        except OSError:
            pass
    return names
