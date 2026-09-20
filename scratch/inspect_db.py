import sqlite3
import os

db_path = os.path.join(os.getcwd(), 'nexus.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print("Tables:")
for table in tables:
    print(f"  {table[0]}")

# For each table, get the schema and a few rows
for table in tables:
    table_name = table[0]
    print(f"\nTable: {table_name}")
    c.execute(f"PRAGMA table_info({table_name})")
    columns = c.fetchall()
    print("  Columns:")
    for col in columns:
        print(f"    {col[1]} ({col[2]})")
    
    # Get a few rows
    c.execute(f"SELECT * FROM {table_name} LIMIT 3")
    rows = c.fetchall()
    if rows:
        print("  Sample rows (up to 3):")
        for row in rows:
            print(f"    {row}")
    else:
        print("  No data")

conn.close()