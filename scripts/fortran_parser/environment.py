from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from scripts.DerivedType import DerivedType

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine
    from scripts.utilityFunctions import Variable


@dataclass
class Environment:
    inst_dict: dict[str, DerivedType]
    variables: dict[str, Variable]
    locals: dict[str, Variable]
    globals: dict[str, Variable]
    dummy_args: dict[str, Variable]
    fns: dict[str, Subroutine]

    def to_dict(self):
        return asdict(self)
