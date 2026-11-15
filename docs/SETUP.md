# Local setup (backend)

Everything runs locally: no Docker, no cloud. Verified on macOS (arm64) with Python 3.14.10 and PostgreSQL 18.6.
The full README (with frontend and demo credentials) arrives in Phase 4; this page covers the backend.

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.14.x | `python3.14 --version` |
| PostgreSQL | 18 | `psql --version`, `pg_isready` |
| Node.js (frontend, Phase 3) | 26 LTS | `node --version` |

## 2. Create the databases

```bash
# macOS/Homebrew (your OS user is a superuser):
createdb itsm
createdb itsm_test          # optional: only for running the SQL tests on PostgreSQL

# Or with a dedicated user (any OS), inside psql as the postgres superuser:
#   CREATE USER itsm_user WITH PASSWORD 'change-me';
#   CREATE DATABASE itsm OWNER itsm_user;
#   CREATE DATABASE itsm_test OWNER itsm_user;
```

## 3. Configure

```bash
cp backend/.env.example backend/.env
python3.14 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as ITSM_JWT_SECRET
```

Set `ITSM_DATABASE_URL`, e.g. `postgresql+psycopg://itsm_user:change-me@localhost:5432/itsm`
(Homebrew with peer auth: `postgresql+psycopg://<your-os-user>@localhost:5432/itsm`).

## 4. Run

```bash
./run_backend.sh          # macOS / Linux
.\run_backend.ps1         # Windows PowerShell
```

The script creates `backend/.venv`, installs the pinned `requirements.txt`, runs `alembic upgrade head`,
and starts uvicorn on <http://127.0.0.1:8000>. API docs: <http://127.0.0.1:8000/docs>.

Manual equivalent:

```bash
cd backend
python3.14 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:create_app --factory --reload
```

## 5. Tests

```bash
cd backend
.venv/bin/pytest                                   # SQLite in-memory, no setup needed
ITSM_TEST_DATABASE_URL=postgresql+psycopg://<user>@localhost:5432/itsm_test .venv/bin/pytest tests/api
```

`ITSM_TEST_DATABASE_URL` drops and recreates every table in that database, so never point it at `itsm`.

## Library compatibility notes (Python 3.14)

| Package | Status |
|---|---|
| FastAPI 0.163 / Starlette 1.10 / Pydantic 2.14 | OK on 3.14 |
| SQLAlchemy 2.1.8 | OK; same typed 2.0-style API (`Mapped`, `mapped_column`) |
| psycopg 3.3 (binary) | OK, 3.14 wheels |
| scikit-learn 1.9.1 / numpy 2.5 / scipy 1.18 | OK, 3.14 wheels |
| argon2-cffi 25.1, PyJWT 2.15 | OK |
| httpx | Starlette 1.10's `TestClient` deprecates `httpx`; pinned its successor **`httpx2`** instead |
| email-validator | Dropped: `EmailStr` rejects reserved demo domains (`.test`, `.local`). Email format is validated once, in the domain (`app/domain/validation.py`) |
