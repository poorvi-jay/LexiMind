"""
One-off copy of the old SQLite database (backend/dev.db) into
PostgreSQL. Run from the repo root after `alembic upgrade head`:

    python scripts/migrate_sqlite_to_pg.py --dry-run
    python scripts/migrate_sqlite_to_pg.py
    python scripts/migrate_sqlite_to_pg.py --sqlite path/to/dev.db

- Reads SQLite with raw sqlite3 in read-only mode, so the old file is
  never changed and the ORM models can't interfere with the read.
- Writes through the table definitions in backend/models_temp.py, in
  foreign-key order, inside a single transaction: if any row fails,
  nothing is written.
- Converts each value to the PostgreSQL column type: text ids to UUID,
  ISO text to datetime/date, 0/1 to bool. Text in a numeric column or
  a malformed id stops the run with the offending row.
- Checks for orphan user_ids before inserting.
- Refuses to run if any target table already has rows, so it can't
  insert twice.
- --dry-run does everything, prints the counts, then always rolls back.
"""
import argparse
import datetime
import sqlite3
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Standalone script: main.py isn't loading .env for us.
load_dotenv(ROOT / "backend" / ".env")

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, Uuid, func, select  # noqa: E402

from backend.models_temp import Base, engine  # noqa: E402

DEFAULT_SQLITE = ROOT / "backend" / "dev.db"

# Parents before children, so every user_id already exists when its
# row goes in.
TABLE_ORDER = [
    "users",
    "saved_documents",
    "writing_sessions",
    "reading_sessions",
    "word_repeat_log",
    "word_bank",
]
CHILD_TABLES = TABLE_ORDER[1:]


class MigrationError(Exception):
    pass


def convert(value, column, table, row_id):
    """Turn one SQLite value into the Python type its PostgreSQL column
    expects. Raises MigrationError instead of letting a bad value fail
    later with a less helpful database error."""
    if value is None:
        return None
    col_type = column.type
    where = f"{table}.{column.name} (row id {row_id!r})"

    if isinstance(col_type, Uuid):
        try:
            return uuid.UUID(str(value))
        except ValueError:
            raise MigrationError(f"{where}: not a valid UUID: {value!r}")

    # Check DateTime before Date: they are separate types, and
    # next_review must stay a plain date.
    if isinstance(col_type, DateTime):
        if not isinstance(value, str):
            raise MigrationError(f"{where}: expected ISO datetime text, got {value!r}")
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            raise MigrationError(f"{where}: unparseable datetime: {value!r}")

    if isinstance(col_type, Date):
        if not isinstance(value, str):
            raise MigrationError(f"{where}: expected ISO date text, got {value!r}")
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            raise MigrationError(f"{where}: unparseable date: {value!r}")

    if isinstance(col_type, Boolean):
        if value in (0, 1):
            return bool(value)
        raise MigrationError(f"{where}: expected 0/1 boolean, got {value!r}")

    if isinstance(col_type, Integer):
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        raise MigrationError(f"{where}: not an integer: {value!r}")

    if isinstance(col_type, Float):
        if isinstance(value, (int, float)):
            return float(value)
        raise MigrationError(f"{where}: not a number: {value!r}")

    if isinstance(col_type, (String, Text)):
        if not isinstance(value, str):
            raise MigrationError(f"{where}: expected text, got {value!r}")
        return value

    raise MigrationError(f"{where}: no conversion for column type {col_type!r}")


def read_table(src, table):
    """Return the SQLite rows of one table as dicts, converted to the
    PostgreSQL column types."""
    source_cols = [r[1] for r in src.execute(f"PRAGMA table_info({table.name})")]
    unknown = set(source_cols) - set(table.columns.keys())
    if unknown:
        # A column the models don't know would be silently dropped.
        raise MigrationError(
            f"{table.name}: SQLite has columns missing from the models: {sorted(unknown)}"
        )

    rows = []
    cursor = src.execute(f"SELECT {', '.join(source_cols)} FROM {table.name}")
    for raw in cursor:
        record = dict(zip(source_cols, raw))
        row_id = record.get("id")
        rows.append(
            {
                name: convert(value, table.columns[name], table.name, row_id)
                for name, value in record.items()
            }
        )
    return rows


def check_orphans(src):
    problems = []
    for name in CHILD_TABLES:
        bad = src.execute(
            f"SELECT id, user_id FROM {name} "
            "WHERE user_id IS NULL OR user_id NOT IN (SELECT id FROM users)"
        ).fetchall()
        if bad:
            problems.append(f"{name}: {len(bad)} orphan row(s), e.g. {bad[:3]}")
    if problems:
        raise MigrationError("Orphan user_ids found:\n  " + "\n  ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy backend/dev.db into PostgreSQL.")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE), help="SQLite file to copy from")
    parser.add_argument("--dry-run", action="store_true", help="run everything, then roll back")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        print(f"SQLite file not found: {sqlite_path}")
        return 1

    tables = {name: Base.metadata.tables[name] for name in TABLE_ORDER}
    print(f"Source: {sqlite_path}")
    print(f"Target: {engine.url.render_as_string(hide_password=True)}")
    print("Mode:   " + ("DRY RUN (will roll back)" if args.dry_run else "REAL RUN"))

    src = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    try:
        check_orphans(src)
        data = {name: read_table(src, tables[name]) for name in TABLE_ORDER}
    except MigrationError as e:
        print(f"ABORTED before writing anything: {e}")
        return 1
    finally:
        src.close()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            non_empty = [
                name for name in TABLE_ORDER
                if conn.execute(select(func.count()).select_from(tables[name])).scalar()
            ]
            if non_empty:
                print(
                    "ABORTED: PostgreSQL already has rows in "
                    + ", ".join(non_empty)
                    + ". Nothing was written."
                )
                trans.rollback()
                return 1

            for name in TABLE_ORDER:
                rows = data[name]
                if rows:
                    conn.execute(tables[name].insert(), rows)
                in_pg = conn.execute(select(func.count()).select_from(tables[name])).scalar()
                if in_pg != len(rows):
                    raise MigrationError(f"{name}: read {len(rows)} rows but PostgreSQL has {in_pg}")
                print(f"  {name}: {in_pg} rows")
        except Exception as e:
            trans.rollback()
            print(f"ABORTED, rolled back, nothing written: {e}")
            return 1

        if args.dry_run:
            trans.rollback()
            print("Dry run finished: rolled back, nothing written.")
        else:
            trans.commit()
            print("Committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
