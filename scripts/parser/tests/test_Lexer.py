import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import lexer
from spel_parser import Parser
from tokens import Token, TokenTypes


class LexTests(unittest.TestCase):

    def test_tokens(self):
        input = """x = 5
        call func(1)
        """

        expected_tokens = [
            # line 1
            Token(token=TokenTypes.IDENT, literal="x"),
            Token(token=TokenTypes.ASSIGN, literal="="),
            Token(token=TokenTypes.INT, literal="5"),
            Token(token=TokenTypes.NEWLINE, literal="\n"),
            # line2
            Token(token=TokenTypes.CALL, literal="call"),
            Token(token=TokenTypes.IDENT, literal="func"),
            Token(token=TokenTypes.LPAREN, literal="("),
            Token(token=TokenTypes.INT, literal="1"),
            Token(token=TokenTypes.RPAREN, literal=")"),
            Token(token=TokenTypes.NEWLINE, literal="\n"),
        ]

        lex = lexer.Lexer(input)

        for expected_tok in expected_tokens:
            tok = lex.next_token()
            with self.subTest(ans=expected_tok):
                self.assertEqual(tok, expected_tok)

    def test_parser(self):

        input = """1+2*x_1
        -2*_x%y-1/2
        (x-y)/(2*y+1)
        add(1,min(2*x,4))"""
        lex = lexer.Lexer(input)
        parser = Parser(lex=lex)
        program = parser.parse_program()

        expected_stmts = [
            "(1+(2*x_1))",
            "(((-2)*_x%y)-(1/2))",
            "((x-y)/((2*y)+1))",
            "[add(1,[min((2*x),4)])]",
        ]

        if parser.errors:
            for err in parser.errors:
                print("err: ", err)

        for n, ans in enumerate(expected_stmts):
            with self.subTest(ans=ans):
                stmt = str(program.statements[n])
                self.assertEqual(stmt, ans)


if __name__ == "__main__":
    unittest.main()
