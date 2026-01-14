from flask import Flask, request, session, render_template, url_for
import utils
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import db_cur, get_department_dimensions, get_occupied_seats, save_booking, get_all_locations
from contextlib import contextmanager
from datetime import date

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route("/", methods=["GET", "POST"])
def home_page():
    if request.method == "POST":
        email = request.form.get("registered_email")
        password = request.form.get("registered_password")
        query = "SELECT * FROM registered_customer WHERE customer_email = %s AND password = %s"
        with db_cur() as cursor:
            cursor.execute(query, (email, password))
            user = cursor.fetchone()
        if user:
            session["customer_email"] = user["Customer_Email"]
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
        with db_cur() as cursor:
            cursor.execute("SELECT * FROM registered_customer WHERE passport_number=%s",(passport_number,))
            if cursor.fetchone():
                return render_template('sign_up.html', error = "passport number already exists")
            query1 = "INSERT INTO customer(email, first_name, last_name) VALUES (%s, %s, %s)"
            cursor.execute(query1, (session["registered_email"], session["first_name"], session["last_name"]))
            query2 = "INSERT INTO registered_customer(customer_email, password, birth_date, registration_date, passport_number) VALUES (%s, %s, %s,%s, %s)"
            cursor.execute(query2, (session["registered_email"],session["registered_password"],session["date_of_birth"], session["registered_password"],session["registered_password"] ))
            query3 = "INSERT INTO customer_phone_number(customer_email, phone_number) VALUES (%s, %s)"
            cursor.execute(query3, (session["registered_email"],session["phones_list"]))
        return redirect("/search_flights")
    return render_template("sign_up.html")

@app.route("/search_flights", methods=["GET", "POST"])
def search_flights():
    today = date.today().strftime('%Y-%m-%d')
    if request.method == "POST":
        date_of_flights = request.form.get("date_of_flights")
        number_of_pass = request.form.get("passengers")
        origin_raw = request.form.get("loc1")
        dest_raw = request.form.get("loc2")
        if origin_raw == dest_raw:
            locations = get_all_locations()
            return render_template("search_flight.html",
                                   locations=locations,
                                   today=today,
                                   error="Origin and destination must be different!")
        try:
            origin_city, origin_country = origin_raw.split(", ")
            dest_city, dest_country = dest_raw.split(", ")
        except (ValueError, AttributeError):
            locations = get_all_locations()
            return render_template("search_flights.html",
                                   locations=locations,
                                   today=today,
                                   error="Please select a valid location from the list.")
        return redirect(url_for("choose_flight",
                                origin_city=origin_city,
                                origin_country=origin_country,
                                dest_city=dest_city,
                                dest_country=dest_country,
                                date=date_of_flights,
                                passengers=number_of_pass))
    locations = get_all_locations()
    return render_template("search_flights.html", locations=locations, today=today)

@app.route("/choose_flight", methods = ["GET", "POST"])
def choose_flight():
    origin_city = request.args.get('origin_city')
    destination_city = request.args.get('dest_city')
    flight_date = request.args.get('date')
    passengers = request.args.get('passengers')
    query = """SELECT f.*, r.duration, o.code as origin_code, d.code as destination_code
                FROM flight f
                JOIN flight_route AS r 
                ON f.flight_route_origin_airport_code = r.origin_airport_code 
                AND f.flight_route_destination_airport_code = r.destination_airport_code
                JOIN airport AS o ON f.flight_route_origin_airport_code = o.code
                JOIN airport AS d ON f.flight_route_destination_airport_code = d.code
                WHERE o.city = %s 
                AND d.city = %s 
                AND DATE(f.departure_datetime) = %s
            """
    with db_cur() as cursor:
        cursor.execute(query,(origin_city,destination_city, flight_date))
        db_flights = cursor.fetchall()
        processed_flights = []
        for flight in db_flights:
            departure_date, landing_date=utils.get_time_display(flight['Departure_datetime'], flight['duration'])
            flight_info = {'flight_id': flight['ID'],
                            'status': flight['status'],
                            'origin_code': flight['origin_code'],
                            'destination_code': flight['destination_code'],
                            'departure_time': departure_date,
                            'landing_time': landing_date,
                            'duration': f"{flight['duration']}h",
                            'price_economy': flight['Economy_price'],
                            'price_business': flight['Business_price'] if flight['Business_price'] else "N/A",
                            'has_business': True if flight['Business_price'] else False}
            processed_flights.append(flight_info)
        return render_template("choose_flight.html", flights=processed_flights, passengers=passengers)

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

@app.route("/select_seats/<flight_id>/<department_type>", methods=["GET", "POST"])
def select_seats(flight_id, department_type):
    occupied = utils.get_occupied_seats(flight_id, department_type)
    rows, cols = utils.get_department_dimensions(flight_id, department_type)
    if request.method == 'POST':
        selected_seat = request.form.get("selected_seat")
        if selected_seat:
            session['selected_seat'] = selected_seat
            return redirect(url_for('payment'))
    return render_template("select_seats.html",
                           rows=rows,
                           cols=cols,
                           occupied=occupied,
                           dept=department_type,
                           flight_id=flight_id)

# save_booking(session['email'], selected, flight_id) #האם ואיך צריכה להיות הפרדה בין לקוח רשום ללקוח ואיך ?
#         return (f"seats booked for {flight_id}")
#     return render_template("seats.html", rows = rows, cols = cols, flight_id = flight_id, occupied = occupied)

@app.route("/managers_log_in", methods=["GET", "POST"])
def managers_log_in():
    if request.method == "POST":
        manager_id = request.form.get("managers_ID")
        manager_pass = request.form.get("managers_password")
        with db_cur() as cursor:
            query = "SELECT id FROM manager WHERE id = %s AND password = %s"
            cursor.execute(query, (manager_id, manager_pass))
            manager = cursor.fetchone()
            if manager:
                session["managers_ID"] = manager_id
                return redirect("/managers_home_page")
            else:
                return render_template("managers_log_in.html", error="ID or Password incorrect")
    return render_template("managers_log_in.html")

@app.route("/managers_home_page", methods=["GET"])
def managers_home_page():
    if "managers_ID" not in session:
        return redirect("/managers_log_in")
    manager_id = session["managers_ID"]
    with db_cur() as cursor:
        query = "SELECT first_name FROM manager WHERE id = %s"
        cursor.execute(query, (manager_id,))
        result = cursor.fetchone()
        if result:
            try:
                manager_first_name = result['first_name']
            except KeyError:
                manager_first_name = result[0]
            return render_template("managers_home_page.html", name=manager_first_name)
    return redirect("/managers_log_in")

if __name__ == "__main__":
    app.run(debug=True)
