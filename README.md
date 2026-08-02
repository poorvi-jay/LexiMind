## Development Setup

Python: 3.13.x
Node.js: 22.x
Create virtual environment:
py -3.13 -m venv .venv

Backend:
pip install -r requirements.txt
uvicorn backend.main:app --reload

Frontend:
cd frontend
npm install
npm run dev