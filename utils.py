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

def get_department_dimensions(flight_id, department_type):
    with db_cur() as cursor:
        query = """
            SELECT d.number_of_rows, d.number_of_columns 
            FROM department AS d 
            JOIN flights AS f ON f.airplane_id = d.airplane_id 
            WHERE f.flight_id = %s AND d.department_type = %s
        """
        cursor.execute(query,(flight_id,department_type))
        result = cursor.fetchone()
        if result:
            rows = result.get("number_of_rows",0)
            columns = result.get("number_of_columns",0)
            return rows, columns
        return 0,0

def get_occupied_seats(flight_id,department_type):
    with db_cur as cursor:
        query = "SELECT s.row_number, s.column_number FROM seats AS s WHERE s.status=occupied, flight_id=%s, department_type=%s "
        cursor.execute(query, (flight_id,department_type))
        occupied_seats = cursor.fetchall()
        occupied = [f"{occupied_seats[0]}-{occupied_seats[1]}" for seat in occupied_seats]
        return occupied

def save_booking(email, selected_seats, flight_id):
    seats_str = ", ".join(selected_seats)
    with db_cur as cursor:
        query = "INSERT INTO booking (email, seats_str, "


def get_all_locations():
    with db_cur as cursor:
        cursor.execute("SELECT * FROM airport")
        return cursor.fetchall
