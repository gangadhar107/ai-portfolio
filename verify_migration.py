"""
Migration verification script for AI Portfolio.
Compares a source DB (Neon) and a target DB (CockroachDB) after import.
"""

import argparse
import sys
import psycopg
from psycopg.rows import dict_row


REQUIRED_TABLES = {"applications", "visits", "ref_codes"}

REQUIRED_COLUMNS = {
    "applications": {
        "id",
        "company_name",
        "person_name",
        "position",
        "date_applied",
        "outcome",
        "ref_code",
        "notes",
        "created_at",
        "outreach_channel",
        "contact_person",
        "role_category",
        "followed_up",
        "follow_up_date",
        "follow_up_response",
        "outcome_date",
        "rejection_reason",
    },
    "visits": {
        "id",
        "ref_code",
        "timestamp",
        "visit_count",
        "pages_visited",
        "country",
        "visit_token",
        "is_return_visit",
        "visit_source",
        "time_on_site",
        "utm_source",
        "utm_medium",
    },
    "ref_codes": {
        "id",
        "ref_code",
        "application_id",
        "created_date",
        "is_active",
    },
}


def _connect(url: str):
    return psycopg.connect(url, row_factory=dict_row)


def _fetch_table_names(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        return {r["table_name"] for r in cur.fetchall()}


def _fetch_columns(conn, table: str) -> dict[str, dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return {r["column_name"]: r for r in cur.fetchall()}


def _row_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        return int(cur.fetchone()["cnt"])


def _check_bool_defaults(columns: dict[str, dict], table: str, col: str, expected_default_substr: str) -> list[str]:
    if col not in columns:
        return [f"{table}.{col} missing"]
    default_val = (columns[col]["column_default"] or "").lower()
    if expected_default_substr not in default_val:
        return [f"{table}.{col} default mismatch (got: {columns[col]['column_default']})"]
    return []


def _smoke_dashboard_query(conn) -> list[str]:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.company_name,
                    a.position,
                    a.ref_code,
                    COUNT(v.id) AS visit_count
                FROM applications a
                LEFT JOIN visits v ON a.ref_code = v.ref_code
                GROUP BY a.id
                ORDER BY a.date_applied DESC
                LIMIT 1
                """
            )
            cur.fetchone()
        return []
    except Exception as e:
        return [f"dashboard smoke query failed: {e}"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="SOURCE_DATABASE_URL (Neon)")
    parser.add_argument("--target", required=True, help="TARGET_DATABASE_URL (CockroachDB)")
    args = parser.parse_args()

    failures: list[str] = []

    try:
        with _connect(args.source) as src, _connect(args.target) as tgt:
            src_tables = _fetch_table_names(src)
            tgt_tables = _fetch_table_names(tgt)

            missing_tables = REQUIRED_TABLES - tgt_tables
            if missing_tables:
                failures.append(f"target missing tables: {sorted(missing_tables)}")

            for table in sorted(REQUIRED_TABLES):
                if table not in tgt_tables:
                    continue

                tgt_cols = _fetch_columns(tgt, table)
                missing_cols = REQUIRED_COLUMNS[table] - set(tgt_cols.keys())
                if missing_cols:
                    failures.append(f"target missing columns in {table}: {sorted(missing_cols)}")

                try:
                    src_cnt = _row_count(src, table) if table in src_tables else None
                    tgt_cnt = _row_count(tgt, table)
                    if src_cnt is not None and src_cnt != tgt_cnt:
                        failures.append(f"row count mismatch for {table}: source={src_cnt} target={tgt_cnt}")
                except Exception as e:
                    failures.append(f"row count check failed for {table}: {e}")

            if "applications" in tgt_tables:
                failures.extend(_check_bool_defaults(_fetch_columns(tgt, "applications"), "applications", "followed_up", "false"))
            if "visits" in tgt_tables:
                failures.extend(_check_bool_defaults(_fetch_columns(tgt, "visits"), "visits", "is_return_visit", "false"))

            failures.extend(_smoke_dashboard_query(tgt))

    except Exception as e:
        print(f"Verification failed to run: {e}")
        sys.exit(2)

    if failures:
        print("❌ Migration verification failed:")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)

    print("✅ Migration verification passed")
    sys.exit(0)


if __name__ == "__main__":
    main()

