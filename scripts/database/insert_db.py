import export_objects as eo
import importlib
import mariadb
import sys
import csv


def create_dicts():
    mod_dict, sub_dict, type_dict = {}, {}, {}

    mod_dict, sub_dict, type_dict = eo.unpickle_unit_test(mod_dict, sub_dict, type_dict)    

    return mod_dict, sub_dict, type_dict
    

def connect():
    try:
        conn = mariadb.connect(
            user="root",
            password="root",
            host="127.0.0.1",
            port=3306,
            database="spel",
            # unix_socket='/var/run/mysqld/mysqld.sock'  # Use the correct path
        )
    except mariadb.Error as e:
        print("error")
        sys.exit(1)
    cur = conn.cursor()
    return cur, conn


def gen_data(dict, filename):
    eo.create_dataframe(dict, filename)
    

def mod_insert(cur, conn, filename):
    with open(filename, "r", ) as file:
        reader = csv.reader(file)
        f = 0
        for i in reader:
            if f == 0: 
                f += 1
                continue
            cur.execute(
                "INSERT INTO mods (`subroutine`, `variable_name`, `status`) VALUES (%s, %s, %s)",
                (i[1].strip(), i[2].strip(), i[3].strip())
            )
        conn.commit()
        
def type_insert(cur, conn, filename):
    with open(filename, "r", ) as file:
        reader = csv.reader(file)
        f = 0
        for i in reader:
            if f == 0: 
                f += 1
                continue
            cur.execute(
                "INSERT INTO user_types (`module`, `type_name`, `member`, `member_type`, `dim`, `bounds`, `active`) VALUES (%s, %s, %s, %s, %d, %s, %s)",
                (i[0].strip(), i[1].strip(), i[2].strip(), i[3].strip(), i[4], i[5], i[6][0])
            )
        conn.commit()
    


    

def query(parm_dict):
    table_name = parm_dict['table']

    statement = f"SELECT * FROM {table_name} where "
    for parm in list(parm_dict.keys())[1:]:
        
        statement += f"{parm} like '%'" if not parm_dict[parm] else f"where {parm}='{parm_dict[parm]}'"
        if parm != list(parm_dict.keys())[-1]:
            statement += " and "
    return statement
