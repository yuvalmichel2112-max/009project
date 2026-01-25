import mysql.connector
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from flask import  session, redirect

#This function creates a connection to the FlyTAU database using the required login information.
def mydb():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="flytau",
        autocommit=True
        )

#This function manages the database cursor and ensures the connection is closed after a task is finished.
@contextmanager
def db_cur():
    conn = mydb()
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()

#This function determines if a flight offers Business class or only Economy based on the aircraft size.
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

#This function calculates the arrival time and formats the departure and landing times for display.
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

#This function retrieves the number of rows and columns for a specific seating section on a plane.
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

#This function returns a list of all seats that are already taken and paid for on a specific flight.
def get_occupied_seats(flight_id, department_type):
    with db_cur() as cursor:
        query = """
            SELECT t.Seat_row, t.Seat_col
            FROM Ticket AS t
            JOIN Booking AS b ON t.Booking_ID = b.ID
            WHERE t.Flight_ID = %s 
            AND t.Department_type = %s 
            AND b.Status = 'Active'"""
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

#This function provides a list of all cities and countries where the airline operates.
def get_all_locations():
    with db_cur() as cursor:
        cursor.execute("SELECT DISTINCT city, country FROM airport")
        locations =  cursor.fetchall()
        return locations

#This function fetches all saved details and phone numbers for a registered customer using their email.
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

#This function adds a temporary guest profile to the database so they can book a flight without an account.
def add_guest_to_db(first_name, last_name, email, phone_number):
    with db_cur() as cursor:
            cursor.execute("INSERT IGNORE INTO customer(First_name, Last_name, Customer_Email) VALUES (%s, %s, %s)",(first_name, last_name, email))
            cursor.execute("INSERT IGNORE INTO guest(Customer_Email) VALUE %s", (email,))
            for phone in phone_number:
                if phone:
                    cursor.execute("INSERT IGNORE INTO customer_phone_number(Customer_Email, Customer_phone_number) values (%s, %S)", (email, phone))

#This function generates a new 4-digit ID and ensures it is unique by checking the database first.
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

#This function finds the last destination of a pilot, attendant, or plane to know where they are currently.
def get_last_location(cursor, table_link, id_column_name, resource_id):
    if table_link == 'Flight':
        sql = """
            SELECT Flight_Route_destination_Airport_Code FROM Flight 
            WHERE Airplane_ID = %s AND status != 'cancelled'
            ORDER BY Departure_datetime DESC LIMIT 1
        """
    else:
        sql = f"""
            SELECT f.Flight_Route_destination_Airport_Code 
            FROM Flight f
            JOIN {table_link} link ON f.ID = link.Flight_ID
            WHERE link.{id_column_name} = %s AND f.status != 'cancelled'
            ORDER BY f.Departure_datetime DESC LIMIT 1
        """
    cursor.execute(sql, (resource_id,))
    result = cursor.fetchone()
    return result[0] if result else None

#This function looks for planes and crew members that are in the right city and ready for a new flight assignment.
def get_available_resources(cursor, origin, destination, departure_str, plane_size):
    cursor.execute("SELECT Duration FROM Flight_Route WHERE origin_Airport_Code = %s AND destination_Airport_Code = %s",
                   (origin, destination))
    route_data = cursor.fetchone()
    if not route_data: return {"error": "Route not found"}

    duration = route_data[0]
    is_long_haul = duration > 6
    req = {'small': {'p': 2, 'a': 3}, 'large': {'p': 3, 'a': 6}}[plane_size]

    available = {"airplanes": [], "pilots": [], "attendants": []}
    cursor.execute("SELECT ID, Size FROM Airplane WHERE Size = %s", (plane_size,))
    for plane in cursor.fetchall():
        loc = get_last_location(cursor, 'Flight', 'Airplane_ID', plane[0])
        if loc is None or loc == origin:
            available["airplanes"].append(plane)
    p_sql = "SELECT ID, First_name, Last_name FROM Pilot"
    if is_long_haul:
        p_sql += " WHERE Long_flight_training = 'yes'"
    cursor.execute(p_sql)
    for p in cursor.fetchall():
        loc = get_last_location(cursor, 'Pilot_in_Flight', 'Pilot_ID', p[0])
        if loc is None or loc == origin:
            available["pilots"].append(p)
    a_sql = "SELECT ID, First_name, Last_name FROM Flight_attendant"
    if is_long_haul:
        a_sql += " WHERE Long_flight_training = 'yes'"
    cursor.execute(a_sql)
    for a in cursor.fetchall():
        loc = get_last_location(cursor, 'Flight_attendant_in_Flight', 'Flight_attendant_ID', a[0])
        if loc is None or loc == origin:
            available["attendants"].append(a)
    if len(available["pilots"]) < req['p']:
        return {"error": f"there's not enough pilots {req['p']})"}
    if len(available["attendants"]) < req['a']:
        return {"error": f"there's not enough flight attendant {req['a']})"}
    return {"success": True, "data": available}

#This function automatically marks flights as 'completed' once they land or 'fully booked' when all seats are sold.
def sync_flight_statuses():
    try:
        with db_cur() as cursor:
            query_completed = """
            UPDATE Flight f
            JOIN Flight_route r ON f.Flight_route_origin_airport_code = r.origin_airport_code 
                               AND f.Flight_route_destination_airport_code = r.destination_airport_code
            SET f.status = 'completed'
            WHERE f.status IN ('active', 'fully booked') 
              AND DATE_ADD(f.departure_datetime, INTERVAL r.duration HOUR) < NOW();
            """
            cursor.execute(query_completed)
            query_full = """
            UPDATE Flight f
            SET f.status = 'fully booked'
            WHERE f.status = 'active'
              AND (
                  SELECT COUNT(*) FROM Ticket t WHERE t.flight_IDF = f.ID
              ) >= (
                  SELECT SUM(d.number_of_rows * d.number_of_columns) 
                  FROM Department d 
                  WHERE d.Airplane_IDF = f.Airplane_IDF
              );
            """
            cursor.execute(query_full)
    except Exception as e:
        print(f"Error updating statuses: {e}")

#This is a security function that checks if the person trying to access a page is a manager.
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

