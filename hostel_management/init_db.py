
import sqlite3, os
from datetime import datetime

def init_db(db_path="database.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Tables
    c.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('student','warden','admin')) NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT UNIQUE,
        status TEXT CHECK(status IN ('empty','booked')) DEFAULT 'empty',
        student_id INTEGER NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT CHECK(status IN ('paid','pending')) NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT CHECK(status IN ('pending','approved','rejected')) DEFAULT 'pending',
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        status TEXT CHECK(status IN ('open','closed')) DEFAULT 'open',
        reply TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0
    );
    """)
    # Seed Users
    users = [
        ("Rohit Student", "student1", "1234", "student"),
        ("Priya Student", "student2", "1234", "student"),
        ("Mr. Sharma", "warden", "1234", "warden"),
        ("Super Admin", "admin", "1234", "admin"),
    ]
    for name, username, password, role in users:
        try:
            c.execute("INSERT INTO users (name, username, password, role) VALUES (?,?,?,?)",
                      (name, username, password, role))
        except sqlite3.IntegrityError:
            pass
    # Seed Rooms
    for i in range(101, 111):
        room_no = str(i)
        try:
            c.execute("INSERT INTO rooms (room_no, status) VALUES (?, 'empty')", (room_no,))
        except sqlite3.IntegrityError:
            pass
    # Seed Fees (one paid example)
    c.execute("INSERT OR IGNORE INTO fees (id, student_id, amount, status, date) VALUES (1, 1, 5000, 'paid', ?)", 
              (datetime.now().strftime("%Y-%m-%d"),))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
