from pyparsing import (
    Forward,
    Group,
    Literal,
    OneOrMore,
    Optional,
    ParseException,
    Word,
    alphanums,
    alphas,
    delimitedList,
    nums,
)

from utilityFunctions import line_unwrapper


def test_parsing():

    # Define basic tokens
    identifier = Word(alphas + "_", alphanums + "_")
    number = Word(nums + ".")("number")
    expr = Forward()

    # Define arguments, allowing for nesting
    nested_parens = Forward()
    nested_parens <<= identifier + Literal("(") + delimitedList(expr) + Literal(")")
    expr <<= nested_parens | identifier | number

    # Define subroutine call structure
    subroutine_call = (
        Literal("call")
        + identifier("subroutine_name")
        + Literal("(")
        + delimitedList(expr)("args")
        + Literal(")")
    )

    # Example code to parse
    fortran_code = """call dynamic_plant_alloc(min(1.0_r8-N_lim_factor(p),1.0_r8-P_lim_factor(p)), W_lim_factor(p), &
                             laisun(p)+laisha(p), allocation_leaf(p), allocation_stem(p), &
                             allocation_froot(p), woody(ivt(p)))
    """
    lines = fortran_code.split("\n")
    print(lines)
    f90_string, _ = line_unwrapper(lines, 0)
    print(f90_string)

    # Parsing and printing results
    try:
        result = subroutine_call.parseString(f90_string)
        print("Subroutine name:", result.subroutine_name)
        print("Arguments:")
        for arg in result.args:
            print(" -", arg)
    except ParseException as pe:
        print("Parsing error:", pe)


if __name__ == "__main__":
    test_parsing()
