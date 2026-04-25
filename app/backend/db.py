import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        host="localhost",
        port="5432",
        database="securepay",
        user=os.getenv("DB_USER", "your_username"),
        password=os.getenv("DB_PASSWORD", "")
    )

def test_connection():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM scenarios")
    print(f"Scenarios count: {cur.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    test_connection()