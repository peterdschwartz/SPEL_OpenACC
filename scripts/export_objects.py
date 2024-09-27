import pickle


def pickle_unit_test(mod_dict, sub_dict, type_dict):
    """
    Function to dump SPEL's output as pickled objects.
    """
    dbfile = open("mod_dict.pkl", "ab")
    pickle.dump(mod_dict, dbfile)
    dbfile.close()

    dbfile = open("sub_dict.pkl", "ab")
    pickle.dump(sub_dict, dbfile)
    dbfile.close()

    dbfile = open("type_dict.pkl", "ab")
    pickle.dump(type_dict, dbfile)
    dbfile.close()


def unpickle_unit_test(mod_dict, sub_dict, type_dict):
    """
    Function to load SPEL's output from pickled files.
    """
    dbfile = open("mod_dict.pkl", "rb")
    mod_dict = pickle.load(dbfile)
    dbfile.close()

    dbfile = open("sub_dict.pkl", "rb")
    sub_dict = pickle.load(dbfile)
    dbfile.close()

    dbfile = open("type_dict.pkl", "rb")
    type_dict = pickle.load(dbfile)
    dbfile.close()

    return mod_dict, sub_dict, type_dict


def create_dataframe(sub_dict):
    import pandas as pd

    # Create dataframe for subroutine's readwrite variable status:
    subname = "SurfaceAlbedo"
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
