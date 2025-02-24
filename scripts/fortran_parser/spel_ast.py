from abc import ABC, abstractmethod
from typing import List, Optional

from scripts.fortran_parser.tokens import Token


# Base interface: Node
class Node(ABC):
    @abstractmethod
    def token_literal(self) -> str:
        """Return the literal value of the token."""
        pass

    @abstractmethod
    def __str__(self) -> str:
        pass


# Derived interface: Statement
class Statement(Node):
    @abstractmethod
    def statement_node(self) -> None:
        """Marker method for statement nodes."""
        pass

    def to_dict(self):
        return {"Node": self.__class__.__name__}


# Derived interface: Expression
class Expression(Node):
    @abstractmethod
    def expression_node(self) -> None:
        """Marker method for expression nodes."""
        pass

    def to_dict(self):
        return {"Node": self.__class__.__name__}


class Program(Statement):
    def __init__(self):
        self.statements: List[Statement] = []

    def token_literal(self) -> str:
        if len(self.statements) > 0:
            return self.statements[0].token_literal()
        else:
            return ""

    def statement_node(self) -> None:
        pass

    def __str__(self):
        return "\n".join(str(stmt) for stmt in self.statements)


class Identifier(Expression):
    def __init__(self, tok: Token, value: str):
        self.token = tok
        self.value: str = value

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self) -> str:
        return self.value

    def expression_node(self) -> None:
        pass

    def __eq__(self, other):
        return isinstance(other, Identifier) and self.value == other.value

    def to_dict(self):
        return {"Node": "Ident", "Val": str(self)}


# Statement Classes
class ExpressionStatement(Statement):
    def __init__(self, tok: Token):
        self.token = tok
        self.expression = None

    def statement_node(self):
        pass

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self):
        return str(self.expression)

    def __eq__(self, other):
        if not isinstance(other, ExpressionStatement):
            return False
        else:
            return self.token == other.token and self.expression == other.expression

    def to_dict(self):
        return {"Node": "ExpressionStatement", "Expr": self.expression.to_dict()}


class SubCallStatement(Statement):
    def __init__(self, tok):
        self.token: Token = tok  # "CALL"
        self.function: Optional[FuncExpression] = None  # FuncExpression

    def statement_node(self):
        pass

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self):
        return "CALL " + str(self.function)

    def __eq__(self, other):
        if not isinstance(other, SubCallStatement):
            return False
        else:
            return self.token == other.token and self.function == other.function

    def to_dict(self):
        return {"Node": "SubCallStatement", "Sub": self.function.to_dict()}


# Expression Classes
class IntegerLiteral(Expression):
    def __init__(self, tok: Token, val: int):
        self.token: Token = tok
        self.value: int = val

    def token_literal(self) -> str:
        return str(self.value)

    def expression_node(self) -> None:
        pass

    def __str__(self):
        return self.token_literal()

    def __eq__(self, other):
        return isinstance(other, IntegerLiteral) and self.value == other.value

    def to_dict(self):
        return {"Node": "IntegerLiteral", "Val": self.value}


class StringLiteral(Expression):
    def __init__(self, tok: Token, val: str):
        self.token: Token = tok  # SQUOTE or DQUOTE
        self.value: str = val

    def token_literal(self) -> str:
        return str(self.value)

    def expression_node(self) -> None:
        pass

    def __str__(self):
        return self.token_literal()

    def __eq__(self, other):
        return isinstance(other, StringLiteral) and self.value == other.value

    def to_dict(self):
        return {"Node": "StringLiteral", "Val": self.value}


class FloatLiteral(Expression):
    def __init__(self, tok: Token):
        self.token: Token = tok
        self.value: Optional[float] = None
        self.precision: str = ""

    def token_literal(self) -> str:
        return self.token.literal

    def expression_node(self) -> None:
        pass

    def __str__(self):
        return str(self.value) + self.precision

    def __eq__(self, other):
        return isinstance(other, FloatLiteral) and self.value == other.value

    def to_dict(self):
        return {"Node": "FloatExpression", "Val": self.value}


class PrefixExpression(Expression):
    def __init__(self, tok: Token, op: str):
        self.token: Token = tok
        self.right_expr: Expression
        self.operator: str = op

    def token_literal(self) -> str:
        return self.token.literal

    def expression_node(self) -> None:
        pass

    def __str__(self):
        return f"({self.operator}{str(self.right_expr)})"

    def __eq__(self, other):
        if not isinstance(other, PrefixExpression):
            return False
        else:
            return (
                self.token == other.token
                and self.right_expr == other.right_expr
                and self.operator == other.operator
            )

    def to_dict(self):
        return {
            "Node": "PrefixExpression",
            "Op": self.operator,
            "Right": self.right_expr.to_dict(),
        }


class InfixExpression(Expression):
    def __init__(
        self,
        tok: Token,
        left: Expression,
        op: str,
    ):
        self.token: Token = tok
        self.left_expr: Expression = left
        self.operator: str = op
        self.right_expr: Expression

    def expression_node(self) -> None:
        pass

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self):
        return "(" + str(self.left_expr) + self.operator + str(self.right_expr) + ")"

    def __eq__(self, other):
        if not isinstance(other, InfixExpression):
            return False
        else:
            return (
                self.token == other.token
                and self.right_expr == other.right_expr
                and self.operator == other.operator
                and self.left_expr == other.left_expr
            )

    def to_dict(self):
        return {
            "Node": "InfixExpression",
            "Left": self.left_expr.to_dict(),
            "Op": self.operator,
            "Right": self.right_expr.to_dict(),
        }


class FieldAccessExpression(Expression):

    def __init__(
        self,
        tok: Token,
        left: Expression,
        field: Expression,
    ):
        self.token: Token = tok  # '%'
        self.left: Expression = left
        self.field: Expression = field

    def expression_node(self) -> None:
        pass

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self):
        return f"{self.left}%{self.field}"

    def __eq__(self, other):
        if not isinstance(other, FieldAccessExpression):
            return False
        else:
            return (
                self.token == other.token
                and self.left == other.left
                and self.field == other.field
            )

    def to_dict(self):
        return {
            "Node": "FieldAccessExpression",
            "Left": self.left.to_dict(),
            "Field": self.field.to_dict(),
        }


class FuncExpression(Expression):
    """
    Expression for functions or arrays. Infix operator expression
    """

    def __init__(
        self,
        tok: Token,
        fn: Expression,
    ):
        self.token: Token = tok  # '('
        self.function: Expression = fn  # Identifier
        self.args: List[Expression] = []

    def expression_node(self) -> None:
        pass

    def token_literal(self) -> str:
        return self.token.literal

    def __str__(self):
        args = ",".join(str(arg) for arg in self.args)
        return "[" + str(self.function) + "(" + args + ")" + "]"

    def __eq__(self, other):
        if not isinstance(other, FuncExpression):
            return False
        else:
            return (
                self.token == other.token
                and self.function == other.function
                and self.args == other.args
            )

    def to_dict(self):
        return {
            "Node": "FuncExpression",
            "Func": str(self.function),
            "Args": [arg.to_dict() for arg in self.args],
        }


class BoundsExpression(Expression):
    def __init__(self, tok):
        self.token: Token = tok  # Colon
        self.start: Expression | str = ""
        self.end: Expression | str = ""

    def expression_node(self) -> None:
        pass

    def token_literal(self) -> str:
        return super().token_literal()

    def __str__(self):
        return f"({self.start}:{self.end})"

    def __eq__(self, other):
        if not isinstance(other, BoundsExpression):
            return False
        else:
            return (
                self.token == other.token
                and self.start == other.start
                and self.end == other.end
            )

    def to_dict(self):
        return {
            "Node": "BoundsExpression",
            "Val": str(self),
        }
