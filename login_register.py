# login_register.py
from db_config import get_conn, hash_password, verify_password
from typing import Tuple


def register_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Creates a new user.
    Returns (ok, message)
    """
    if not username or not password:
        return False, "Username and password required."

    conn = get_conn()
    try:
        pwd_hash, salt = hash_password(password)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, salt, wallet) VALUES (%s, %s, %s, %s)",
                (username, pwd_hash, salt, 0)
            )
        conn.commit()
        return True, "Registration successful!"
    except Exception as e:
        
        if "Duplicate" in str(e) or "unique" in str(e).lower():
            return False, "Username already exists."
        return False, f"Registration failed: {e}"
    finally:
        conn.close()



def login_user(username: str, password: str):
    """
    Attempts login.
    Returns: (ok: bool, user_id: int|None, role: "admin"|"user"|None, message: str)
    """
    if not username or not password:
        return False, None, None, "Username and password required."

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, salt, is_admin FROM users WHERE username=%s LIMIT 1",
                (username,)
            )
            row = cur.fetchone()
            if not row:
                return False, None, None, "User not found."

            user_id = row['id']
            stored_hash = row['password_hash']
            stored_salt = row['salt']
            is_admin = bool(row.get('is_admin', 0))

            if verify_password(stored_hash, stored_salt, password):
                role = "admin" if is_admin else "user"
                return True, user_id, role, "Login successful!"
            else:
                return False, None, None, "Incorrect password."
    except Exception as e:
        return False, None, None, f"Login error: {e}"
    finally:
        conn.close()




def add_funds(user_id: int, amount: int) -> Tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be positive."
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET wallet = wallet + %s WHERE id=%s", (amount, user_id))
        conn.commit()
        return True, f"Added ₹{amount} to wallet."
    except Exception as e:
        return False, f"Add funds failed: {e}"
    finally:
        conn.close()

def get_wallet(user_id: int) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT wallet FROM users WHERE id=%s", (user_id,))
            r = cur.fetchone()
            return r['wallet'] if r and r.get('wallet') is not None else 0
    finally:
        conn.close()

def change_password(user_id: int, old_password: str, new_password: str):
    if not old_password or not new_password:
        return False, "Old and new passwords required."
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, salt FROM users WHERE id=%s", (user_id,))
            r = cur.fetchone()
            if not r:
                return False, "User not found."
            if not verify_password(r['password_hash'], r['salt'], old_password):
                return False, "Old password incorrect."
            new_hash, new_salt = hash_password(new_password)
            cur.execute("UPDATE users SET password_hash=%s, salt=%s WHERE id=%s", (new_hash, new_salt, user_id))
        conn.commit()
        return True, "Password changed."
    except Exception as e:
        return False, f"Password change failed: {e}"
    finally:
        conn.close()