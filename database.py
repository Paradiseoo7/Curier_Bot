import os
import sqlite3
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')


def get_connection():
    if DATABASE_URL:
        # Conexiune PostgreSQL (pentru Render)
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        # Conexiune SQLite (pentru testare locală)
        return sqlite3.connect('bot_data.db')


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela utilizatori / curieri
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS users
                   (
                       user_id
                       BIGINT
                       PRIMARY
                       KEY,
                       role
                       TEXT
                       NOT
                       NULL,
                       phone
                       TEXT,
                       is_active
                       INT
                       DEFAULT
                       1,
                       lang
                       TEXT
                       DEFAULT
                       'ro'
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


def clear_all_orders():
    """Șterge toate comenzile existente pentru a reseta starea pe Render."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders;")
    conn.commit()
    cursor.close()
    conn.close()


def set_user_language(user_id: int, lang: str):
    conn = get_connection()
    cursor = conn.cursor()

    # Verificăm dacă utilizatorul există deja
    if DATABASE_URL:
        cursor.execute("""
                       INSERT INTO users (user_id, role, lang)
                       VALUES (%s, 'none', %s) ON CONFLICT (user_id) DO
                       UPDATE SET lang = EXCLUDED.lang;
                       """, (user_id, lang))
    else:
        cursor.execute("""
                       INSERT INTO users (user_id, role, lang)
                       VALUES (?, 'none', ?) ON CONFLICT(user_id) DO
                       UPDATE SET lang = excluded.lang;
                       """, (user_id, lang))

    conn.commit()
    cursor.close()
    conn.close()


def get_user_language(user_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT lang FROM users WHERE user_id = {ph}", (user_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row[0] if row else 'ro'


def register_user(user_id: int, role: str, phone: str = None):
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute("""
                       INSERT INTO users (user_id, role, phone, is_active)
                       VALUES (%s, %s, %s, 1) ON CONFLICT (user_id) 
            DO
                       UPDATE SET role = EXCLUDED.role, phone = EXCLUDED.phone, is_active = 1;
                       """, (user_id, role, phone))
    else:
        cursor.execute("""
                       INSERT INTO users (user_id, role, phone, is_active)
                       VALUES (?, ?, ?, 1) ON CONFLICT(user_id) 
            DO
                       UPDATE SET role = excluded.role, phone = excluded.phone, is_active = 1;
                       """, (user_id, role, phone))

    conn.commit()
    cursor.close()
    conn.close()


def get_user_role(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT role, is_active FROM users WHERE user_id = {ph}", (user_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None


def set_courier_status(user_id: int, is_active: int):
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"UPDATE users SET is_active = {ph} WHERE user_id = {ph}", (is_active, user_id))

    conn.commit()
    cursor.close()
    conn.close()


def create_order(client_id: int, details: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(
            "INSERT INTO orders (client_id, details, status) VALUES (%s, %s, 'active') RETURNING id;",
            (client_id, details)
        )
        order_id = cursor.fetchone()[0]
    else:
        cursor.execute(
            "INSERT INTO orders (client_id, details, status) VALUES (?, ?, 'active');",
            (client_id, details)
        )
        order_id = cursor.lastrowid

    conn.commit()
    cursor.close()
    conn.close()
    return order_id


def count_active_orders_by_client(client_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id = {ph} AND status IN ('active', 'taken');",
        (client_id,)
    )
    count = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return count


def get_active_couriers():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE role = 'courier' AND is_active = 1;")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return [row[0] for row in rows]


def assign_order(order_id: int, courier_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"UPDATE orders SET status = 'taken', courier_id = {ph} WHERE id = {ph} AND status = 'active';",
        (courier_id, order_id)
    )
    affected = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()
    return affected > 0


def complete_order(order_id: int, courier_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"UPDATE orders SET status = 'completed' WHERE id = {ph} AND courier_id = {ph} AND status = 'taken';",
        (order_id, courier_id)
    )
    affected = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()
    return affected > 0


def cancel_order(order_id: int, client_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(
        f"UPDATE orders SET status = 'cancelled' WHERE id = {ph} AND client_id = {ph} AND status = 'active';",
        (order_id, client_id)
    )
    affected = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()
    return affected > 0


def get_order_by_id(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"
    cursor.execute(f"SELECT id, client_id, details, status, courier_id FROM orders WHERE id = {ph};", (order_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row