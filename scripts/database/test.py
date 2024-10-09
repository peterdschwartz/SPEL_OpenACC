import csv

import importlib
import mariadb
import sys
import csv

def connect():
    try:
        conn = mariadb.connect(
            user="root",
            password="root",
            host="127.0.0.1",
            port=3306,
            database="spel",
        )
    except mariadb.Error as e:
        print("error")
        sys.exit(1)
    cur = conn.cursor()
    return cur, conn




TYPE_DEFAULT_DICT = {
    "table": "user_types",
    "id": "",
    "module": "",
    "type_name": "",
    "member": "",
    "member_type": "",
    "dim": "",
    "bounds": "",
    "active": ""
}

MODS_DEFAULT_DICT = {
    "table": "subroutine_active_global_vars",
    "id": "",
    "subroutine": "",
    "variable_name": "",
    "status": "",
}

cur, conn = connect()


def query(parm_dict):

    table_name = parm_dict['table']

    statement = f"SELECT * FROM {table_name} where "
    
    # create query statement based on parm_dict
    for parm in list(parm_dict.keys())[1:]:
        
        statement += f"{parm} like '%'" if not parm_dict[parm] else f"{parm}='{parm_dict[parm]}'"
        
        if parm != list(parm_dict.keys())[-1]:
            statement += " and "
            
    return statement
       
       
MODS_DEFAULT_DICT["id"] = '1'

q = query(MODS_DEFAULT_DICT)
print(q)
cur.execute(q)
conn.commit()
print(list(cur))




def insert(cur, conn, table_name, csv_file):
    with open(csv_file, "r") as file:
        reader = csv.reader(file)
        cols = []
        val_types = ["%s"]
        header = True
        for line in reader:
            
            # grab header info from first line
            if header:
                cols = line
                length = len(cols)
                cols = ", ".join(['`' + col.strip() + '`' for col in cols])
                val_types = ", ".join(val_types * length)
                header = False
                continue
            # insert into table
            cur.execute(
                f"INSERT INTO {table_name} ({cols}) VALUES ({val_types})",
                (line)
            )
            conn.commit()
            
# insert(cur, conn, "subroutine_active_global_vars", csv_file="../testcopy.csv")





