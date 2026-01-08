from flask import Flask, request, session, render_template
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import db_cur, get_department_dimensions, get_occupied_seats, save_booking, get_all_locations
from contextlib import contextmanager
from datetime import date

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
@app.route("/", methods =["GET", "POST"])
def home_page():
    if request.method == "POST":
        session["registered_email"]=request.form.get("registered_email")
        session["registered_password"] = request.form.get("registered_password")
        return redirect("/flights")
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
        session["first_name"]=request.form.get("first_name")
        session["last_name"] = request.form.get("last_name")
        session["date_of_birth"]=request.form.get("date_of_birth")
        session["registered_email"] = request.form.get("registered_email")
        session["passport_number"]=request.form.get("passport_number")
        session["phones_list"] = request.form.getlist("phones_list")
        session["date_of_registration"] = request.form.get("date_of_registration")
        session["registered_password"] = request.form.get("registered_password")
        query1 = "INSERT INTO customer(email, first_name, last_name) VALUES (%s, %s, %s)"
        query2 = "INSERT INTO registered_customer(customer_email, password, birth_date, registration_date, passport_number) VALUES (%s, %s, %s,%s, %s)"
        query3= "INSERT INTO customer_phone_number(customer_email, phone_number) VALUES (%s, %s)"
        with db_cur as cursor:
            cursor.execute(query1,(session["registered_email"],session["first_name"],session["last_name"]))
            cursor.execute(query2, (session["registered_email"],session["registered_password"],session["date_of_birth"], session["registered_password"],session["registered_password"] ))
            cursor.execute(query3, (session["registered_email"],session["phones_list"]))
        return redirect("/flights")
    return render_template("sign_up.html")

@app.route("/search_flights", methods = ["GET", "POST"])
def search_flights():
    today = date.today().strftime('%Y-%m-%d')
    if request.method == "POST":
        locations = get_all_locations()
        loc1 = request.form.get("loc1")
        loc2 = request.form.get("loc2")
        date_of_flights = request.form.get("date_of_flights")
        number_of_pass = request.form.get("number_of_pass")
        return redirect("/choose_flight")
    return render_template("search_flight.html")

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

# @app.route("/flight/<flight_id>/seats/<department_type>", methods = ["GET", "POST"]) ### לא יודעות מה לכתוב פה
# def select_seats():
#     flight_id = session.get['flight_id']
#     department_type = session.get['department_type']
#     occupied = get_occupied_seats(flight_id, department_type)
#     rows, cols = get_department_dimensions(flight_id, department_type)
#     if request.method == 'POST':
#         selected = request.form.getlist("seat_choice")

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

if __name__ == "__main__":
    app.run(debug=True)