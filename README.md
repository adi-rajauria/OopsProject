# I-ITSM: Intelligent IT Service Management & Incident Resolution System

[![CI](https://github.com/adi-rajauria/OopsProject/actions/workflows/ci.yml/badge.svg)](https://github.com/adi-rajauria/OopsProject/actions/workflows/ci.yml)

A web application for the full incident lifecycle (**report → classify → prioritise → assign → investigate → resolve →
verify → close**), with SLA monitoring, notifications, a complete audit trail, dashboards and eight explainable
intelligent features. Built for CS F213 (Object-Oriented Programming) to show how OOP design keeps a real system
maintainable and extensible.

Everything runs locally: no Docker, no cloud.

---

## Features

### By role (each role gets its own interface)

| Employee (portal) | Technician (console) | Administrator (console) |
|---|---|---|
| Register / sign in | Personal queue, sorted by deadline | Overview dashboard with live updates |
| Report an incident, **by typing or by voice** | Acknowledge, start, add internal notes | Manage users, technicians, services, categories |
| Live suggestions while typing: category, impact/urgency, similar open incidents, **fixes to try first** | Request more information (pauses the SLA clock) | Configure SLA policies per priority / service |
| Track status and the full timeline | Resolve with a summary; reuse past fixes | **Switch the assignment strategy at runtime** |
| Answer technician questions, add information | Recommended technicians with reasons | Technician workload, service analysis, SLA report |
| Verify the fix, rate it, or reopen | Workload view | Audit log viewer, CSV exports |
| Notification bell, in-app + simulated e-mail/SMS | Service health and correlation | Escalation settings, on-demand SLA check |

### Core

- **Priority** from impact x urgency x business criticality x affected-users factor (P1-P4, documented formula).
- **4 assignment strategies:** skill, load, round-robin, experience (Strategy pattern, switchable without a restart).
- **SLA:** response + resolution deadlines per priority and service, warning at 75 %, violation detection and
  recording, a background check every 60 s, and a clock that pauses while waiting on the reporter.
- **Lifecycle:** 9 states with enforced transitions (`InvalidStateTransitionError` for illegal moves, e.g. NEW → CLOSED).
- **Notifications:** in-app, e-mail and SMS (simulated providers behind adapters).
- **Audit trail:** timestamp, user, action, incident, previous state, new state and description for every change.
- **Search:** 11 combinable criteria (ID, text, date range, status, priority, category, service, technician,
  unassigned, SLA status, open only), bookmarkable, exportable to CSV.

### Intelligent features (all explainable; see [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md))

| Feature | How |
|---|---|
| Duplicate / related incident detection | scikit-learn TF-IDF (character n-grams) + cosine similarity, same service, 24 h window |
| Category suggestion | keywords + similarity to resolved history (matches the final category for 39 of 43 seed incidents) |
| Smart technician recommendation | weighted skill, free capacity, experience, service history and reporter ratings, with reasons |
| SLA risk detection | elapsed % x priority weight + penalties for unassigned / unacknowledged incidents |
| Automatic escalation | Technician → Team Lead → System Admin → IT Manager, one level per missed response window |
| Suggested resolutions + self-service | fixes that worked for similar incidents, for staff and for employees before they submit |
| Recurring problem detection | similar incidents that keep coming back on a service over 30 days |
| Predicted resolution time | median working time of comparable resolved incidents |
| Impact / urgency hints | phrase rules ("all customers", "cannot pay") with the matched phrase as the reason |

### Innovation

- **Real-time dashboard** via Server-Sent Events.
- **Service dependency graph** with hotspot and upstream-cause correlation.
- **Voice input** for reporting incidents and for every free-text box on the incident page: notes, questions, answers,
  resolutions (Web Speech API, on-device where the browser supports it).
- **CI on GitHub Actions:** tests on SQLite and PostgreSQL 18, migration + seed, frontend build.

---

## Architecture

```
React + TypeScript (Vite)  ──HTTP/JSON + SSE──▶  FastAPI routers (api)        role guard on every endpoint
                                                     │
                                                     ▼
                                                 services (use cases)  ──▶  observers (audit, notifications, SLA, live)
                                                     │
                                                     ▼
                                                 domain (pure OOP, no framework imports)
                                                     ▲
                                                     │ implements interfaces defined in the domain
                                                 repositories (SQLAlchemy)  ──▶  PostgreSQL 18
```

Dependencies point inward, so the domain is unit-tested without a database.

| Pattern | Where |
|---|---|
| Strategy | `PriorityCalculator`, `AssignmentStrategy` (4), notification channel selection |
| State | incident lifecycle (`domain/lifecycle.py`) |
| Observer | event bus → audit logger, notification dispatcher, SLA tracker, live broadcaster |
| Factory | `IncidentFactory`, `UserFactory`, `NotificationFactory` |
| Repository + Unit of Work | all persistence, interfaces in `domain/repositories.py` |
| Adapter | simulated e-mail / SMS providers behind `NotificationChannel` |
| Template Method | `AssignmentStrategy.choose()` filters, subclasses pick |

Open/Closed examples (new category, strategy or channel with no changes elsewhere): [`docs/OPEN_CLOSED_EXAMPLES.md`](docs/OPEN_CLOSED_EXAMPLES.md).

### Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14, FastAPI, SQLAlchemy 2 (typed), Alembic, Pydantic v2 |
| Auth | JWT (PyJWT, HS256), Argon2id password hashing, 3 roles |
| Intelligence | scikit-learn (TF-IDF + cosine similarity), rule-based scoring |
| Database | PostgreSQL 18 (tests: SQLite in memory, or PostgreSQL) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, React Router |
| Tests / CI | pytest (171 cases), GitHub Actions |

---

## Quick start

### 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.14 | `python --version` |
| PostgreSQL | 18 | `psql --version` |
| Node.js | 26 LTS (npm 11) | `node --version` |

### 2. Create the database

In `psql` as the `postgres` user:

```sql
CREATE DATABASE itsm;
CREATE DATABASE itsm_test;   -- optional: only for running the tests on PostgreSQL
```

### 3. Configure the backend

```bash
cp backend/.env.example backend/.env                     # Windows: copy backend\.env.example backend\.env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

In `backend/.env`, paste that value as `ITSM_JWT_SECRET` and set `ITSM_DATABASE_URL`, for example
`postgresql+psycopg://postgres:<password>@localhost:5432/itsm`.

### 4. Run (two terminals)

| | Windows (PowerShell) | macOS / Linux |
|---|---|---|
| Backend → <http://127.0.0.1:8000/docs> | `.\run_backend.ps1` | `./run_backend.sh` |
| Frontend → <http://127.0.0.1:5173> | `.\run_frontend.ps1` | `./run_frontend.sh` |

The backend script creates the virtual environment, installs the pinned requirements, runs `alembic upgrade head` and
starts the API. To install the Python packages yourself: `pip install -r requirements.txt` from the repository root
(versions are pinned in `backend/requirements.txt`). The frontend script installs packages on first run and starts Vite, which forwards `/api` to the backend.

### 5. Load demo data

```bash
cd backend
.venv\Scripts\python -m scripts.seed --reset     # Windows
.venv/bin/python -m scripts.seed --reset         # macOS / Linux
```

`--reset` wipes all data first. The seed replays two weeks of history through the real services: 18 users,
11 services with dependencies, 9 categories, 7 SLA policies and 43 incidents in every state, with SLA violations,
near-duplicates, escalations, feedback and a recurring problem. Times are relative to "now", so **re-seed shortly
before a demo**: the payment-outage hotspot is only visible for about 30 minutes after seeding.

---

## Demo accounts

**Password for every account: `Demo@1234`.** The sign-in page also has one-click buttons for the three roles.

| Role | Email | Name | Notes |
|---|---|---|---|
| Administrator | admin@itsm.demo | Ada Sharma | System Admin |
| Administrator | ops@itsm.demo | Omar Siddiqui | System Admin |
| Administrator | manager@itsm.demo | Ravi Menon | IT Manager (last escalation level) |
| Technician | priya@itsm.demo | Priya Nair | Team lead, Apps: APPLICATION, SOFTWARE, DATABASE |
| Technician | arjun@itsm.demo | Arjun Verma | Apps: APPLICATION, CLOUD |
| Technician | kabir@itsm.demo | Kabir Rao | Team lead, Infra: NETWORK, SECURITY |
| Technician | meera@itsm.demo | Meera Iyer | Infra: NETWORK, HARDWARE |
| Technician | tom@itsm.demo | Tom D'Souza | Infra: HARDWARE, SOFTWARE (no phone, so no SMS) |
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

---

## Tests

```bash
cd backend
.venv\Scripts\python -m pytest          # Windows: 171 cases on SQLite in memory, no setup needed
.venv/bin/pytest                        # macOS / Linux
```

To run the same suite on PostgreSQL, set `ITSM_TEST_DATABASE_URL` to the **`itsm_test`** database (it drops and
recreates every table, so never point it at `itsm`). Frontend check: `cd frontend && npm run build`.

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs both on every push and pull request.
The test-case table (ID, description, input, expected, type) is in [`docs/TEST_CASES.md`](docs/TEST_CASES.md).

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | Approved plan, repository layout, data model |
| [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) | Every intelligent feature: formula, rationale, calibration |
| [`docs/ER.md`](docs/ER.md) | Database design (Mermaid ER diagram) and relationships |
| [`docs/TEST_CASES.md`](docs/TEST_CASES.md) | Test-case table and spec-exception coverage |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Security measures and documented trade-offs |
| [`docs/OPEN_CLOSED_EXAMPLES.md`](docs/OPEN_CLOSED_EXAMPLES.md) | Extending the system without changing unrelated code |
| [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) | Every assumption made, numbered |
| [`docs/SETUP.md`](docs/SETUP.md) | Detailed setup, versions and library compatibility notes |
| <http://127.0.0.1:8000/docs> | Interactive API documentation (73 operations), while the backend runs |

## Project structure

```
backend/
  app/domain/          pure OOP model: users, incident, lifecycle (State), SLA, events, factories, strategies
  app/services/        use cases + dependency wiring (container.py)
  app/repositories/    SQLAlchemy models, mappers, repository implementations
  app/observers/       audit logger, notification dispatcher, SLA tracker, live forwarder
  app/intelligence/    the intelligent features (scikit-learn only in text_similarity.py)
  app/notifications/   simulated e-mail / SMS providers and channel adapters
  app/api/             FastAPI routers (role-guarded) + SSE stream
  app/workers/         background SLA monitor
  alembic/             database migrations
  scripts/seed.py      demo data
  tests/               unit, service and API tests
frontend/src/          typed API client, auth, hooks, components, pages per role
docs/                  design and project documentation
```

## Known limitations

- Single-process by design: the SLA monitor and the live-update broadcaster run inside the API process (see the
  scalability notes in the report).
- E-mail and SMS are simulated; real providers would plug in behind the existing adapters.
- The JWT is stored in `localStorage`, and the SSE stream takes it as a query parameter (trade-offs documented in
  `docs/SECURITY.md`).
- Voice input needs Chrome or Edge, and a network that allows the browser's speech service unless the browser has an
  on-device model.
- The UI is served by the Vite dev server; there is no production web-server setup.
