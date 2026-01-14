import mysql.connector
from contextlib import contextmanager
from datetime import datetime, timedelta

def mydb():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="flytau",
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

def get_flight_dept(flight_id):
    with db_cur() as cursor:
        query = """SELECT a.size AS airplane_size 
                FROM airplane AS a JOIN flight AS f ON a.id = f.airplane_id
                WHERE f.id = %s"""
        cursor.execute(query,(flight_id,))
        airplane_size = cursor.fetchone()
        flight_dept = ['Economy']
        if airplane_size and airplane_size[0] == 'large':
            flight_dept.append('Business')
        return flight_dept

def get_time_display(departure_time, duration):
    if not departure_time or duration is None:
        return "--:--", "--:--"
    landing_time = departure_time + timedelta(hours=float(duration))
    departure_display=departure_time.strftime('%H:%M')
    landing_display = landing_time.strftime('%H:%M')
    if landing_time.date() > departure_time.date():
        days_diff = (landing_time.date() - departure_time.date()).days
        landing_display += f" (+{days_diff} day)"
    return departure_display, landing_display

def get_department_dimensions(flight_id, department_type):
    with db_cur() as cursor:
        query = """
            SELECT d.number_of_rows, d.number_of_columns 
            FROM department AS d 
            JOIN flight AS f ON f.airplane_id = d.airplane_id 
            WHERE f.flight_id = %s AND d.department_type = %s"""
        cursor.execute(query,(flight_id,department_type))
        result = cursor.fetchone()
        if result:
            return result[0], result[1]
        return 0,0

def get_occupied_seats(flight_id,department_type):
    with db_cur() as cursor:
        query = """SELECT s.row_number, s.column_number
                    FROM seats AS s     
                    WHERE s.status='occupied'
                    AND flight_id=%s
                     AND department_type=%s """
        cursor.execute(query, (flight_id,department_type))
        occupied_seats = cursor.fetchall()
        occupied = [f"{occupied_seats[0]}-{occupied_seats[1]}" for seat in occupied_seats]
        return occupied

def save_booking(email, selected_seats, flight_id):
    seats_str = ", ".join(selected_seats)
    with db_cur() as cursor:
        query = "INSERT INTO booking (email, seats_str, "


def get_all_locations():
    with db_cur() as cursor:
        cursor.execute("SELECT DISTINCT city, country FROM airport")
        locations =  cursor.fetchall()
        return locations
