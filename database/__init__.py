"""
Database connection module for AI Portfolio.
Provides context managers for PostgreSQL connections using psycopg3.
"""

import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def get_connection():
    """
    Context manager that yields a PostgreSQL connection.
    Automatically commits on success and rolls back on error.
    
    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = None
    try:
        conn = psycopg.connect(DATABASE_URL)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_cursor(dict_cursor=True):
    """
    Context manager that yields a PostgreSQL cursor.
    Uses dict_row by default for dict-like row access.
    Automatically commits the connection on success.
    
    Usage:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM applications")
            rows = cur.fetchall()
    """
    with get_connection() as conn:
        row_factory = dict_row if dict_cursor else None
        cur = conn.cursor(row_factory=row_factory)
        try:
            yield cur
        finally:
            cur.close()
