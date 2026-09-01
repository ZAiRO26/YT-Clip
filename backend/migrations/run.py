"""
Run SQL migration files against the database.
Usage: uv run python -m migrations.run
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection_string() -> str:
    """Build a psycopg2-compatible connection string from DATABASE_URL_SYNC."""
    url = os.getenv("DATABASE_URL_SYNC", "")
    if not url:
        print("ERROR: DATABASE_URL_SYNC not set in .env")
        sys.exit(1)
    # Strip SQLAlchemy dialect prefix — psycopg2 only understands postgresql://
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    return url


def run_migration(filepath: Path) -> None:
    """Execute a single .sql migration file."""
    conn_str = get_connection_string()
    sql = filepath.read_text(encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Running migration: {filepath.name}")
    print(f"{'='*60}")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        print(f"[OK] Migration {filepath.name} applied successfully.")
    except Exception as e:
        print(f"[FAIL] Migration {filepath.name} failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def main() -> None:
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        print("No migration files found.")
        return

    print(f"Found {len(sql_files)} migration file(s):")
    for f in sql_files:
        print(f"  - {f.name}")

    for sql_file in sql_files:
        run_migration(sql_file)

    print(f"\n{'='*60}")
    print("All migrations complete.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
