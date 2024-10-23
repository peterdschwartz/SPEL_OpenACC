import pickle
import sys

from mod_config import E3SM_SRCROOT


def pickle_unit_test(mod_dict, sub_dict, type_dict):
    """
    Function to dump SPEL's output as pickled objects.
    """

    import subprocess as sp

    func_name = "pickle_unit_test"
    cmd = f"./git_commit.sh {E3SM_SRCROOT}"
    output = sp.getoutput(cmd)

    if "ERROR" in output:
        print(f"{func_name}::Couldn't find GIT COMMIT\n{output}")
        sys.exit(1)
    output = output.split()
    output[1] = output[1][0:7]
    commit = output[1]

    dbfile = open(f"mod_dict-{commit}.pkl", "ab")
    pickle.dump(mod_dict, dbfile)
    dbfile.close()

    for sub in sub_dict.values():
        sub.filepath = sub.filepath.replace(E3SM_SRCROOT, "")

    dbfile = open(f"sub_dict-{commit}.pkl", "ab")
    pickle.dump(sub_dict, dbfile)
    dbfile.close()

    dbfile = open(f"type_dict-{commit}.pkl", "ab")
    pickle.dump(type_dict, dbfile)
    dbfile.close()


def unpickle_unit_test(mod_dict, sub_dict, type_dict, commit):
    """
    Function to load SPEL's output from pickled files.
    """
    dbfile = open(f"mod_dict{commit}.pkl", "rb")
    mod_dict = pickle.load(dbfile)
    dbfile.close()

    dbfile = open(f"sub_dict{commit}.pkl", "rb")
    sub_dict = pickle.load(dbfile)
    dbfile.close()

    for sub in sub_dict.values():
        sub.filepath = E3SM_SRCROOT + sub.filepath

    dbfile = open(f"type_dict{commit}.pkl", "rb")
    type_dict = pickle.load(dbfile)
    dbfile.close()

    return mod_dict, sub_dict, type_dict


def create_dataframe(sub_dict):
    import pandas as pd

    # Create dataframe for subroutine's readwrite variable status:
    subname = "SoilTemperature".lower()
    sub = sub_dict[subname]
    # combine each dictionary
    status_dict = sub.elmtype_r | sub.elmtype_rw | sub.elmtype_w
    # flip the dicitonary to dataframe format:
    data_dict = {
        "variable names": [key for key in status_dict.keys()],
        "status": [val for val in status_dict.values()],
    }
    df = pd.DataFrame(data_dict)
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
