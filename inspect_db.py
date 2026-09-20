import sqlite3

def inspect_database():
    conn = sqlite3.connect('nexus.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("Database Tables:")
    print("=" * 50)
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        print("-" * 30)
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULL'} {'PRIMARY KEY' if col[5] else ''}")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  Rows: {count}")
        
        # Show first few rows if table is not too large
        if count > 0 and count < 10:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            for row in rows:
                print(f"  Row: {row}")
        elif count >= 10:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            print("  First 3 rows:")
            for row in rows:
                print(f"    {row}")
            print("  ...")
    
    conn.close()

if __name__ == "__main__":
    inspect_database()