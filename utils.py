import mysql.connector
from contextlib import contextmanager
from datetime import datetime, timedelta
import random

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
        query = """SELECT d.Number_of_rows, d.Number_of_columns 
                FROM Department AS d 
                JOIN Flight AS f ON f.Airplane_id = d.Airplane_id 
                WHERE f.id = %s AND d.type = %s"""
        cursor.execute(query,(flight_id,department_type))
        result = cursor.fetchone()
        if result:
            if isinstance(result, dict):
                return result['Number_of_rows'], result['Number_of_columns']
            return result[0], result[1]
        return 0, 0


def get_occupied_seats(flight_id, department_type):
    with db_cur() as cursor:
        query = """
            SELECT t.Seat_row, t.Seat_col
            FROM Ticket AS t
            JOIN Booking AS b ON t.Booking_ID = b.ID
            WHERE t.Flight_ID = %s 
            AND t.Department_type = %s 
            AND b.Status != 'canceled'"""
        cursor.execute(query, (flight_id, department_type))
        occupied_seats = cursor.fetchall()
        occupied = []
        for seat in occupied_seats:
            if isinstance(seat, dict):
                row = seat.get('Seat_row')
                col = seat.get('Seat_col')
                occupied.append(f"{row}-{col}")
            else:
                occupied.append(f"{seat[0]}-{seat[1]}")
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

def get_reg_cus_info(email):
    if not email:
        return None
    with db_cur() as cursor:
        query= """SELECT c.First_name, c.Last_name, c.Email, r.Passport_number, r.Birth_date
                FROM customer c
                JOIN registered_customer r ON c.Email = r.Customer_Email
                WHERE c.Email = %s
            """
        cursor.execute(query,(email,))
        customer_data = cursor.fetchone()
        if not customer_data:
            return None
        query_phones = "SELECT Phone_number FROM customer_phone_number WHERE Customer_email = %s"
        cursor.execute(query_phones, (email,))
        phones_result = cursor.fetchall()
        customer_data['phones_list'] = [row['Phone_number'] for row in phones_result]
        return customer_data

def add_guest_to_db(first_name, last_name, email, phone_number):
    with db_cur() as cursor:
            cursor.execute("INSERT IGNORE INTO customer(First_name, Last_name, Customer_Email) VALUES (%s, %s, %s)",(first_name, last_name, email))
            cursor.execute("INSERT IGNORE INTO guest(Customer_Email) VALUE %s", (email,))
            for phone in phone_number:
                if phone:
                    cursor.execute("INSERT IGNORE INTO customer_phone_number(Customer_Email, Customer_phone_number) values (%s, %S)", (email, phone))

def generate_unique_id(table_name, column_name):
    with db_cur() as cursor:
        while True:
            new_id = random.randint(1000, 9999)
            query = f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = %s"
            cursor.execute(query, (new_id,))
            result = cursor.fetchone()
            if isinstance(result, dict):
                count = list(result.values())[0]
                return new_id
            else:
                count = result[0]
            if count == 0:
                return new_id