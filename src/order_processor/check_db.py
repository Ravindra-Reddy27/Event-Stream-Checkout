import os
import pymysql
from dotenv import load_dotenv

# 1. Load the environment variables from the .env file
load_dotenv()

# 2. Fetch the credentials securely
DB_HOST = os.environ.get("DB_HOST")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_USER = os.environ.get("DB_USER")
DB_NAME = os.environ.get("DB_NAME")

# Quick sanity check to ensure the .env file is being read properly
if not DB_HOST or not DB_PASSWORD:
    print("❌ Error: Missing database credentials! Please check your .env file.")
    exit(1)

print(f"🔄 Connecting to the database at: {DB_HOST}...")

# 3. Establish the connection
try:
    conn = pymysql.connect(
        host=DB_HOST, 
        user=DB_USER, 
        password=DB_PASSWORD, 
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor # This makes the printed output look like nice JSON dictionaries
    )
    
    with conn.cursor() as cursor:
        print("\n=== 📦 ORDERS TABLE ===")
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
        if not orders:
            print("No orders found.")
        else:
            for order in orders:
                print(order)

        print("\n=== 📋 INVENTORY TABLE ===")
        cursor.execute("SELECT * FROM inventory")
        inventory = cursor.fetchall()
        if not inventory:
            print("No inventory found.")
        else:
            for item in inventory:
                print(item)

except pymysql.MySQLError as e:
    print(f"❌ Database connection failed: {e}")
finally:
    if 'conn' in locals() and conn.open:
        conn.close()
        print("\n🔒 Database connection closed.")