from dataclasses import dataclass
from enum import Enum
from typing import Dict


class TokenTypes(Enum):
    IDENT = "IDENT"
    EOF = "EOF"
    INT = "INT"
    FLOAT = "FLOAT"
    ILLEGAL = "ILLEGAL"
    # Operators
    ASSIGN = "="
    PLUS = "+"
    MINUS = "-"
    ASTERISK = "*"
    BANG = "!"
    SLASH = "/"
    EXP = "**"
    EQUIV = "=="
    # delimiters
    DOT = "."
    COMMA = ","
    LPAREN = "("
    RPAREN = ")"
    NEWLINE = "\n"
    COLON = ":"
    # keywords
    SUBROUTINE = "SUBROUTINE"
    FUNCTION = "FUNCTION"
    TRUE = ".true."
    FALSE = ".false."
    RETURN = "RETURN"
    CALL = "CALL"


keywords: Dict[str, TokenTypes] = {
    ".true.": TokenTypes.TRUE,
    ".false.": TokenTypes.FALSE,
    "call": TokenTypes.CALL,
    "subroutine": TokenTypes.SUBROUTINE,
    "function": TokenTypes.FUNCTION,
}


@dataclass
class Token:
    token: TokenTypes
    literal: str


def lookup_indentifer(ident: str) -> TokenTypes:
    if ident in keywords:
        return keywords[ident]
    return TokenTypes.IDENT
