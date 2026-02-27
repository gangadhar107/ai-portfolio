"""
Test PostgreSQL Connection — Phase 1 Verification
Run this to verify Python can connect to the local PostgreSQL database.
DELETE THIS FILE after verification.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    print("Make sure your .env file exists and has DATABASE_URL set")
    sys.exit(1)

try:
    import psycopg
    
    print(f"Connecting to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Check PostgreSQL version
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    print(f"✅ Connection successful!")
    print(f"   PostgreSQL version: {version.split(',')[0]}")
    
    # Check if tables exist
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    if tables:
        print(f"✅ Tables found: {', '.join(tables)}")
    else:
        print("⚠️  No tables found. Run database/schema.sql first.")
    
    # Check row counts if tables exist
    for table in ['applications', 'visits', 'ref_codes']:
        if table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"   {table}: {count} rows")
    
    cur.close()
    conn.close()
    print("\n✅ Phase 1 database connection verified!")
    
except psycopg.OperationalError as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Is PostgreSQL running? (check with: pg_isready)")
    print("2. Does the database exist? (createdb portfolio_db)")
    print("3. Does the user exist? (createuser portfolio_user)")
    print("4. Is the DATABASE_URL correct in .env?")
    sys.exit(1)
    
except ImportError:
    print("❌ psycopg not installed. Run: pip install 'psycopg[binary]'")
    sys.exit(1)
