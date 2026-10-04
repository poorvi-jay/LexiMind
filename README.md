## Development Setup

Python: 3.13.x
Node.js: 22.x
Create virtual environment:
py -3.13 -m venv .venv

Database (PostgreSQL):
Create a database and user, e.g. in psql:
CREATE USER leximind WITH PASSWORD 'leximind';
CREATE DATABASE leximind OWNER leximind;

Backend:
pip install -r requirements.txt
Copy backend/.env.example to backend/.env and set SECRET_KEY and DATABASE_URL
uvicorn backend.main:app --reload
Tables are created automatically on first start.
If DATABASE_URL is not set, the backend falls back to a local SQLite file (backend/dev.db).

Moving existing data from SQLite to PostgreSQL (one-off, optional):
python -m backend.scripts.migrate_sqlite_to_postgres
Copies everything from backend/dev.db into DATABASE_URL. It refuses to run if PostgreSQL already has data.
Check which tables exist with: python check_tables.py

Frontend:
cd frontend
npm install
npm run dev