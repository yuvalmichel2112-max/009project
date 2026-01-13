from flask import Flask, request, session, render_template, url_for

import utils
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import mydb, db_cur, get_department_dimensions, get_occupied_seats, save_booking, get_all_locations
from contextlib import contextmanager
from datetime import date

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)


@app.route("/", methods =["GET", "POST"])
def home_page():
    if request.method == "POST":
        email=request.form.get("registered_email")
        password= request.form.get("registered_password")
        query = "SELECT * FROM registered_customer WHERE email = %s AND password = %s"
        with db_cur as cursor:
            cursor.execute(query,(email,password))
            user=cursor.fetchone()
        if user:
            session["registered_email"]=user["customer_email"]
            return redirect("/search_flights")
        else:
            return render_template("home_page.html", error="Incorrect email or password")
    return render_template("home_page.html")




# @app.route("/continue_as_guest", methods = ["POST"])
# def continue_as_guest():
#     Session["guest_email"]=request.form.get("guest_email")
#     query1 = "INSERT INTO customer(email, first_name, last_name) VALUES (%s, %s, %s)"
#     query2 = "INSERT INTO customer_phone_number(guest_email, phone_number) VALUES (%s, %s)"
#     with db_cur as cursor:
#         cursor.execute(query1, (session["guest_email"], session["first_name"], session["last_name"]))
#         cursor.execute(query2, (session["guest_email"], session["phones_list"]))
#         return redirect("/flights")

@app.route("/sign_up", methods = ["POST", "GET"])
def sign_up():
    today= date.today().strftime('%Y-%m-%d')
    if request.method == "POST":
        first_name=request.form.get("first_name")
        last_name = request.form.get("last_name")
        date_of_birth=request.form.get("date_of_birth")
        registered_email = request.form.get("registered_email")
        passport_number=request.form.get("passport_number")
        phones_list = request.form.getlist("phones_list")
        date_of_registration = request.form.get("date_of_registration")
        registered_password = request.form.get("registered_password")
        with db_cur as cursor:
            cursor.execute("SELECT * FROM registered_customer WHERE passport_number=%s",(passport_number,))
            if cursor.fetchone():
                return render_template('sign_up.html', error = "passport number already exists")
            query1 = "INSERT INTO customer(email, first_name, last_name) VALUES (%s, %s, %s)"
            cursor.execute(query1, (session["registered_email"], session["first_name"], session["last_name"]))
            query2 = "INSERT INTO registered_customer(customer_email, password, birth_date, registration_date, passport_number) VALUES (%s, %s, %s,%s, %s)"
            cursor.execute(query2, (session["registered_email"],session["registered_password"],session["date_of_birth"], session["registered_password"],session["registered_password"] ))
            query3 = "INSERT INTO customer_phone_number(customer_email, phone_number) VALUES (%s, %s)"
            cursor.execute(query3, (session["registered_email"],session["phones_list"]))
        return redirect("/flights")
    return render_template("sign_up.html")

@app.route("/search_flights", methods = ["GET", "POST"])
def search_flights():
    today = date.today().strftime('%Y-%m-%d')
    locations = get_all_locations()
    if request.method == "POST":
        loc1 = request.form.get("loc1")
        loc2 = request.form.get("loc2")
        date_of_flights = request.form.get("date_of_flights")
        number_of_pass = request.form.get("passengers")
        return redirect(url_for("choose_flight",origin=loc1, destination=loc2,date=date_of_flights, passengers=number_of_pass))
    return render_template("search_flight.html", locations=locations, today=today)

@app.route("/choose_flight", methods = ["GET", "POST"])
def choose_flight():
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    flight_date = request.args.get('flight_date')
    passengers = request.args.get('passengers')
    query = """SELECT f.*, r.duration,o.code as origin_code, d.code as destination_code
            FROM flights f
            JOIN flight_route AS r 
            ON f.origin_airport_code = r.origin_airport_code 
            AND f.destination_airport_code = r.destination_airport_code
            JOIN airports AS o ON f.origin_airport_id = o.id
            JOIN airports AS d ON f.dest_airport_id = d.id
            WHERE f.origin_airport_id = %s 
            AND f.dest_airport_id = %s 
            AND DATE(f.departure_time) = %s"""
    with db_cur as cursor:
        cursor.execute(query,(origin,destination, flight_date))
        db_flights = cursor.fetchall()
        processed_flights = []
        for flight in db_flights:
            departure_date, landing_date=utils.get_time_display(flight['departure_time'], flight['duration'])
            flight_info = {'flight_id': flight['id'],
            'status': flight['status'],
            'origin_code': flight['origin_code'],
            'destination_code': flight['destination_code'],
            'departure_time': departure_date,
            'landing_time': landing_date,
            'duration': f"{flight['duration']}h",
            'has_business': True if flight['business_seats_count'] > 0 else False}
            processed_flights.append(flight_info)
        return render_template("/choose_flight.html",flights=processed_flights, passengers=passengers)

# @app.route("/flights", methods = ["GET"])
# def show_flights():
#     def show_flights():
#         try:
#             with db_cur() as cursor:
#                 query = """
#                     SELECT f.flight_id, f.origin_airport, f.destination_airport, f.departure_date, f.status,
#                            d.department_type
#                     FROM flights f
#                     JOIN department d ON f.airplane_id = d.airplane_id
#                     WHERE f.status = 'active'
#                 """
#                 cursor.execute(query)
#                 rows = cursor.fetchall()
#             flights_dict = {}
#             for row in rows:
#                 f_id = row['flight_id']
#                 if f_id not in flights_dict:
#                     flights_dict[f_id] = row
#                     flights_dict[f_id]['available_depts'] = []
#                 flights_dict[f_id]['available_depts'].append(row['department_type'])
#             return render_template("search_flights.html", flights=list(flights_dict.values()))
#         except mysql.connector.Error as err:
#             print(f"Database error: {err}")

@app.route("/flight/<flight_id>/seats/<department_type>", methods = ["GET", "POST"]) ### לא יודעות מה לכתוב פה
def select_seats():
    flight_id = session.get['flight_id']
    department_type = session.get['department_type']
    occupied = get_occupied_seats(flight_id, department_type)
    rows, cols = get_department_dimensions(flight_id, department_type)
    if request.method == 'POST':
        selected = request.form.getlist("seat_choice")

# save_booking(session['email'], selected, flight_id) #האם ואיך צריכה להיות הפרדה בין לקוח רשום ללקוח ואיך ?
#         return (f"seats booked for {flight_id}")
#     return render_template("seats.html", rows = rows, cols = cols, flight_id = flight_id, occupied = occupied)
#

@app.route("/managers_log_in", methods = ["GET", "POST"])
def managers_log_in():
    if request.method == "POST":
        session["managers_ID"] = request.form.get("managers_ID")
        session["managers_password"] = request.form.get("managers_password")
        return redirect("/managers_home_page")
    return render_template("managers_log_in.html")

@app.route("/managers_home_page", methods = ["GET"])
def managers_home_page():
    manager_id = session["managers_ID"]
    if not manager_id:
        return redirect("/managers_log_in")
    with db_cur as cursor:
        query = "SELECT first_name FROM managers WHERE id = %s"
        cursor.execute(query, (manager_id,))
        result = cursor.fetchone()
        manager_first_name = result[0]

if __name__ == "__main__":
    app.run(debug=True)
