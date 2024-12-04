import random
from string import ascii_lowercase
from .analyze_subroutines import Subroutine
from helper_functions import ReadWrite


def generate_condition():
    """Generate a random condition."""
    conditions = [
        (".true.", True),
        (".false.", False),
        (".not. .true.", False),
        (".not. .false.", True),
    ]
    return random.choice(conditions)


def insert_variables():
    variables = [(i, False if random.random() < 0.5 else True) for i in ascii_lowercase]
    return random.choice(variables)


def generate_fortran_if(depth=0, max_depth=4, prev=True, ln=0, stack=[]):
    if depth > max_depth:
        return ""

    rando_condo = generate_condition()
    code = (
        f"{' ' * (depth * 3)}if ({rando_condo[0]}) then !{rando_condo[1] and prev} \n\n"
    )
    ln += 2
    rando_var = insert_variables()
    choices = (f"{rando_var[0]} = {str(rando_var[1])}"), "do_something"
    choice = random.choice(choices)
    if choice == choices[0]:
        stack.append((rando_var[0], ln))
    code += f"{' ' * (depth * 3 + 3)}{choice}\n\n"
    ln += 2

    # Decide what to include inside this block
    num_inner_blocks = random.randint(0, 2)
    for _ in range(num_inner_blocks):
        if random.random() < 0.7:  # 70% chance to add nested blocks
            code += f"{' ' * (depth-1 * 3)}{generate_fortran_if(depth + 1, max_depth, rando_condo[1], ln, stack) }"

    # # Randomly add elif or else blocks
    elseif_present = False
    elseif_cond = False
    if random.random() < 0.5:  # 50% chance for an elif block
        condo_rando = generate_condition()
        elseif_present = True
        elseif_cond = condo_rando[1]
        code += f"{' ' * (depth * 3)}else if ({condo_rando[0]}) then !{not rando_condo[1] and condo_rando[1]} \n\n"
        ln += 2
        rando_var = insert_variables()
        choices = (f"{rando_var[0]} = {str(rando_var[1])}"), "do_something"
        choice = random.choice(choices)
        if choice == choices[0]:
            stack.append((rando_var[0], ln))
        code += f"{' ' * (depth * 3 + 3)}{choice}\n\n"
        ln += 2
    if random.random() < 0.5:
        if elseif_present:
            odnar_odanc = elseif_cond and rando_condo[1]
        else:
            odnar_odanc = rando_condo[1]

        code += f"{' ' * (depth * 3)}else !{not odnar_odanc}\n\n"
        ln += 2
        rando_var = insert_variables()
        choices = (f"{rando_var[0]} = {str(rando_var[1])}"), "do_something"
        choice = random.choice(choices)
        if choice == choices[0]:
            stack.append((rando_var[0], ln))
        code += f"{' ' * (depth * 3 + 3)}{choice}\n\n"
        ln += 2

    code += f"{' ' * (depth * 3)}endif\n\n"
    ln += 2
    if random.random() < 0.5:
        rando_var = insert_variables()
        choices = (f"{rando_var[0]} = {str(rando_var[1])}"), "do_something"
        choice = random.choice(choices)
        if choice == choices[0]:
            stack.append((rando_var[0], ln))
        code += f"{' ' * (depth * 3 + 3)}{choice}\n\n"
        ln += 2

    return code


def generate_fortran_program(num_blocks=1, max_depth=4):
    """Generate a complete Fortran program with randomly nested if blocks."""
    program = ""
    stack = []
    ln = 0
    for _ in range(num_blocks):
        program += generate_fortran_if(
            max_depth=max_depth, prev=True, ln=ln, stack=stack
        )

        program += "\n"
        ln += 1

    subroutine = "test"
    sub_dict = {
        subroutine: Subroutine(
            name=subroutine,
            calltree=[],
            file="test",
            start=-999,
            end=-999,
            lib_func=True,
        )
    }
    sub_dict[subroutine].elmtype_access_by_ln = {}

    print(stack)
    return program


# Generate a Fortran program with 3 nested blocks and a maximum depth of 3
if __name__ == "__main__":
    fortran_code = generate_fortran_program(num_blocks=1, max_depth=4)
    with open("unitTest.F90", "w") as file:
        file.write(fortran_code)

    print(fortran_code)
