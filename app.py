from flask import Flask, render_template, request, flash, redirect, session
import sqlite3
import bcrypt
import os
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
def init_db():
    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            amount REAL,
            description TEXT,
            transaction_type TEXT,
            transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect("/register")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return redirect("/register")

        has_letter = any(ch.isalpha() for ch in password)
        has_digit = any(ch.isdigit() for ch in password)
        has_symbol = any(not ch.isalnum() for ch in password)

        if not (has_letter and has_digit and has_symbol):
            flash("Password must contain at least one letter, one number and one special character.", "error")
            return redirect("/register")

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = sqlite3.connect("bank.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, mobile, password)
                VALUES (?, ?, ?, ?)
            """, (full_name, email, mobile, hashed_password))

            conn.commit()

        except sqlite3.IntegrityError:
            flash("Email already registered.", "error")
            conn.close()
            return redirect("/register")

        conn.close()

        flash("Account created successfully!", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("bank.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user[4].encode("utf-8")):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect("/dashboard")

        flash("Invalid email or password.", "error")
        return redirect("/login")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, full_name, email, mobile, balance FROM users WHERE id = ?",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    if user is None:
        session.clear()
        flash("User not found. Please login again.", "error")
        return redirect("/login")

    account_number = "VB" + str(user[0]).zfill(6)

    return render_template(
        "dashboard.html",
        account_number=account_number,
        name=user[1],
        email=user[2],
        mobile=user[3],
        balance=user[4]
    )


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    if request.method == "POST":
        amount = float(request.form["amount"])

        if amount <= 0:
            flash("Enter a valid amount.", "error")
            return redirect("/deposit")

        conn = sqlite3.connect("bank.db")
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, session["user_id"])
        )

        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, description, transaction_type)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], None, amount, "Self deposit", "Deposit"))

        conn.commit()
        conn.close()

        flash(f"₹{amount:.2f} deposited successfully.", "success")
        return redirect("/dashboard")

    return render_template("deposit.html")


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    if request.method == "POST":
        amount = float(request.form["amount"])

        if amount <= 0:
            flash("Enter a valid amount.", "error")
            return redirect("/withdraw")

        if amount > 10000:
            flash("Withdrawal limit is ₹10,000.00 per transaction.", "error")
            return redirect("/withdraw")

        conn = sqlite3.connect("bank.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT balance FROM users WHERE id = ?",
            (session["user_id"],)
        )

        user = cursor.fetchone()

        if user[0] < amount:
            conn.close()
            flash("Insufficient balance.", "error")
            return redirect("/withdraw")

        cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, session["user_id"])
        )

        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, description, transaction_type)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], None, amount, "Cash withdrawal", "Withdraw"))

        conn.commit()
        conn.close()

        flash(f"₹{amount:.2f} withdrawn successfully.", "success")
        return redirect("/dashboard")

    return render_template("withdraw.html")


@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    if request.method == "POST":
        receiver_account = request.form["receiver_account"]
        amount = float(request.form["amount"])
        description = request.form["description"]

        sender_id = session["user_id"]

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect("/transfer")

        try:
            receiver_id = int(receiver_account.replace("VB", ""))
        except ValueError:
            flash("Invalid receiver account number.", "error")
            return redirect("/transfer")

        if receiver_id == sender_id:
            flash("You cannot transfer money to your own account.", "error")
            return redirect("/transfer")

        conn = sqlite3.connect("bank.db")
        cursor = conn.cursor()

        cursor.execute("SELECT balance FROM users WHERE id = ?", (sender_id,))
        sender = cursor.fetchone()

        cursor.execute("SELECT id FROM users WHERE id = ?", (receiver_id,))
        receiver = cursor.fetchone()

        if receiver is None:
            conn.close()
            flash("Receiver account does not exist.", "error")
            return redirect("/transfer")

        if sender[0] < amount:
            conn.close()
            flash("Insufficient balance.", "error")
            return redirect("/transfer")

        cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, sender_id)
        )

        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, receiver_id)
        )

        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, description, transaction_type)
            VALUES (?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, amount, description, "Transfer"))

        conn.commit()
        conn.close()

        flash(f"₹{amount:.2f} transferred successfully.", "success")
        return redirect("/dashboard")

    return render_template("transfer.html")


@app.route("/history")
def history():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sender_id, receiver_id, amount, description, transaction_type, transaction_time
        FROM transactions
        WHERE sender_id = ? OR receiver_id = ?
        ORDER BY transaction_time DESC
    """, (user_id, user_id))

    rows = cursor.fetchall()
    conn.close()

    transactions = []

    for row in rows:
        sender_id, receiver_id, amount, description, transaction_type, transaction_time = row

        if transaction_type == "Deposit":
         tx_type = "Credited"
         account = "Self"

        elif transaction_type == "Withdraw":
         tx_type = "Debited"
         account = "Self"

        elif sender_id == user_id:
         tx_type = "Debited"
         account = "VB" + str(receiver_id).zfill(6)

        elif receiver_id == user_id:
         tx_type = "Credited"
         account = "VB" + str(sender_id).zfill(6)

        transactions.append({
            "type": tx_type,
            "account": account,
            "amount": amount,
            "description": description if description else "-",
            "time": transaction_time
        })

    return render_template("history.html", transactions=transactions)
@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect("/login")

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_name, email, mobile, balance
        FROM users
        WHERE id = ?
    """, (session["user_id"],))

    user = cursor.fetchone()
    conn.close()

    account_number = "VB" + str(user[0]).zfill(6)

    return render_template(
        "profile.html",
        account_number=account_number,
        name=user[1],
        email=user[2],
        mobile=user[3],
        balance=user[4]
    )

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect("/login")
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)