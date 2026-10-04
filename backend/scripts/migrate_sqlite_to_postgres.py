"""
Copy existing data from the local SQLite database (backend/dev.db)
into the PostgreSQL database named by DATABASE_URL.

One-off, run from the repo root after setting DATABASE_URL:

    python -m backend.scripts.migrate_sqlite_to_postgres
    python -m backend.scripts.migrate_sqlite_to_postgres --sqlite path/to/dev.db

Creates any missing tables in PostgreSQL, then copies every table in
foreign-key-safe order inside a single transaction - if any row fails,
nothing is written. Refuses to run if the PostgreSQL tables already
contain data, so it can't duplicate rows by being run twice.
"""
import argparse
import os
import sys

from sqlalchemy import func, inspect, select

from backend.models_temp import (
    Base,
    DATABASE_URL,
    SQLITE_PATH,
    make_engine,
)

BATCH_SIZE = 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--sqlite",
        default=SQLITE_PATH,
        help=f"SQLite file to copy from (default: {SQLITE_PATH})",
    )
    args = parser.parse_args()

    if not DATABASE_URL.startswith("postgresql"):
        print("DATABASE_URL must point at PostgreSQL (set it in backend/.env).")
        return 1
    if not os.path.exists(args.sqlite):
        print(f"SQLite file not found: {args.sqlite} - nothing to migrate.")
        return 1

    source = make_engine(f"sqlite:///{args.sqlite}")
    target = make_engine(DATABASE_URL)

    Base.metadata.create_all(bind=target)

    with target.connect() as conn:
        non_empty = [
            t.name
            for t in Base.metadata.sorted_tables
            if conn.execute(select(func.count()).select_from(t)).scalar()
        ]
    if non_empty:
        print(
            "PostgreSQL already has data in: "
            + ", ".join(non_empty)
            + ". Aborting so rows aren't duplicated."
        )
        return 1

    source_tables = set(inspect(source).get_table_names())

    with source.connect() as src, target.begin() as dst:
        for table in Base.metadata.sorted_tables:
            if table.name not in source_tables:
                print(f"{table.name}: not in SQLite, skipped")
                continue

            # An older dev.db may predate some columns; copy the ones it
            # has and let the rest fall back to their defaults.
            source_columns = {c["name"] for c in inspect(source).get_columns(table.name)}
            columns = [c for c in table.columns if c.name in source_columns]

            result = src.execute(select(*columns))
            copied = 0
            while rows := result.fetchmany(BATCH_SIZE):
                dst.execute(table.insert(), [dict(r._mapping) for r in rows])
                copied += len(rows)
            print(f"{table.name}: {copied} rows")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
