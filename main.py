# main.py
from db_config import init_db
import login_register as auth
import features
import os, sys



init_db()

def clear():
    os.system('cls' if os.name=='nt' else 'clear')

def main_menu():
    while True:
        print("\n===== BUS TICKET SYSTEM =====")
        print("1. Register")
        print("2. Login")
        print("3. Exit")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            do_register()
        elif choice == "2":
            do_login()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")

def do_register():
    print("\n--- Register ---")
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    ok, msg = auth.register_user(username, password)
    print(msg)

def do_login():
    print("\n--- Login ---")
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    ok, user_id, role, msg = auth.login_user(username, password)
    print(msg)
    if ok:
        if role == "admin":
            admin_dashboard(user_id)
        else:
            user_dashboard(user_id)




def user_dashboard(user_id: int):
    while True:
        print("\n===== USER DASHBOARD =====")
        print("1. View Buses")
        print("2. Advanced Search")
        print("3. View Seat Map")
        print("4. Book Ticket")
        print("5. My Tickets")
        print("6. Cancel Ticket")
        print("7. Wallet")
        print("8. Change Password")
        print("9. Logout")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            show_buses()
        elif choice == "2":
            route_term = input("Route search term (blank skip): ").strip() or None
            min_seats = input("Min seats available (blank skip): ").strip()
            min_seats = int(min_seats) if min_seats else None
            pmin = input("Min price (blank skip): ").strip()
            pmin = int(pmin) if pmin else None
            pmax = input("Max price (blank skip): ").strip()
            pmax = int(pmax) if pmax else None
            results = features.search_buses_advanced(route_term, min_seats, pmin, pmax)
            if not results:
                print("No buses found.")
            else:
                for b in results:
                    print(f"ID:{b['id']} | {b['route']} | Seats:{b['total_seats']} | Avail:{b['seats_available']} | Price:₹{b['price']} | Dep:{b['departure_time']} Arr:{b['arrival_time']}")
        elif choice == "3":
            bid = int(input("Enter Bus ID: "))
            ok, out = features.pretty_print_seat_map(bid)
            print(out if ok else out)
        elif choice == "4":
            show_buses()
            bid = int(input("Enter Bus ID to book: "))
            seat = int(input("Enter seat number (0 for auto-assign): "))
            tdate = input("Travel date (YYYY-MM-DD) leave blank for none: ").strip() or None
            # check wallet
            wallet = auth.get_wallet(user_id)
            print(f"Your wallet balance: ₹{wallet}")
            pay_choice = input("Pay from wallet? (y/n): ").strip().lower()
            pay_from_wallet = (pay_choice == 'y')
            ok, msg, info = features.create_ticket(user_id, bid, seat, travel_date=tdate, pay_from_wallet=pay_from_wallet)
            print(msg)
            if ok and info:
                path_txt = features.save_ticket_text(info)
                print(f"Saved ticket text: {path_txt}")
                pdf_ok, pdf_res = features.save_ticket_pdf(info)
                if pdf_ok:
                    print(f"Saved ticket pdf: {pdf_res}")
                else:
                    print(f"PDF not created: {pdf_res}")
        elif choice == "5":
            tickets = features.get_user_tickets(user_id)
            if not tickets:
                print("No tickets found.")
            else:
                for t in tickets:
                    print(f"ID:{t['id']} | TNo:{t['ticket_no']} | Route:{t['route']} | Seat:{t['seat_no']} | Price:₹{t['price']} | Status:{t['status']} | At:{t['booked_at']} | Travel:{t['travel_date']}")
        elif choice == "6":
            tickets = features.get_user_tickets(user_id)
            if not tickets:
                print("No tickets to cancel.")
            else:
                for t in tickets:
                    print(f"ID:{t['id']} | TNo:{t['ticket_no']} | Route:{t['route']} | Seat:{t['seat_no']} | Status:{t['status']}")
                tid = int(input("Enter Ticket ID to cancel: "))
                ok, msg = features.cancel_user_ticket(user_id, tid)
                print(msg)
        elif choice == "7":
            print(f"Wallet balance: ₹{auth.get_wallet(user_id)}")
            sub = input("1:Add funds  2:Back  Enter: ").strip()
            if sub == "1":
                amt = int(input("Enter amount to add: "))
                ok, msg = auth.add_funds(user_id, amt)
                print(msg)
        elif choice == "8":
            old = input("Old password: ")
            new = input("New password: ")
            ok, msg = auth.change_password(user_id, old, new)
            print(msg)
        elif choice == "9":
            print("Logged out.")
            break
        else:
            print("Invalid choice.")


def show_buses():
    buses = features.list_buses()
    if not buses:
        print("No buses available.")
        return
    for b in buses:
        print(f"ID:{b['id']} | {b['route']} | Seats:{b['total_seats']} | Avail:{b['seats_available']} | Price:₹{b['price']} | Dep:{b['departure_time']} Arr:{b['arrival_time']}")




def admin_dashboard(admin_user_id: int):
    while True:
        print("\n===== ADMIN DASHBOARD =====")
        print("1. Add Bus")
        print("2. Update Bus")
        print("3. Delete Bus")
        print("4. View All Buses")
        print("5. View All Tickets")
        print("6. View All Users")
        print("7. View Stats")
        print("8. Logout")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            route = input("Route: ").strip()
            desc = input("Description (short): ").strip()
            seats = int(input("Total seats: ").strip())
            price = int(input("Price per ticket: ").strip())
            dep = input("Departure time (HH:MM) leave blank: ").strip() or None
            arr = input("Arrival time (HH:MM) leave blank: ").strip() or None
            ok, msg = features.add_bus(route, seats, price, departure_time=dep, arrival_time=arr, description=desc)
            print(msg)
        elif choice == "2":
            show_buses()
            bid = int(input("Bus ID to update: "))
            new_route = input("New route (blank no-change): ").strip() or None
            new_price_raw = input("New price (blank no-change): ").strip()
            new_price = int(new_price_raw) if new_price_raw else None
            tot_raw = input("New total seats (blank no-change): ").strip()
            tot = int(tot_raw) if tot_raw else None
            dep = input("New departure time (blank no-change): ").strip() or None
            arr = input("New arrival time (blank no-change): ").strip() or None
            ok, msg = features.update_bus(bid, route=new_route, price=new_price, total_seats=tot, departure_time=dep, arrival_time=arr)
            print(msg)
        elif choice == "3":
            show_buses()
            bid = int(input("Bus ID to delete: "))
            ok, msg = features.delete_bus(bid)
            print(msg)
        elif choice == "4":
            show_buses()
        elif choice == "5":
            tickets = features.view_all_tickets()
            if not tickets:
                print("No tickets.")
            else:
                for t in tickets:
                    print(f"ID:{t['id']} | TNo:{t['ticket_no']} | User:{t['username']} | Route:{t['route']} | Seat:{t['seat_no']} | Price:₹{t['price_paid']} | Status:{t['status']} | At:{t['booked_at']}")
        elif choice == "6":
            users = features.view_all_users()
            for u in users:
                role = "Admin" if u['is_admin'] else "User"
                print(f"ID:{u['id']} | {u['username']} | Role:{role} | Wallet:₹{u['wallet']} | Created:{u['created_at']}")
        elif choice == "7":
            s = features.admin_stats()
            print("=== STATS ===")
            print(f"Total users: {s['total_users']}")
            print(f"Total buses: {s['total_buses']}")
            print(f"Total active tickets: {s['total_tickets']}")
            print(f"Total revenue (active): ₹{s['revenue']}")
            print(f"Top route: {s['top_route']}")
        elif choice == "8":
            print("Admin logged out.")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main_menu()