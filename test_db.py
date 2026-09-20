print("Testing Python...")
import sqlite3
print("SQLite imported successfully")
try:
    conn = sqlite3.connect('nexus.db')
    print("Connected to database successfully")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables found:", tables)
    conn.close()
except Exception as e:
    print("Error:", e)