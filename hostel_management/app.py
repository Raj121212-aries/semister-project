
from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "hostel_secret"

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(role=None):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Access denied")
                return redirect(url_for(f"{session.get('role')}_dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        role = request.form["role"].strip()
        with get_db() as conn:
            cur = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?",
                               (username, password, role))
            user = cur.fetchone()
        if user:
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome {user['name']}!")
            return redirect(url_for(f"{role}_dashboard"))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- STUDENT ----------------
@app.route("/student")
@login_required("student")
def student_dashboard():
    return render_template("student.html")

@app.route("/student/rooms", methods=["GET", "POST"])
@login_required("student")
def student_rooms():
    uid = session["user_id"]
    with get_db() as conn:
        if request.method == "POST":
            room_id = request.form.get("room_id")
            # Book only if empty and student has no room
            has_room = conn.execute("SELECT id FROM rooms WHERE student_id=?", (uid,)).fetchone()
            status = conn.execute("SELECT status FROM rooms WHERE id=?", (room_id,)).fetchone()
            if has_room:
                flash("You already have a room.")
            elif status and status["status"] == "empty":
                conn.execute("UPDATE rooms SET status='booked', student_id=? WHERE id=?", (uid, room_id))
                conn.commit()
                flash("Room booked successfully!")
            else:
                flash("Room not available.")
        empty_rooms = conn.execute("SELECT * FROM rooms WHERE status='empty'").fetchall()
        my_room = conn.execute("SELECT * FROM rooms WHERE student_id=?", (uid,)).fetchone()
    return render_template("rooms.html", empty_rooms=empty_rooms, my_room=my_room, role="student")

@app.route("/student/fees", methods=["GET","POST"])
@login_required("student")
def student_fees():
    uid = session["user_id"]
    with get_db() as conn:
        if request.method == "POST":
            amount = float(request.form.get("amount", "0") or "0")
            conn.execute("INSERT INTO fees (student_id, amount, status, date) VALUES (?,?, 'paid', ?)",
                         (uid, amount, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            flash("Fee payment marked as PAID (demo).")
        my_fees = conn.execute("SELECT * FROM fees WHERE student_id=? ORDER BY date DESC", (uid,)).fetchall()
    return render_template("fees.html", fees=my_fees, role="student")

@app.route("/student/leaves", methods=["GET","POST"])
@login_required("student")
def student_leaves():
    uid = session["user_id"]
    with get_db() as conn:
        if request.method == "POST":
            reason = request.form["reason"].strip()
            conn.execute("INSERT INTO leave_requests (student_id, reason, status) VALUES (?, ?, 'pending')",
                         (uid, reason))
            conn.commit()
            flash("Leave request submitted.")
        my_leaves = conn.execute("""
            SELECT lr.*, u.name as student_name
            FROM leave_requests lr
            JOIN users u ON u.id = lr.student_id
            WHERE student_id=? ORDER BY id DESC
        """, (uid,)).fetchall()
    return render_template("leaves.html", leaves=my_leaves, role="student")

@app.route("/student/complaints", methods=["GET","POST"])
@login_required("student")
def student_complaints():
    uid = session["user_id"]
    with get_db() as conn:
        if request.method == "POST":
            desc = request.form["description"].strip()
            conn.execute("INSERT INTO complaints (student_id, description, status) VALUES (?, ?, 'open')",
                         (uid, desc))
            conn.commit()
            flash("Complaint submitted.")
        my_complaints = conn.execute("""
            SELECT c.*, u.name as student_name
            FROM complaints c
            JOIN users u ON u.id = c.student_id
            WHERE student_id=? ORDER BY id DESC
        """, (uid,)).fetchall()
    return render_template("complaints.html", complaints=my_complaints, role="student")

# ---------------- WARDEN ----------------
@app.route("/warden")
@login_required("warden")
def warden_dashboard():
    return render_template("warden.html")

@app.route("/warden/allocate", methods=["GET","POST"])
@login_required("warden")
def warden_allocate():
    with get_db() as conn:
        if request.method == "POST":
            room_id = request.form["room_id"]
            student_id = request.form["student_id"]
            # free existing assignment if any
            conn.execute("UPDATE rooms SET status='empty', student_id=NULL WHERE student_id=?", (student_id,))
            # allocate new
            status = conn.execute("SELECT status FROM rooms WHERE id=?", (room_id,)).fetchone()
            if status and status["status"] == "empty":
                conn.execute("UPDATE rooms SET status='booked', student_id=? WHERE id=?", (student_id, room_id))
                conn.commit()
                flash("Room allocated.")
            else:
                flash("Selected room is not empty.")
        students = conn.execute("SELECT id, name FROM users WHERE role='student'").fetchall()
        empty_rooms = conn.execute("SELECT * FROM rooms WHERE status='empty'").fetchall()
        occupied = conn.execute("""
            SELECT r.id, r.room_no, u.name as student_name, u.id as student_id
            FROM rooms r LEFT JOIN users u ON u.id = r.student_id
            WHERE r.status='booked'
        """).fetchall()
    return render_template("rooms.html", empty_rooms=empty_rooms, occupied=occupied, students=students, role="warden")

@app.route("/warden/fees")
@login_required("warden")
def warden_fees():
    with get_db() as conn:
        fees = conn.execute("""
            SELECT f.*, u.name as student_name FROM fees f
            JOIN users u ON u.id = f.student_id
            ORDER BY date DESC
        """).fetchall()
        # unpaid students (no 'paid' record this month)
        month_prefix = datetime.now().strftime("%Y-%m")
        paid_ids = {row["student_id"] for row in conn.execute(
            "SELECT DISTINCT student_id FROM fees WHERE date LIKE ? AND status='paid'",
            (f"{month_prefix}%",)).fetchall()}
        students = conn.execute("SELECT id, name FROM users WHERE role='student'").fetchall()
        pending = [s for s in students if s["id"] not in paid_ids]
    return render_template("fees.html", fees=fees, pending=pending, role="warden")

@app.route("/warden/leaves", methods=["GET","POST"])
@login_required("warden")
def warden_leaves():
    with get_db() as conn:
        if request.method == "POST":
            leave_id = request.form["leave_id"]
            action = request.form["action"]
            if action in ("approved", "rejected"):
                conn.execute("UPDATE leave_requests SET status=? WHERE id=?", (action, leave_id))
                conn.commit()
                flash(f"Leave {action}.")
        leaves = conn.execute("""
            SELECT lr.*, u.name as student_name
            FROM leave_requests lr
            JOIN users u ON u.id = lr.student_id
            ORDER BY lr.id DESC
        """).fetchall()
    return render_template("leaves.html", leaves=leaves, role="warden")

@app.route("/warden/complaints", methods=["GET","POST"])
@login_required("warden")
def warden_complaints():
    with get_db() as conn:
        if request.method == "POST":
            comp_id = request.form["complaint_id"]
            reply = request.form.get("reply","").strip()
            action = request.form.get("action")
            if action == "close":
                conn.execute("UPDATE complaints SET status='closed', reply=? WHERE id=?", (reply, comp_id))
                conn.commit()
                flash("Complaint closed.")
        complaints = conn.execute("""
            SELECT c.*, u.name as student_name
            FROM complaints c
            JOIN users u ON u.id = c.student_id
            ORDER BY c.id DESC
        """).fetchall()
    return render_template("complaints.html", complaints=complaints, role="warden")

@app.route("/warden/inventory", methods=["GET","POST"])
@login_required("warden")
def warden_inventory():
    with get_db() as conn:
        if request.method == "POST":
            name = request.form["name"].strip()
            qty = int(request.form["quantity"])
            conn.execute("INSERT INTO inventory (name, quantity) VALUES (?,?)", (name, qty))
            conn.commit()
            flash("Item added.")
        items = conn.execute("SELECT * FROM inventory ORDER BY id DESC").fetchall()
    return render_template("inventory.html", items=items)

# ---------------- ADMIN ----------------
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    return render_template("admin.html")

@app.route("/admin/users", methods=["GET","POST"])
@login_required("admin")
def admin_users():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form["action"]
            if action == "add":
                name = request.form["name"].strip()
                username = request.form["username"].strip()
                password = request.form["password"].strip()
                role = request.form["role"]
                try:
                    conn.execute("INSERT INTO users (name, username, password, role) VALUES (?,?,?,?)",
                                 (name, username, password, role))
                    conn.commit()
                    flash("User added.")
                except sqlite3.IntegrityError:
                    flash("Username already exists.")
            elif action == "delete":
                uid = request.form["user_id"]
                if uid == str(session["user_id"]):
                    flash("Cannot delete yourself.")
                else:
                    conn.execute("DELETE FROM users WHERE id=?", (uid,))
                    conn.commit()
                    flash("User deleted.")
        users = conn.execute("SELECT * FROM users ORDER BY role, name").fetchall()
    return render_template("users.html", users=users)

@app.route("/admin/reports")
@login_required("admin")
def admin_reports():
    with get_db() as conn:
        total_rooms = conn.execute("SELECT COUNT(*) as c FROM rooms").fetchone()["c"]
        booked_rooms = conn.execute("SELECT COUNT(*) as c FROM rooms WHERE status='booked'").fetchone()["c"]
        total_students = conn.execute("SELECT COUNT(*) as c FROM users WHERE role='student'").fetchone()["c"]
        total_fees = conn.execute("SELECT IFNULL(SUM(amount),0) as s FROM fees WHERE status='paid'").fetchone()["s"]
        open_complaints = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE status='open'").fetchone()["c"]
    metrics = {
        "total_rooms": total_rooms,
        "booked_rooms": booked_rooms,
        "available_rooms": total_rooms - booked_rooms,
        "total_students": total_students,
        "fees_collected": total_fees,
        "open_complaints": open_complaints
    }
    return render_template("reports.html", metrics=metrics)

# ------------- Utilities -------------
@app.context_processor
def inject_now():
    return {"now": datetime.now()}

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        from init_db import init_db
        init_db(DB_PATH)
    app.run(debug=True)
