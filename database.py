import os
import psycopg2
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, sslmode="require")
    else:
        return sqlite3.connect("curier_bot.db")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela utilizatori / curieri
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            role TEXT NOT NULL,
            phone TEXT,
            is_active INT DEFAULT 1,
            lang TEXT DEFAULT 'ro'
        );
    """)

    # Tabela comenzi
    pk_type = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS orders (
            id {pk_type},
            client_id BIGINT NOT NULL,
            details TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            courier_id BIGINT
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()


def save_or_update_user(user_id: int, role: str = 'client', phone: str = None, lang: str = 'ro'):
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute("""
            INSERT INTO users (user_id, role, phone, lang)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                phone = COALESCE(EXCLUDED.phone, users.phone),
                lang = EXCLUDED.lang;
        """, (user_id, role, phone, lang))
    else:
        cursor.execute("""
            INSERT INTO users (user_id, role, phone, lang)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                role = excluded.role,
                phone = COALESCE(excluded.phone, users.phone),
                lang = excluded.lang;
        """, (user_id, role, phone, lang))

    conn.commit()
    cursor.close()
    conn.close()


def set_user_language(user_id: int, lang: str):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"UPDATE users SET lang = {placeholder} WHERE user_id = {placeholder}", (lang, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT user_id, role, phone, is_active, lang FROM users WHERE user_id = {placeholder}", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def toggle_courier_status(user_id: int, new_status: int):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"UPDATE users SET is_active = {placeholder} WHERE user_id = {placeholder}", (new_status, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_active_couriers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, lang FROM users WHERE role = 'courier' AND is_active = 1")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def create_order(client_id: int, details: str):
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("INSERT INTO orders (client_id, details) VALUES (%s, %s) RETURNING id;", (client_id, details))
        order_id = cursor.fetchone()[0]
    else:
        cursor.execute("INSERT INTO orders (client_id, details) VALUES (?, ?);", (client_id, details))
        order_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return order_id


def count_active_orders_by_client(client_id: int) -> int:
    """Numără doar comenzile în derulare ('active' sau 'taken'). Comenzile 'completed' nu sunt incluse."""
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id = {placeholder} AND status IN ('active', 'taken')",
        (client_id,)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def cancel_order(order_id: int, client_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"UPDATE orders SET status = 'cancelled' WHERE id = {placeholder} AND client_id = {placeholder} AND status = 'active'",
        (order_id, client_id)
    )
    rows = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return rows > 0


def claim_order(order_id: int, courier_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    cursor.execute(f"SELECT status FROM orders WHERE id = {placeholder}", (order_id,))
    res = cursor.fetchone()
    if not res:
        cursor.close()
        conn.close()
        return False, 'not_found'

    current_status = res[0]
    if current_status != 'active':
        cursor.close()
        conn.close()
        return False, current_status

    cursor.execute(
        f"UPDATE orders SET status = 'taken', courier_id = {placeholder} WHERE id = {placeholder}",
        (courier_id, order_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True, 'taken'


def complete_order(order_id: int, user_id: int):
    """Marchează comanda ca 'completed' dacă este inițiată de clientul sau curierul ei."""
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"

    cursor.execute(f"SELECT client_id, courier_id, status FROM orders WHERE id = {placeholder}", (order_id,))
    res = cursor.fetchone()
    if not res:
        cursor.close()
        conn.close()
        return False, "not_found"

    client_id, courier_id, status = res[0], res[1], res[2]

    if status == 'completed':
        cursor.close()
        conn.close()
        return False, "already_completed"

    if user_id not in (client_id, courier_id):
        cursor.close()
        conn.close()
        return False, "unauthorized"

    cursor.execute(
        f"UPDATE orders SET status = 'completed' WHERE id = {placeholder}",
        (order_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True, "completed"


def get_order_details(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    placeholder = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT client_id, details, status, courier_id FROM orders WHERE id = {placeholder}", (order_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def get_admin_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'client'")
    total_clients = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'courier'")
    total_couriers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'courier' AND is_active = 1")
    active_couriers = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return {
        'total_users': total_users,
        'total_clients': total_clients,
        'total_couriers': total_couriers,
        'active_couriers': active_couriers
    }