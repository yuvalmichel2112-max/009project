from flask import Flask, request, session, render_template, url_for
from datetime import datetime, timedelta
import utils
from flask_session import Session
from werkzeug.utils import redirect
import mysql.connector
from utils import db_cur, get_department_dimensions, get_occupied_seats, get_all_locations,get_reg_cus_info, add_guest_to_db
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import os
from contextlib import contextmanager
from datetime import date
from matplotlib.ticker import FuncFormatter

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


@app.route("/sign_up", methods=["POST", "GET"])
def sign_up():
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        date_of_birth = request.form.get("date_of_birth")
        registered_email = request.form.get("registered_email")
        passport_number = request.form.get("passport_number")
        registered_password = request.form.get("registered_password")
        phones_list = request.form.getlist("phones_list")
        registration_date = date.today().strftime('%Y-%m-%d')
        with db_cur() as cursor:
            cursor.execute("SELECT * FROM Registered_customer WHERE Customer_Email=%s", (registered_email,))
            if cursor.fetchone():
                return render_template('sign_up.html', error="Email already registered")
            query1 = "INSERT INTO Customer(Email, First_name, Last_name) VALUES (%s, %s, %s)"
            cursor.execute(query1, (registered_email, first_name, last_name))
            query2 = """INSERT INTO Registered_customer(Customer_Email, Password, Birth_date, Registration_date, Passport_number) 
                        VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query2,
                           (registered_email, registered_password, date_of_birth, registration_date, passport_number))
            query3 = "INSERT INTO Customer_phone_number(Customer_Email, Phone_number) VALUES (%s, %s)"
            for phone in phones_list:
                if phone.strip():  # מוודא שהטלפון לא ריק
                    cursor.execute(query3, (registered_email, phone))
        session["customer_email"] = registered_email
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

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home_page"))


@app.route('/booking_management')
def booking_management():
    # בדיקה האם המשתמש מחובר
    customer_email = session.get('customer_email')
    if not customer_email:
        return redirect(url_for('home_page'))

    now = datetime.now()

    # השאילתה המתוקנת עם GROUP BY מלא לפי חוקי ONLY_FULL_GROUP_BY
    query = """
    SELECT b.ID as booking_id, b.Booking_date, 
           o.City as origin_city, d.City as destination_city,
           f.Departure_datetime as dep_time,
           r.Duration,
           COUNT(t.ID) as num_tickets,
           SUM(t.Price) as total_price
    FROM Booking b
    JOIN Ticket t ON b.ID = t.Booking_ID
    JOIN Flight f ON t.Flight_ID = f.ID
    JOIN Flight_Route r ON f.Flight_Route_origin_Airport_Code = r.origin_Airport_Code 
                       AND f.Flight_Route_destination_Airport_Code = r.destination_Airport_Code
    JOIN Airport o ON r.origin_Airport_Code = o.Code
    JOIN Airport d ON r.destination_Airport_Code = d.Code
    WHERE b.Customer_Email = %s 
      AND b.Status = 'Active'
      AND f.Departure_datetime >= %s
    GROUP BY b.ID, b.Booking_date, o.City, d.City, f.Departure_datetime, r.Duration
    ORDER BY f.Departure_datetime ASC
    """

    with db_cur() as cursor:
        cursor.execute(query, (customer_email, now))
        results = cursor.fetchall()

        # שימוש במפתחות Dict כפי שמוגדר ב-Cursor שלכם
        for b in results:
            b['landing_time'] = b['dep_time'] + timedelta(hours=float(b['Duration']))

    return render_template('booking_management.html', bookings=results)

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


@app.route('/report1')
def report1_page():
    sql_query = """
    SELECT (total_sold*1.0/total_capacity)*100 as global_occupancy_percentage
    FROM 
    (SELECT 
    (SELECT COUNT(t.ID) FROM ticket as t JOIN booking as b ON t.Booking_ID = b.ID JOIN flight as f ON t.Flight_ID = f.ID 
    WHERE f.status = 'completed' AND b.Status = 'completed') as total_sold,
    (SELECT SUM(d.Number_of_rows*d.Number_of_columns) FROM flight as f JOIN department as d ON f.Airplane_ID = d.Airplane_ID
    WHERE f.status = 'completed') as total_capacity) as stats ;
    """
    occupancy_rate = 0
    with db_cur() as cursor:
        cursor.execute(sql_query)
        result = cursor.fetchone()
        if result and result['global_occupancy_percentage'] is not None:
            occupancy_rate = float(result['global_occupancy_percentage'])
    empty_rate = 100 - occupancy_rate
    values = [occupancy_rate, empty_rate]
    labels = ['Occupied', 'Empty']
    colors = ['#FF6B00', '#2E0249']
    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=labels, colors=colors, startangle=90, counterclock=False,
            wedgeprops={'width': 0.3, 'edgecolor': 'white'})
    plt.text(0, 0, f'{occupancy_rate:.1f}%', ha='center', va='center', fontsize=20, fontweight='bold')
    plt.title('Global Flight Occupancy', fontsize=16)
    image_filename = 'occupancy_report.png'
    image_path = f'static/images/{image_filename}'
    plt.savefig(image_path, transparent=True, bbox_inches='tight')
    plt.close()
    return render_template('report1.html',
                           graph_image=f'images/{image_filename}',
                           percentage=occupancy_rate)

@app.route('/report2')
def report2_page():
    sql_query = """
    SELECT a.size as airplane_size, a.Manufactorer as manufactorer, d.type as department_type, SUM(t.price) as total_revenue
    FROM ticket as t 
    JOIN flight as f ON t.Flight_ID = f.ID 
    JOIN booking as b ON t.Booking_ID = b.ID 
    JOIN airplane as a ON f.Airplane_ID = a.ID 
    JOIN department as d ON d.Airplane_ID = a.ID
    WHERE f.status <> "cancelled" AND (b.status = "completed" OR b.Status = "active")
    GROUP BY a.size, a.Manufactorer, d.type;
    """

    with db_cur() as cursor:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = ['airplane_size', 'manufactorer', 'department_type', 'total_revenue']
        df = pd.DataFrame(results, columns=columns)

    if df.empty:
        return "No data found for report 2"

    df['total_revenue'] = df['total_revenue'].astype(float)
    df['Plane_Type'] = df['manufactorer'] + ' ' + df['airplane_size'].astype(str)

    pivot_df = df.pivot_table(index='Plane_Type', columns='department_type', values='total_revenue', fill_value=0)

    plt.figure(figsize=(10, 6))
    pivot_df.plot(kind='bar', stacked=True, ax=plt.gca())

    plt.title('Revenue Analysis by Airplane Type')
    plt.xlabel('Airplane Type')
    plt.ylabel('Revenue')
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend(title='Department')
    plt.tight_layout()

    image_filename = 'revenue_report.png'
    plt.savefig(f'static/images/{image_filename}')
    plt.close()

    return render_template('report2.html', graph_image=f'images/{image_filename}')

@app.route('/report3')
def report3_page():
    sql_query = """
    SELECT first_name, last_name, employee_role, 
           SUM(CASE WHEN duration > 6 THEN duration ELSE 0 END) as long_flight_hours,
           SUM(CASE WHEN duration <= 6 THEN duration ELSE 0 END) as short_flight_hours 
    FROM 
    (SELECT p.first_name as first_name, p.last_name as last_name , "pilot" as employee_role, r.Duration
    FROM pilot as p JOIN pilot_in_flight as pif ON p.ID = pif.Pilot_ID
    JOIN flight as f ON pif.Flight_ID = f.ID JOIN flight_route as r ON r.origin_Airport_Code = f.Flight_Route_origin_Airport_Code
    AND r.destination_Airport_Code = f.Flight_Route_destination_Airport_Code
    WHERE f.status <> "cancelled" 
    UNION ALL 
    SELECT fa.first_name as first_name, fa.last_name as last_name, "flight attendant" as employee_role, r.Duration
    FROM flight_attendant as fa JOIN flight_attendant_in_flight as fif ON fa.ID = fif.Flight_attendant_ID
    JOIN flight as f ON fif.Flight_ID = f.ID JOIN flight_route as r ON r.origin_Airport_Code = f.Flight_Route_origin_Airport_Code
    AND r.destination_Airport_Code = f.Flight_Route_destination_Airport_Code
    WHERE f.status <> "cancelled") as employee_data
    GROUP BY first_name, last_name, employee_role
    ORDER BY employee_role ; 
    """
    with db_cur() as cursor:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = ['first_name', 'last_name', 'employee_role', 'long_flight_hours', 'short_flight_hours']
        df = pd.DataFrame(results, columns=columns)
    if df.empty:
        return "No data found for report 3"

    df['Full_Label'] = df['first_name'] + ' ' + df['last_name'] + ' (' + df['employee_role'] + ')'
    df['short_flight_hours'] = df['short_flight_hours'].astype(float)
    df['long_flight_hours'] = df['long_flight_hours'].astype(float)
    plt.figure(figsize=(10, 8))
    plt.barh(df['Full_Label'], df['short_flight_hours'], label='Short Flights (<=6h)', color='#3498db')
    plt.barh(df['Full_Label'], df['long_flight_hours'], left=df['short_flight_hours'], label='Long Flights (>6h)',
             color='#e67e22')
    plt.xlabel('Total Flight Hours')
    plt.title('Employee Flight Hours Analysis')
    plt.legend()
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    image_filename = 'employee_hours_report.png'
    plt.savefig(f'static/images/{image_filename}', bbox_inches='tight')
    plt.close()
    return render_template('report3.html', graph_image=f'images/{image_filename}')

@app.route('/report4')
def report4_page():
    sql_query = """
    SELECT booking_year, booking_month, CONCAT(ROUND((cancelled_bookings / total_bookings) * 100, 2), '%') as cancellation_rate
    FROM 
    (SELECT YEAR(booking_date) as booking_year, MONTH(booking_date) as booking_month, 
    SUM(CASE WHEN booking.status = "customer cancellation" THEN 1 ELSE 0 END) as cancelled_bookings, COUNT(*) as total_bookings 
    FROM booking GROUP BY YEAR(booking_date), MONTH(Booking_date)) as monthly_stats 
    ORDER BY booking_year DESC, booking_month DESC ; 
    """
    with db_cur() as cursor:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = ['booking_year', 'booking_month', 'cancellation_rate']
        df = pd.DataFrame(results, columns=columns)
    if df.empty:
        return "No data found for report 4"
    df['rate_numeric'] = df['cancellation_rate'].astype(str).str.replace('%', '').astype(float)
    df['Date_Label'] = df['booking_year'].astype(str) + '-' + df['booking_month'].astype(str).str.zfill(2)
    df = df.sort_values('Date_Label')
    plt.figure(figsize=(10, 6))
    plt.plot(df['Date_Label'], df['rate_numeric'], marker='o', linestyle='-', color='#e74c3c', linewidth=2)
    plt.title('Monthly Cancellation Rate Trend')
    plt.xlabel('Month')
    plt.ylabel('Cancellation Rate (%)')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, loc: "{:.0f}%".format(x)))
    image_filename = 'cancellation_report.png'
    plt.savefig(f'static/images/{image_filename}', bbox_inches='tight')
    plt.close()
    return render_template('report4.html', graph_image=f'images/{image_filename}')

@app.route('/report5')
def report5_page():
    sql_query = """
    SELECT a.City, COUNT(f.ID) as total_flights
    FROM Flight as f
    JOIN Airport as a ON f.Flight_Route_destination_Airport_Code = a.Code
    WHERE f.status <> 'cancelled'
    GROUP BY a.City
    ORDER BY total_flights DESC
    LIMIT 3;
    """
    destinations_data = []
    with db_cur() as cursor:
        cursor.execute(sql_query)
        results = cursor.fetchall()

        for i, row in enumerate(results):
            destinations_data.append({
                'city': row['City'],
                'flights': row['total_flights'],
                'rank': i + 1
            })
    return render_template('report5.html', destinations=destinations_data)

if __name__ == "__main__":
    app.run(debug=True)
