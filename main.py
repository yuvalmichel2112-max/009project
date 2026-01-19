from flask import Flask, request, session, render_template, url_for
from datetime import datetime, timedelta
import utils
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import db_cur, get_department_dimensions, get_occupied_seats, get_all_locations,get_reg_cus_info, add_guest_to_db

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
    if not request.args.get('origin_city'):
        return redirect(url_for('search_flights'))
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
                AND DATE(f.departure_datetime) = %s"""
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
        return render_template("choose_flight.html",
                               flights=processed_flights,
                               passengers=passengers)

@app.route('/select_seats/<int:flight_id>/<department_type>', methods=['GET', 'POST'])
def select_seats(flight_id, department_type):
    price_from_url = request.args.get('price')
    if price_from_url:
        session['ticket_price'] = price_from_url
    if request.method == 'POST':
        selected_seats = request.form.getlist('seat_choice')
        session['selected_seats'] = selected_seats
        session['flight_id'] = flight_id
        session['department_type'] = department_type
        return redirect(url_for('details_for_customer'))
    num_passengers = request.args.get('passengers', default=1, type=int)
    rows, cols = get_department_dimensions(flight_id, department_type)
    occupied = get_occupied_seats(flight_id, department_type)
    return render_template('seats.html',
                           flight_id=flight_id,
                           department_type=department_type,
                           rows=rows,
                           cols=cols,
                           occupied=occupied,
                           num_passengers=num_passengers)

@app.route("/details_for_customer")
def details_for_customer():
    if 'selected_seats' not in session:
        return redirect(url_for('search_flights'))
    customer_email = session.get("customer_email")
    customer_info = None
    if customer_email:
        customer_info = get_reg_cus_info(customer_email)
    return render_template("details_for_customer.html", customer=customer_info)

@app.route('/submit-booking', methods=['POST'])
def submit_booking():
    if 'flight_id' not in session:
        return redirect(url_for('search_flights'))
    f_name = request.form.get('first_name')
    l_name = request.form.get('last_name')
    email = request.form.get('email')
    passport_number = request.form.get('passport_number')
    birth_date = request.form.get('birth_date')
    phones = request.form.getlist('phones_list')
    session['booking_temp_data'] = {'first_name': f_name,
                                    'last_name': l_name,
                                    'email': email,
                                    'passport_number': passport_number,
                                    'birth_date': birth_date,
                                    'phones': phones}
    if not session.get('customer_email'):
        add_guest_to_db(f_name, l_name, email, phones)
    return redirect(url_for('booking_summary'))

@app.route('/booking_summary')
def booking_summary():
    if 'selected_seats' not in session or 'booking_temp_data' not in session:
        return redirect(url_for('search_flights'))
    passenger = session.get('booking_temp_data')
    raw_seats = session.get('selected_seats', [])
    flight_id = session.get('flight_id')
    dept_type = session.get('department_type')
    ticket_price = session.get('ticket_price')
    try:
        price_val = float(ticket_price)
    except (ValueError, TypeError):
        price_val = 0.0
    total_amount = price_val * len(raw_seats)
    booking_id = utils.generate_unique_id('booking', 'ID')
    tickets = []
    for seat_str in raw_seats:
        ticket_id = utils.generate_unique_id('ticket', 'ID')
        row_col = seat_str.split('-')
        tickets.append({
            'ticket_id': ticket_id,
            'booking_id': booking_id,
            'flight_id': flight_id,
            'seat': f"Row {row_col[0]}, Seat {row_col[1]}",
            'class': dept_type,
            'price': price_val})
    session['final_tickets'] = tickets
    session['final_booking_id'] = booking_id
    session['total_order_amount'] = total_amount
    return render_template('booking_summary.html', tickets=tickets, passenger=passenger, total_amount=total_amount)


@app.route('/final_confirm', methods=['POST'])
def final_confirm():
    tickets = session.get('final_tickets')
    booking_id = session.get('final_booking_id')
    passenger = session.get('booking_temp_data')
    if not tickets or not booking_id or not passenger:
        return redirect(url_for('search_flights'))
    now = datetime.now()
    booking_time_display = now.strftime("%d/%m/%Y %H:%M")
    db_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db_cur() as cursor:
            query_booking = """INSERT INTO booking (ID, Customer_Email, Booking_date, Status)
                               VALUES (%s, %s, %s, %s)"""
            cursor.execute(query_booking, (booking_id, passenger['email'], db_timestamp, 'Active'))
            query_ticket = """INSERT INTO ticket (ID, Booking_ID, Flight_ID, Seat_row, Seat_col, Price, Department_type)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)"""

            for t in tickets:
                row = t['seat'].split('Row ')[1].split(',')[0]
                col = t['seat'].split('Seat ')[1]

                cursor.execute(query_ticket, (t['ticket_id'], booking_id, t['flight_id'],
                                              row, col, t['price'], t['class']))
        session.pop('final_tickets', None)
        session.pop('selected_seats', None)
        return render_template('final_confirm.html',
                               booking_id=booking_id,
                               name=passenger['first_name'],
                               booking_time=booking_time_display)
    except Exception as e:
        print(f"Database Error: {e}")
        return render_template('booking_summary.html',
                               error=f"Database error: {str(e)}",
                               tickets=tickets,
                               passenger=passenger)

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
