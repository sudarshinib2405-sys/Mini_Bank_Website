import sqlite3

conn = sqlite3.connect("bank.db")
cursor = conn.cursor()

cursor.execute("SELECT id, full_name, email, mobile, balance FROM users")

users = cursor.fetchall()

print("\nXYZ Bank Demo Customers")
print("-" * 70)

for user in users:
    user_id, full_name, email, mobile, balance = user
    account_number = "VB" + str(user_id).zfill(6)

    print(f"Account Number : {account_number}")
    print(f"Name           : {full_name}")
    print(f"Email          : {email}")
    print(f"Mobile         : {mobile}")
    print(f"Balance        : ₹{balance:.2f}")
    print("-" * 70)

conn.close()