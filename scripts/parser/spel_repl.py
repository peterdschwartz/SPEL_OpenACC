import os

import lexer
from spel_parser import Parser


def start_repl():
    os.system("banner SPEL REPL")

    while True:
        user_input = input(">>> ")
        lex = lexer.Lexer(user_input)
        parser = Parser(lex=lex)

        program = parser.parse_program()

        for stmt in program.statements:
            print(stmt)


if __name__ == "__main__":
    start_repl()
