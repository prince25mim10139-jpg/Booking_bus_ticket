# features.py
from db_config import get_conn, generate_ticket_no
from datetime import datetime
import os

# -------------- BUS CRUD ----------------
def add_bus(route: str, total_seats: int, price: int = 100, departure_time: str = None, arrival_time: str = None, description: str = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO buses (route, route_description, total_seats, seats_available, price, departure_time, arrival_time)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (route, description, total_seats, total_seats, price, departure_time, arrival_time))
        conn.commit()
        return True, "Bus added."
    except Exception as e:
        return False, f"Error adding bus: {e}"
    finally:
        conn.close()

def list_buses():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, route, total_seats, seats_available, price, departure_time, arrival_time FROM buses")
            return cur.fetchall()
    finally:
        conn.close()

def get_bus(bus_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, route, total_seats, seats_available, price, departure_time, arrival_time FROM buses WHERE id=%s", (bus_id,))
            return cur.fetchone()
    finally:
        conn.close()

def update_bus(bus_id: int, route: str = None, price: int = None, total_seats: int = None, departure_time: str = None, arrival_time: str = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if route is not None:
                cur.execute("UPDATE buses SET route=%s WHERE id=%s", (route, bus_id))
            if price is not None:
                cur.execute("UPDATE buses SET price=%s WHERE id=%s", (price, bus_id))
            if total_seats is not None:
                # Update total seats and recalc seats_available carefully
                cur.execute("SELECT total_seats, seats_available FROM buses WHERE id=%s", (bus_id,))
                r = cur.fetchone()
                if r:
                    old_total = r['total_seats']
                    old_avail = r['seats_available']
                    delta = total_seats - old_total
                    new_avail = old_avail + delta
                    if new_avail < 0:
                        return False, "Cannot reduce seats below already booked seats."
                    cur.execute("UPDATE buses SET total_seats=%s, seats_available=%s WHERE id=%s", (total_seats, new_avail, bus_id))
            if departure_time is not None:
                cur.execute("UPDATE buses SET departure_time=%s WHERE id=%s", (departure_time, bus_id))
            if arrival_time is not None:
                cur.execute("UPDATE buses SET arrival_time=%s WHERE id=%s", (arrival_time, bus_id))
        conn.commit()
        return True, "Bus updated."
    except Exception as e:
        return False, f"Error updating: {e}"
    finally:
        conn.close()

def delete_bus(bus_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM buses WHERE id=%s", (bus_id,))
        conn.commit()
        return True, "Bus deleted."
    except Exception as e:
        return False, f"Error deleting bus: {e}"
    finally:
        conn.close()


# ------------- SEARCH -------------------
def search_buses_by_route(term: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, route, total_seats, seats_available, price, departure_time, arrival_time FROM buses WHERE route LIKE %s", ('%' + term + '%',))
            return cur.fetchall()
    finally:
        conn.close()

def search_buses_advanced(route_term: str = None, min_seats_available: int = None, price_min: int = None, price_max: int = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = "SELECT id, route, total_seats, seats_available, price, departure_time, arrival_time FROM buses WHERE 1=1"
            params = []
            if route_term:
                sql += " AND route LIKE %s"; params.append('%' + route_term + '%')
            if min_seats_available is not None:
                sql += " AND seats_available >= %s"; params.append(min_seats_available)
            if price_min is not None:
                sql += " AND price >= %s"; params.append(price_min)
            if price_max is not None:
                sql += " AND price <= %s"; params.append(price_max)
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


# ------------- SEAT MAP ------------------
def booked_seats(bus_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT seat_no FROM tickets WHERE bus_id=%s AND status='ACTIVE'", (bus_id,))
            rows = cur.fetchall()
            return [r['seat_no'] for r in rows]
    finally:
        conn.close()

def pretty_print_seat_map(bus_id: int, per_row: int = 4):
    bus = get_bus(bus_id)
    if not bus:
        return False, "Bus not found."
    total = bus['total_seats']
    booked = set(booked_seats(bus_id))
    lines = []
    for i in range(1, total + 1):
        mark = "X" if i in booked else str(i)
        lines.append(f"[{mark}]")
        if i % per_row == 0:
            lines.append("\n")
    return True, "".join(lines)


# ------------- TICKETING -----------------
def _find_next_free_seat(bus_id: int):
    bus = get_bus(bus_id)
    if not bus:
        return None
    total = bus['total_seats']
    booked = set(booked_seats(bus_id))
    for s in range(1, total + 1):
        if s not in booked:
            return s
    return None

def create_ticket(user_id: int, bus_id: int, seat_no: int, travel_date: str = None, pay_from_wallet: bool = True):
    """
    seat_no == 0 => auto assign next free seat
    travel_date -> 'YYYY-MM-DD' or None
    pay_from_wallet -> deduct from user wallet if True
    Returns (ok, msg, ticket_info)
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT total_seats, seats_available, price FROM buses WHERE id=%s", (bus_id,))
            b = cur.fetchone()
            if not b:
                return False, "Bus not found.", None
            total_seats = b['total_seats']; seats_available = b['seats_available']; price = b['price']
            if seats_available <= 0:
                return False, "No seats available.", None
            if seat_no == 0:
                seat_no = _find_next_free_seat(bus_id)
                if seat_no is None:
                    return False, "No free seat available.", None
            if seat_no < 1 or seat_no > total_seats:
                return False, "Invalid seat number.", None
            # check already booked
            cur.execute("SELECT id FROM tickets WHERE bus_id=%s AND seat_no=%s AND status='ACTIVE'", (bus_id, seat_no))
            if cur.fetchone():
                return False, "Seat already taken.", None

            # payment via wallet
            if pay_from_wallet:
                cur.execute("SELECT wallet FROM users WHERE id=%s", (user_id,))
                r = cur.fetchone()
                wallet = r['wallet'] if r else 0
                if wallet < price:
                    return False, f"Insufficient wallet balance (₹{wallet}). Please add funds or set pay_from_wallet=False.", None
                # deduct
                cur.execute("UPDATE users SET wallet = wallet - %s WHERE id=%s", (price, user_id))

            ticket_no = generate_ticket_no()
            cur.execute("INSERT INTO tickets (ticket_no, user_id, bus_id, seat_no, price_paid, travel_date) VALUES (%s,%s,%s,%s,%s,%s)",
                        (ticket_no, user_id, bus_id, seat_no, price, travel_date))
            cur.execute("UPDATE buses SET seats_available = seats_available - 1 WHERE id=%s", (bus_id,))
        conn.commit()
        ticket_info = {"ticket_no": ticket_no, "user_id": user_id, "bus_id": bus_id, "seat_no": seat_no, "price": price, "travel_date": travel_date}
        return True, "Ticket booked successfully.", ticket_info
    except Exception as e:
        return False, f"Error creating ticket: {e}", None
    finally:
        conn.close()

def get_user_tickets(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.ticket_no, b.route, t.seat_no, t.price_paid AS price, t.status, t.booked_at, t.travel_date
                FROM tickets t JOIN buses b ON t.bus_id=b.id
                WHERE t.user_id=%s
                ORDER BY t.booked_at DESC
            """, (user_id,))
            return cur.fetchall()
    finally:
        conn.close()

def cancel_user_ticket(user_id: int, ticket_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT bus_id, price_paid, status FROM tickets WHERE id=%s AND user_id=%s", (ticket_id, user_id))
            r = cur.fetchone()
            if not r:
                return False, "Ticket not found.", None
            if r['status'] == 'CANCELLED':
                return False, "Ticket already cancelled.", None
            bus_id = r['bus_id']; price_paid = r['price_paid']
            # perform cancellation: mark ticket cancelled
            cur.execute("UPDATE tickets SET status='CANCELLED' WHERE id=%s", (ticket_id,))
            # refund policy: full refund to wallet (for simplicity)
            cur.execute("UPDATE users SET wallet = wallet + %s WHERE id=%s", (price_paid, user_id))
            # update seats_available
            cur.execute("UPDATE buses SET seats_available = seats_available + 1 WHERE id=%s", (bus_id,))
            # log history
            cur.execute("INSERT INTO ticket_history (ticket_id, action, note) VALUES (%s,%s,%s)", (ticket_id, "CANCELLED", "User cancelled — refunded to wallet"))
        conn.commit()
        return True, "Ticket cancelled and refunded to wallet."
    except Exception as e:
        return False, f"Error cancelling: {e}"
    finally:
        conn.close()


# ------------- ADMIN VIEWS & STATS --------------
def view_all_tickets():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.ticket_no, u.username, b.route, t.seat_no, t.price_paid, t.status, t.booked_at
                FROM tickets t
                JOIN users u ON t.user_id = u.id
                JOIN buses b ON t.bus_id = b.id
                ORDER BY t.booked_at DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def view_all_users():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, is_admin, wallet, created_at FROM users")
            return cur.fetchall()
    finally:
        conn.close()

def admin_stats():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total_users FROM users")
            total_users = cur.fetchone().get('total_users', 0)
            cur.execute("SELECT COUNT(*) AS total_buses FROM buses")
            total_buses = cur.fetchone().get('total_buses', 0)
            cur.execute("SELECT COUNT(*) AS total_tickets FROM tickets WHERE status='ACTIVE'")
            total_tickets = cur.fetchone().get('total_tickets', 0)
            cur.execute("SELECT IFNULL(SUM(price_paid),0) AS revenue FROM tickets WHERE status='ACTIVE'")
            revenue = cur.fetchone().get('revenue', 0)
            cur.execute("""
                SELECT b.route, COUNT(*) AS cnt
                FROM tickets t JOIN buses b ON t.bus_id=b.id
                WHERE t.status='ACTIVE'
                GROUP BY b.route ORDER BY cnt DESC LIMIT 1
            """)
            top = cur.fetchone()
            top_route = top['route'] if top else None
        return {"total_users": total_users, "total_buses": total_buses, "total_tickets": total_tickets, "revenue": revenue, "top_route": top_route}
    finally:
        conn.close()


# ------------- EXPORT TICKET (TEXT & PDF) --------------
def save_ticket_text(ticket_info: dict, folder: str = None):
    if folder is None:
        folder = os.path.join(os.getcwd(), "saved_tickets")
    os.makedirs(folder, exist_ok=True)
    tno = ticket_info.get("ticket_no")
    filename = f"ticket_{tno}.txt"
    path = os.path.join(folder, filename)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "------ BUS TICKET ------",
        f"Ticket No: {tno}",
        f"User ID: {ticket_info.get('user_id')}",
        f"Bus ID: {ticket_info.get('bus_id')}",
        f"Seat No: {ticket_info.get('seat_no')}",
        f"Price: ₹{ticket_info.get('price')}",
        f"Travel Date: {ticket_info.get('travel_date')}",
        f"Issued At: {now}",
        "------------------------"
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path

def save_ticket_pdf(ticket_info: dict, folder: str = None):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A5
    except Exception as e:
        return False, f"reportlab not installed: {e}"
    if folder is None:
        folder = os.path.join(os.getcwd(), "saved_tickets")
    os.makedirs(folder, exist_ok=True)
    tno = ticket_info.get("ticket_no")
    filename = f"ticket_{tno}.pdf"
    path = os.path.join(folder, filename)
    c = canvas.Canvas(path, pagesize=A5)
    width, height = A5
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 40, "BUS TICKET")
    c.setFont("Helvetica", 10)
    y = height - 70
    lines = [
        f"Ticket No: {ticket_info.get('ticket_no')}",
        f"User ID: {ticket_info.get('user_id')}",
        f"Bus ID: {ticket_info.get('bus_id')}",
        f"Seat No: {ticket_info.get('seat_no')}",
        f"Price: ₹{ticket_info.get('price')}",
        f"Travel Date: {ticket_info.get('travel_date')}",
        f"Issued At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    for line in lines:
        c.drawString(40, y, line)
        y -= 16
    c.line(30, y-6, width-30, y-6)
    c.save()
    return True, path