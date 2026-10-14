## Development Setup

Python: 3.13.x
Node.js: 22.x
Create virtual environment:
py -3.13 -m venv .venv

Database (PostgreSQL 13 or newer):
Install PostgreSQL and make sure its service is running.
Create a database and user, e.g. in psql as the postgres superuser:
CREATE USER leximind WITH PASSWORD 'choose_a_password';
CREATE DATABASE leximind OWNER leximind;
Avoid @ : / # in the password, or URL-encode them in DATABASE_URL.

Backend:
pip install -r requirements.txt
Copy backend/.env.example to backend/.env and set SECRET_KEY and DATABASE_URL.
The port in DATABASE_URL is machine-specific (5432 is the default; some installs use 5433).
The backend refuses to start without DATABASE_URL.
Create the schema (run again after pulling new migrations):
alembic upgrade head
uvicorn backend.main:app --reload
If the backend says "Database schema not found", run alembic upgrade head.

Windows: if the backend fails with "no pq wrapper available" or "An Application Control
policy has blocked this file", Smart App Control is blocking the driver's bundled DLL.
Add PostgreSQL's bin folder (e.g. C:\Program Files\PostgreSQL\17\bin) to your user PATH
and open a new terminal; psycopg then uses PostgreSQL's own libpq.

Schema changes:
Edit backend/models_temp.py, then:
alembic revision --autogenerate -m "describe the change"
Review the generated file in alembic/versions before running alembic upgrade head.

Moving existing data from the old SQLite database (one-off, optional):
python scripts/migrate_sqlite_to_pg.py --dry-run
python scripts/migrate_sqlite_to_pg.py
Copies backend/dev.db into DATABASE_URL in one transaction. The dry run rolls back.
It refuses to run if PostgreSQL already has data, and stops on orphan rows or bad ids.
Use --sqlite path/to/dev.db to copy a different file.
Check which tables exist with: python check_tables.py

Frontend:
cd frontend
npm install
npm run dev
