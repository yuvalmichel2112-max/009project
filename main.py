from flask import Flask, request, session, render_template
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import db_cur, get_airplane_dimensions
from contextlib import contextmanager

app = Flask(__name__)
Session(app)
@app.route("/", methods =["GET", "POST"])
def home_page():
    if request.method == "POST":
        session["registered_email"]=request.form.get("registered_email")
        session["registered_password"] = request.form.get("registered_password")
        return redirect("/flights")
    return render_template("home_page.html")

@app.route("/sign_up", methods = ["post", "GET"])
def sign_up():
    if request.method == "POST":
        session["first_name"]=request.form.get("first_name")
        session["last_name"] = request.form.get("last_name")
        session["date_of_birth"]=request.form.get("date_of_birth")
        session["registered_email"] = request.form.get("registered_email")
        session["passport_number"]=request.form.get("passport_number")
        session["phones_list"] = request.form.getlist("phones_list")
        session["date_of_registration"] = request.form.get("date_of_registration")
        session["registered_password"] = request.form.get("registered_password")
        return redirect("/flights")
    return render_template("sign_up.html")

@app.route("/flights", methods = ["GET"])
def show_flights():
    try:
        with db_cur() as cursor:
            query = "SELECT flight_id, origin_airport, destination_airport, departure_date, status FROM flights WHERE status = 'active'"
            cursor.execute(query)
            active_flights = cursor.fetchall()
        return render_template("flights.html",flights = active_flights)
    except mysql.connector.Error as err:
        return f"Error"

@app.route('/select.seats', methods = ["GET", "POST"])
def select_seats():
    rows, cols = get_airplane_dimensions()#פונקציה שבונה את מימד כל המחלקה






