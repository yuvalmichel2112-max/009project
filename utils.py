import mysql.connector
from contextlib import contextmanager

def mydb():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="flyTAU",
        autocommit=True
        )

@contextmanager
def db_cur():
    conn = mydb()
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()

def get_airplane_dimensions(flight_id):
    with db_cur() as cursor:
        query = "SELECT a.rows, a.columns FROM airplane AS a JOIN flights AS f ON f.airplane_id = a.id WHERE f.id = %s"
        cursor.execute(query,(flight_id,))
        result = cursor.fetchone()
        if result:
            rows = result.get("rows",0)
            columns = result.get("columns",0)
            return rows, columns
        return 0,0
