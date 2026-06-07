import psycopg2
import os

try:
    conn = psycopg2.connect("postgres://postgres:Rev1704@localhost:5432/ai_driver_drowsiness")
    cur = conn.cursor()
    cur.execute("SELECT name, email, role FROM users LIMIT 10")
    users = cur.fetchall()
    print("Users found:")
    for user in users:
        print(user)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
