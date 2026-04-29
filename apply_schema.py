import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

with open("database/schema.sql", "r", encoding="utf-8") as f:
    schema_sql = f.read()

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        # We need to execute the commands. To handle 'ALTER TABLE', we might need a separate check 
        # or just run it and ignore errors if column already exists.
        # But schema.sql has CREATE TABLE IF NOT EXISTS.
        cur.execute(schema_sql)
        # Explicitly alter the applications table in case it exists but doesn't have the new column
        try:
            cur.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS assessment_status TEXT DEFAULT 'not_run';")
        except psycopg.errors.DuplicateColumn:
            pass
        conn.commit()

print("Schema applied successfully.")

