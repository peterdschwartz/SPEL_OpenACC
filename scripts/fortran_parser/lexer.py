import sys

import scripts.fortran_parser.tokens as tokens


class Lexer:
    def __init__(self, input: str):
        self.input: str = input.lower()  # FORTRAN case-insensitive
        self.position: int = 0
        self.read_position: int = 0
        self.ch: str = ""
        self.read_char()

    def read_char(self):
        if self.read_position >= len(self.input):
            self.ch = ""
        else:
            self.ch = self.input[self.read_position]
        self.position = self.read_position
        self.read_position += 1

    def read_identifier(self) -> str:
        # Identifiers may contain digits but can't start with digits
        pos = self.position
        while is_valid_ident(self.ch):
            self.read_char()
        return self.input[pos : self.position]

    def read_num(self) -> str:
        pos = self.position
        check_prec = False
        while is_number(self.ch):
            self.read_char()
            if self.ch == ".":
                check_prec = True
                self.read_char()
        if check_prec:
            self.check_precision()

        return self.input[pos : self.position]

    def check_precision(self):
        """
        Need to retrieve scientific notation/precision.
        EX: 1.D-10, 1.E+3, 1._r8
        """
        peek_ch = self.peek_char()
        if peek_ch == " " or peek_ch == "\t":
            return
        if self.ch in ["d", "e"]:
            self.read_char()  # cur token is now one of the above.
            if self.ch in ["-", "+"]:
                self.read_char()
            # self.ch is either a letter or +/-
            self.read_char()
            self.read_num()  # Advance position to end of exponent
        elif self.ch == "_":
            self.read_identifier()
        return

    def skip_white_space(self) -> None:
        while self.ch == " " or self.ch == "\t":
            self.read_char()
        return

    def peek_char(self):
        if self.read_position >= len(self.input):
            return ""
        else:
            return self.input[self.read_position]

    def next_token(self) -> tokens.Token:
        """
        Get next tokens
        """

        self.skip_white_space()

        match self.ch:
            case "=":
                tok = new_token(tokens.TokenTypes.ASSIGN, self.ch)
            case "(":
                tok = new_token(tokens.TokenTypes.LPAREN, self.ch)
            case ")":
                tok = new_token(tokens.TokenTypes.RPAREN, self.ch)
            case ",":
                tok = new_token(tokens.TokenTypes.COMMA, self.ch)
            case "+":
                tok = new_token(tokens.TokenTypes.PLUS, self.ch)
            case "-":
                tok = new_token(tokens.TokenTypes.MINUS, self.ch)
            case "*":
                tok = new_token(tokens.TokenTypes.ASTERISK, self.ch)
            case "/":
                tok = new_token(tokens.TokenTypes.SLASH, self.ch)
            case "":
                tok = new_token(tokens.TokenTypes.EOF, "")
            case "\n":
                tok = new_token(tokens.TokenTypes.NEWLINE, self.ch)
            case ":":
                tok = new_token(tokens.TokenTypes.COLON, self.ch)
            case _:
                cur_ch = self.ch
                if cur_ch.isalpha() or cur_ch == "_":
                    lit: str = self.read_identifier()
                    tok_type = tokens.lookup_indentifer(lit)
                    tok = new_token(tok_type, lit)
                    return tok
                elif is_number(cur_ch):
                    lit: str = self.read_num()
                    if "." in lit:
                        tok = new_token(tokens.TokenTypes.FLOAT, lit)
                    else:
                        tok = new_token(tokens.TokenTypes.INT, lit)
                    return tok
                else:
                    tok = new_token(tokens.TokenTypes.ILLEGAL, self.ch)

        self.read_char()
        return tok


def is_valid_ident(ch: str) -> bool:
    "FORTRAN allows numbers, _, and % (for derived types) in identifier names"
    return ch.isalnum() or ch == "_" or ch == "%"


def is_number(ch: str) -> bool:
    return ch.isdigit()


def new_token(tok_type, lit) -> tokens.Token:
    token = tokens.Token(
        token=tok_type,
        literal=lit,
    )
    return token
