"""
Settle Up - Safe, Non-Destructive SQLite to PostgreSQL Migration Tool
Transfers existing local development data from `settleup.db` to hosted PostgreSQL (e.g. Neon).

Safety Guarantees:
- READ-ONLY access to `settleup.db` (source data is never altered or deleted).
- NON-DESTRUCTIVE to target PostgreSQL (never drops or purges tables).
- Idempotent: Skips records that already exist in the target database.
- Defaults to --dry-run unless --commit is explicitly passed.

Usage:
    # 1. Preview records to migrate (dry run):
    python migrate_sqlite_to_postgres.py --dry-run

    # 2. Execute migration with DATABASE_URL from environment or argument:
    python migrate_sqlite_to_postgres.py --commit --target-url "postgresql://user:pass@ep-host.neon.tech/neondb?sslmode=require"
"""

import os
import sys
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

# Reconfigure console output for UTF-8 (emojis, currency symbols)
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TABLE_ORDER = [
    'users',
    'rooms',
    'members',
    'expenses',
    'expense_splits',
    'settlements',
    'join_requests',
    'balance_records',
    'room_invitations'
]


def get_sqlite_tables_and_columns(sqlite_conn):
    cur = sqlite_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = {r[0] for r in cur.fetchall()}
    schema = {}
    for table in existing_tables:
        cur.execute(f"PRAGMA table_info(\"{table}\");")
        columns = [r[1] for r in cur.fetchall()]
        schema[table] = columns
    return schema


def parse_args():
    parser = argparse.ArgumentParser(
        description="Safely migrate Settle-Up SQLite data to PostgreSQL (Neon)."
    )
    parser.add_argument(
        '--sqlite-path',
        default='settleup.db',
        help="Path to source SQLite database file (default: settleup.db)"
    )
    parser.add_argument(
        '--target-url',
        default=os.getenv('DATABASE_URL'),
        help="Target PostgreSQL connection URL (defaults to DATABASE_URL environment variable)"
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        help="Execute database writes. If not specified, runs in DRY-RUN mode."
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Simulate migration without making changes (default behavior)."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dry_run = not args.commit or args.dry_run

    sqlite_path = Path(args.sqlite_path).resolve()
    if not sqlite_path.exists():
        print(f"[!] SQLite source database not found at: {sqlite_path}")
        sys.exit(1)

    print("\n" + "=" * 64)
    print("  SETTLE-UP SAFE DATA MIGRATION (SQLite → PostgreSQL)")
    print("=" * 64)
    print(f" [*] Source SQLite:  {sqlite_path}")
    print(f" [*] Mode:           {'DRY RUN (Simulation only, no data written)' if dry_run else 'LIVE COMMIT (Writing to PostgreSQL)'}")

    # Open SQLite in read-only mode (URI format)
    sqlite_uri = f"file:{sqlite_path.as_posix()}?mode=ro"
    try:
        sqlite_conn = sqlite3.connect(sqlite_uri, uri=True)
    except Exception:
        # Fallback to standard connection if URI mode is unsupported
        sqlite_conn = sqlite3.connect(str(sqlite_path))

    sqlite_schema = get_sqlite_tables_and_columns(sqlite_conn)

    # Count source records
    total_source_records = 0
    source_counts = {}
    for table in TABLE_ORDER:
        if table in sqlite_schema:
            cur = sqlite_conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM \"{table}\"")
            count = cur.fetchone()[0]
            source_counts[table] = count
            total_source_records += count
        else:
            source_counts[table] = 0

    print("\n [1] SOURCE SQLITE SUMMARY:")
    for table in TABLE_ORDER:
        if table in sqlite_schema:
            print(f"     • {table:18} : {source_counts[table]} records")

    if total_source_records == 0:
        print("\n [✓] Source SQLite database has 0 records. Nothing to migrate.")
        sqlite_conn.close()
        return

    if dry_run:
        print("\n" + "-" * 64)
        print(" [!] DRY-RUN COMPLETE")
        print(f"     Found {total_source_records} source records across {len([t for t in TABLE_ORDER if source_counts[t] > 0])} tables.")
        print("     To migrate these records into PostgreSQL, run:")
        print("       python migrate_sqlite_to_postgres.py --commit --target-url \"postgresql://...\"")
        print("-" * 64 + "\n")
        sqlite_conn.close()
        return

    # LIVE COMMIT: PostgreSQL Connection
    target_url = args.target_url
    if not target_url:
        print("\n[!] Error: Target PostgreSQL URL is required for live migration.")
        print("    Specify --target-url or set the DATABASE_URL environment variable.")
        sys.exit(1)

    # Clean URL scheme
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    print(f"\n [*] Connecting to target PostgreSQL...")
    try:
        from sqlalchemy import create_engine, text, inspect
    except ImportError:
        print("[!] Error: SQLAlchemy is required. Run: pip install -r requirements.txt")
        sys.exit(1)

    try:
        pg_engine = create_engine(target_url, pool_pre_ping=True)
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(" [✓] Successfully connected to PostgreSQL.")
    except Exception as e:
        print(f"\n[!] Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    # Verify tables exist on target
    inspector = inspect(pg_engine)
    pg_tables = set(inspector.get_table_names())

    # Migrate table by table in dependency order
    migrated_count = 0
    skipped_count = 0

    with pg_engine.begin() as pg_conn:
        for table in TABLE_ORDER:
            if table not in sqlite_schema or source_counts[table] == 0:
                continue

            if table not in pg_tables:
                print(f" [!] Skipping table '{table}': Table does not exist in target PostgreSQL database.")
                print(f"     Tip: Initialize tables first with: python server.py --init-db")
                continue

            # Intersect columns between SQLite and PostgreSQL
            sqlite_cols = sqlite_schema[table]
            pg_col_info = inspector.get_columns(table)
            pg_cols = {c['name'] for c in pg_col_info}
            common_cols = [c for c in sqlite_cols if c in pg_cols]

            if not common_cols:
                continue

            col_names_sql = ", ".join([f'"{c}"' for c in common_cols])
            placeholders = ", ".join([f":{c}" for c in common_cols])

            # Fetch existing IDs in PostgreSQL to avoid duplicates
            existing_ids = set()
            if 'id' in pg_cols:
                res = pg_conn.execute(text(f'SELECT "id" FROM "{table}"'))
                existing_ids = {str(r[0]) for r in res.fetchall()}

            # Fetch source records
            cur = sqlite_conn.cursor()
            cur.execute(f"SELECT {col_names_sql} FROM \"{table}\"")
            rows = cur.fetchall()

            table_migrated = 0
            table_skipped = 0

            insert_stmt = text(f'INSERT INTO "{table}" ({col_names_sql}) VALUES ({placeholders})')

            for row in rows:
                row_dict = dict(zip(common_cols, row))
                record_id = str(row_dict.get('id', ''))

                if record_id and record_id in existing_ids:
                    table_skipped += 1
                    skipped_count += 1
                    continue

                pg_conn.execute(insert_stmt, row_dict)
                if record_id:
                    existing_ids.add(record_id)
                table_migrated += 1
                migrated_count += 1

            print(f"  --> {table:18}: {table_migrated} inserted, {table_skipped} already existed (skipped)")

    sqlite_conn.close()

    print("\n" + "=" * 64)
    print(" [✓] MIGRATION COMPLETED SUCCESSFULLY")
    print(f"     Total records inserted into PostgreSQL: {migrated_count}")
    print(f"     Total existing records skipped:        {skipped_count}")
    print("=" * 64 + "\n")


if __name__ == '__main__':
    main()
