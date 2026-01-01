# Gas Agency Backend (FastAPI)

This is a FastAPI backend scaffold for the Gas Agency system. It provides user auth, booking and basic stock management logic with MySQL.

Quick start:

1. Create a virtualenv and install:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and update credentials.

3. Run the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Notes:
- This is a scaffold. Extend models, implement payment integration, and add tests and migrations (alembic).
