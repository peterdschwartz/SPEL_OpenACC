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
