import subprocess as sp

from scripts.mod_config import ELM_SRC

interface_list: list[str] = []


def populate_interface_list():
    """
    returns a list of all interfaces
    """

    cmd = f'grep -rin --exclude-dir={ELM_SRC}external_models/ -E "^[[:space:]]+(interface)" {ELM_SRC}*'
    output = sp.getoutput(cmd)
    output = output.split("\n")
    global interface_list
    if interface_list:
        print("Warning - Trying to recalculate interface list")
    for el in output:
        el = el.split()
        interface = el[2]
        interface_list.append(interface.lower())

    return
