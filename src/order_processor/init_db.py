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
SQL_FILE_PATH = os.environ.get("SQL_FILE_PATH")

# Quick sanity check to ensure variables are loaded
if not DB_HOST or not DB_PASSWORD or not SQL_FILE_PATH:
    print("❌ Error: Missing credentials or SQL file path! Please check your .env file.")
    exit(1)

def init_database():
    print(f"🔄 Connecting to {DB_HOST}...")
    
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("✅ Successfully connected!")
        
        with connection.cursor() as cursor:
            # Read the SQL file
            if not os.path.exists(SQL_FILE_PATH):
                print(f"❌ Error: Could not find SQL file at {SQL_FILE_PATH}")
                return

            with open(SQL_FILE_PATH, 'r') as f:
                sql_script = f.read()
            
            # Split into individual statements
            statements = sql_script.split(';')
            
            for statement in statements:
                if statement.strip():
                    try:
                        print(f"Executing: {statement.strip()[:50]}...")
                        cursor.execute(statement)
                    except Exception as e:
                        print(f"⚠️ Error executing statement: {e}")
                        
        connection.commit()
        print("\n🎉 Database tables and sample data created successfully!")
        
    except Exception as e:
        print(f"\n❌ Failed to initialize database: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()
            print("🔒 Database connection closed.")

if __name__ == "__main__":
    init_database()