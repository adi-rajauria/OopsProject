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

## 5. Web UI (frontend)

Requires Node 26 LTS (verified with Node 26.13 / npm 11.20).

```bash
./run_frontend.sh          # macOS / Linux  (installs with `npm ci` on first run)
.\run_frontend.ps1         # Windows PowerShell
```

Open <http://127.0.0.1:5173>. The Vite dev server proxies `/api` to the backend on `127.0.0.1:8000`
(override with `ITSM_API_URL=http://host:port`), so the browser only ever talks to one origin, including the
live event stream. The login page has one-click buttons for the three demo roles.

Manual equivalent: `cd frontend && npm ci && npm run dev`. Production build: `npm run build` (type-checks, then
bundles into `frontend/dist`).

| Package | Version | Note |
|---|---|---|
| React / React DOM | 19.3.1 | |
| React Router | 8.5.1 | declarative `<BrowserRouter>` API |
| Vite / @vitejs/plugin-react | 8.3.8 / 6.3.0 | |
| Tailwind CSS (+ @tailwindcss/vite) | 4.3.5 | CSS-first config in `src/index.css` |
| TypeScript | 7.0.2 | the new native compiler; `tsc` works unchanged |

## 6. Demo data

```bash
cd backend
.venv/bin/python -m scripts.seed            # refuses if data already exists
.venv/bin/python -m scripts.seed --reset    # wipes ALL data, then seeds
```

The seeder replays two weeks of history through the real services: 18 users, 11 services with dependencies, 9 categories,
7 SLA policies and 42 incidents in every state, with SLA violations, near-duplicate links, escalations and feedback.
Times are relative to "now", so re-seed shortly before a demo (open P1s keep escalating as real time passes).

**All demo accounts use the password `Demo@1234`.**

| Role | Email | Name | Notes |
|---|---|---|---|
| Administrator | admin@itsm.demo | Ada Sharma | System Admin |
| Administrator | ops@itsm.demo | Omar Siddiqui | System Admin |
| Administrator | manager@itsm.demo | Ravi Menon | IT Manager (last escalation level) |
| Technician | priya@itsm.demo | Priya Nair | Team lead, Apps: APPLICATION, SOFTWARE, DATABASE |
| Technician | arjun@itsm.demo | Arjun Verma | Apps: APPLICATION, CLOUD |
| Technician | kabir@itsm.demo | Kabir Rao | Team lead, Infra: NETWORK, SECURITY |
| Technician | meera@itsm.demo | Meera Iyer | Infra: NETWORK, HARDWARE |
| Technician | tom@itsm.demo | Tom D'Souza | Infra: HARDWARE, SOFTWARE (no phone: no SMS) |
| Technician | dev@itsm.demo | Dev Malhotra | Team lead, Platform: DATABASE, STORAGE, CLOUD |
| Technician | lina@itsm.demo | Lina Fernandes | Platform: STORAGE, CLOUD |
| Technician | sana@itsm.demo | Sana Qureshi | Identity: AUTHENTICATION, SECURITY |
| Employee | riya@itsm.demo | Riya Kapoor | Finance (reported the payment outage) |
| Employee | aman@itsm.demo | Aman Gupta | Sales |
| Employee | neha@itsm.demo | Neha Joshi | HR |
| Employee | vikram@itsm.demo | Vikram Singh | Operations |
| Employee | zoya@itsm.demo | Zoya Khan | Marketing |
| Employee | karan@itsm.demo | Karan Mehta | Engineering |
| Employee | isha@itsm.demo | Isha Bose | Customer Support |

## 7. Tests

```bash
cd backend
.venv/bin/pytest                                   # 158 cases, SQLite in-memory, no setup needed (~20 s)
ITSM_TEST_DATABASE_URL=postgresql+psycopg://<user>@localhost:5432/itsm_test .venv/bin/pytest tests/api   # same tests on PostgreSQL
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
