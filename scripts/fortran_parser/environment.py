from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine
    from scripts.utilityFunctions import Variable


@dataclass
class Environment:
    variables: Dict[str, Variable]
    locals: dict[str, Variable]
    globals: dict[str, Variable]
    dummy_args: dict[str, Variable]
    fns: Dict[str, Subroutine]
