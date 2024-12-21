import pickle
import sys

from scripts.analyze_subroutines import Subroutine
from scripts.DerivedType import DerivedType
from scripts.fortran_modules import FortranModule
from scripts.mod_config import E3SM_SRCROOT, scripts_dir


def pickle_unit_test(
    mod_dict: dict[str, FortranModule],
    sub_dict: dict[str, Subroutine],
    type_dict: dict[str, DerivedType],
):
    """
    Function to dump SPEL's output as pickled objects.
    """

    import subprocess as sp

    func_name = "pickle_unit_test"
    cmd = f"{scripts_dir}/git_commit.sh {E3SM_SRCROOT}"
    output = sp.getoutput(cmd)

    if "ERROR" in output:
        print(f"{func_name}::Couldn't find GIT COMMIT\n{output}")
        sys.exit(1)
    output = output.split()
    output[1] = output[1][0:7]
    commit = output[1]

    for mod in mod_dict.values():
        mod.filepath = mod.filepath.replace(E3SM_SRCROOT, "")

    dbfile = open(f"{scripts_dir}/mod_dict-{commit}.pkl", "ab")
    pickle.dump(mod_dict, dbfile)
    dbfile.close()

    for sub in sub_dict.values():
        sub.filepath = sub.filepath.replace(E3SM_SRCROOT, "")

    dbfile = open(f"{scripts_dir}/sub_dict-{commit}.pkl", "ab")
    pickle.dump(sub_dict, dbfile)
    dbfile.close()

    for dtype in type_dict.values():
        dtype.filepath = dtype.filepath.replace(E3SM_SRCROOT, "")

    dbfile = open(f"{scripts_dir}/type_dict-{commit}.pkl", "ab")
    pickle.dump(type_dict, dbfile)
    dbfile.close()


def unpickle_unit_test(commit):
    """
    Function to load SPEL's output from pickled files.
    """
    mod_dict, sub_dict, type_dict = {}, {}, {}
    dbfile = open(f"{scripts_dir}/mod_dict{commit}.pkl", "rb")
    mod_dict = pickle.load(dbfile)
    dbfile.close()

    for mod in mod_dict.values():
        mod.filepath = E3SM_SRCROOT + mod.filepath

    dbfile = open(f"{scripts_dir}/sub_dict{commit}.pkl", "rb")
    sub_dict = pickle.load(dbfile)
    dbfile.close()

    for sub in sub_dict.values():
        sub.filepath = E3SM_SRCROOT + sub.filepath

    dbfile = open(f"{scripts_dir}/type_dict{commit}.pkl", "rb")
    type_dict = pickle.load(dbfile)
    dbfile.close()
    for dtype in type_dict.values():
        dtype.filepath = E3SM_SRCROOT + dtype.filepath

    return mod_dict, sub_dict, type_dict


def create_dataframe(sub_dict, filename):
    import pandas as pd

    main_data_dict = {"subroutine": [], "variable names": [], "status": []}
    # Create dataframe for subroutine's readwrite variable status:
    for subname in sub_dict.keys():
        sub = sub_dict[subname]

        status_dict = sub.elmtype_r | sub.elmtype_rw | sub.elmtype_w

        main_data_dict["subroutine"].extend([subname] * len(status_dict))
        main_data_dict["variable names"].extend([key for key in status_dict.keys()])
        main_data_dict["status"].extend([val for val in status_dict.values()])

    df = pd.DataFrame(main_data_dict)
    df.to_csv(f"{filename}.csv")
    return df


def global_var_dataframe(mod_dict):
    import pandas as pd

    for mod in mod_dict.values():
        variables = [
            v.name + "_" + str(v.dim) + "-D"
            for v in mod.global_vars
            # if v.type in ["real", "integer", "logical", "character"] and not v.parameter
            if v.type == "logical" and not v.parameter
        ]
        print(mod.name)
        print(mod.modules)


if __name__ == "__main__":
    mod_dict = {}
    sub_dict = {}
    type_dict = {}

    mod_dict, sub_dict, type_dict = unpickle_unit_test(mod_dict, sub_dict, type_dict)

    global_var_dataframe(mod_dict)
    df_test = create_dataframe(sub_dict)

    print(df_test)
