
import pymysql
import hashlib
import binascii
import uuid

import os
from datetime import datetime



DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"       
DB_PASS = "1234"       
DB_NAME = "bus_system" 





def get_conn(use_db=True):
    kwargs = dict(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    if use_db:
        kwargs['database'] = DB_NAME
    return pymysql.connect(**kwargs)


def init_db():
    """
    Resets/creates the database schema and inserts sample data.
    This drops old tables and recreates clean schema (Option A).
    """
    # Create database if doesn't exist
    conn0 = get_conn(use_db=False)
    try:
        with conn0.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn0.commit()
    finally:
        conn0.close()

    # Connect to DB and recreate schema (dropping old tables)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # drop tables if exist (reset)
            cur.execute("SET FOREIGN_KEY_CHECKS=0;")
            cur.execute("DROP TABLE IF EXISTS ticket_history;")
            cur.execute("DROP TABLE IF EXISTS tickets;")
            cur.execute("DROP TABLE IF EXISTS buses;")
            cur.execute("DROP TABLE IF EXISTS users;")
            cur.execute("SET FOREIGN_KEY_CHECKS=1;")

            # users

            cur.execute("""
                CREATE TABLE users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(256) NOT NULL,
                    salt VARCHAR(64) NOT NULL,
                    is_admin TINYINT DEFAULT 0,
                    wallet BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)

            # buses
            cur.execute("""
                CREATE TABLE buses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    route VARCHAR(255) NOT NULL,
                    route_description TEXT NULL,
                    total_seats INT NOT NULL,
                    seats_available INT NOT NULL,
                    price INT DEFAULT 100,
                    departure_time TIME NULL,
                    arrival_time TIME NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)

           
            cur.execute("""
                CREATE TABLE tickets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_no VARCHAR(64) NOT NULL UNIQUE,
                    user_id INT NOT NULL,
                    bus_id INT NOT NULL,
                    seat_no INT NOT NULL,
                    price_paid INT NOT NULL,
                    status ENUM('ACTIVE','CANCELLED') DEFAULT 'ACTIVE',
                    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    travel_date DATE NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (bus_id) REFERENCES buses(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
            """)

           
            cur.execute("""
                CREATE TABLE ticket_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_id INT NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    note TEXT,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
            """)

        conn.commit()
    finally:
        conn.close()

    
    create_default_admin_if_missing()
    insert_sample_buses_if_missing()



def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 150_000)
    return binascii.hexlify(pwdhash).decode('ascii'), binascii.hexlify(salt).decode('ascii')


def verify_password(stored_hash_hex: str, stored_salt_hex: str, provided_password: str) -> bool:
    salt = binascii.unhexlify(stored_salt_hex.encode('ascii'))
    new_hash, _ = hash_password(provided_password, salt)
    return new_hash == stored_hash_hex




def create_default_admin_if_missing():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1;")
            if cur.fetchone():
                return
           
            pwd_hash, salt = hash_password("admin123")
            cur.execute("INSERT INTO users (username, password_hash, salt, is_admin, wallet) VALUES (%s,%s,%s,1,%s)",
                        ("admin", pwd_hash, salt, 0))
        conn.commit()
        print("Default admin created -> username: admin password: admin123")
    finally:
        conn.close()


def insert_sample_buses_if_missing():
    samples = [
        ("Bhopal → Indore", "Express via NH46", 40, 40, 250, "06:00:00", "09:00:00"),
        ("Bhopal → Mumbai", "Overnight Volvo", 50, 50, 1200, "22:00:00", "08:00:00"),
        ("Delhi → Jaipur", "AC Deluxe", 35, 35, 350, "07:00:00", "11:00:00"),
        ("Mumbai → Pune", "Frequent", 45, 45, 300, "09:00:00", "11:30:00"),
        ("Hyderabad → Bangalore", "Comfort Coach", 40, 40, 700, "06:30:00", "11:00:00")
    ]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM buses;")
            r = cur.fetchone()
            if r and r.get('cnt', 0) > 0:
                return
            for route, desc, total, avail, price, dep, arr in samples:
                cur.execute("""
                    INSERT INTO buses (route, route_description, total_seats, seats_available, price, departure_time, arrival_time)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (route, desc, total, avail, price, dep, arr))
        conn.commit()
        print("Sample buses inserted.")
    finally:
        conn.close()



def generate_ticket_no():
    return "T" + uuid.uuid4().hex[:10].upper()