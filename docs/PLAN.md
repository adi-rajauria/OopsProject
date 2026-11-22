# Decerno — Phase 0 Plan (approved)

Spec: `OOPs_Project.pdf` (CS F213/MAC F212, Sem I 2026-27). Rubric (120): Functionality 60, Technical depth 15, UX 10, Innovation 10, Docs+Demo 10, Design/Architecture 10, Testing 5.

## Library compatibility decisions (Python 3.14 / Node 26)

| Concern | Decision |
|---|---|
| `passlib` unmaintained, breaks with bcrypt ≥4.1 / Python 3.13+ | `argon2-cffi` directly (Argon2id) |
| `python-jose` unmaintained | `PyJWT` |
| TF-IDF / cosine similarity | `scikit-learn` (`TfidfVectorizer`, `cosine_similarity`); 3.14 wheels available since 1.7.2 — verify when pinning. Wrapped behind a small `TextSimilarity` interface in `intelligence/` so the rest of the code never imports sklearn directly |
| Postgres driver | `psycopg[binary]` 3.x, sync |
| Background jobs | Plain asyncio task in FastAPI lifespan |
| Real-time | SSE via Starlette `StreamingResponse` |
| Frontend | Vite + React + TS + Tailwind v4 (`@tailwindcss/vite`) + `react-router`; no chart/UI libs (CSS bars, plain SVG graph) |

Verify exact pins against PyPI/npm when writing `requirements.txt`; if a package lacks 3.14 wheels, say so and pin the nearest working version.

## Repo tree

```
i-itsm/
├── backend/
│   ├── app/
│   │   ├── domain/            # pure Python, zero framework imports
│   │   │   ├── enums.py               # Status, Priority, Role, SLAStatus, Channel…
│   │   │   ├── exceptions.py          # ITSMError hierarchy
│   │   │   ├── users.py               # User(ABC) → Employee/Technician/Administrator
│   │   │   ├── incident.py            # Incident aggregate (has SLA, AuditTrail, comments)
│   │   │   ├── lifecycle.py           # State pattern: IncidentState subclasses
│   │   │   ├── sla.py                 # SLAPolicy, SLAClock (value objects)
│   │   │   ├── audit.py               # AuditRecord, AuditTrail
│   │   │   ├── service.py, category.py, notification.py, feedback.py
│   │   │   ├── events.py              # DomainEvent + EventBus (Observer subject)
│   │   │   ├── factories.py           # IncidentFactory, UserFactory, NotificationFactory
│   │   │   ├── strategies/
│   │   │   │   ├── priority.py        # PriorityCalculator protocol + WeightedPriorityCalculator
│   │   │   │   ├── assignment.py      # 4 strategies + registry
│   │   │   │   └── channel_selection.py
│   │   │   └── repositories.py        # repository interfaces (ABCs)
│   │   ├── repositories/      # SQLAlchemy ORM models + repo impls + mappers (+ in-memory impls for tests)
│   │   ├── services/          # IncidentService, AssignmentService, SLAService, AuthService,
│   │   │                      # NotificationService, AdminService, ReportService, SearchService
│   │   ├── notifications/     # Adapter: EmailAdapter, SMSAdapter, InAppChannel (simulated providers)
│   │   ├── intelligence/      # text_similarity.py (sklearn wrapper), duplicate_detector.py, recommender.py,
│   │   │                      # sla_risk.py, escalation.py, category_classifier.py, correlation.py
│   │   ├── observers/         # AuditLogger, NotificationDispatcher, SLATracker, SSEBroadcaster
│   │   ├── api/               # routers: auth, incidents, technicians, admin, reports, search, stream
│   │   ├── core/              # config, security (JWT/argon2), deps/role guards, db session, error handlers
│   │   ├── workers/           # sla_monitor.py (60 s loop)
│   │   └── main.py
│   ├── alembic/ + alembic.ini
│   ├── scripts/seed.py
│   ├── tests/{unit,services,api}/
│   ├── requirements.txt, .env.example
├── frontend/src/{api, auth, components, pages/{employee,technician,admin,shared}, hooks, types}
├── docs/  PLAN.md, ASSUMPTIONS.md, ARCHITECTURE.md, ALGORITHMS.md, OPEN_CLOSED_EXAMPLES.md,
│          SECURITY.md, TEST_CASES.md, REPORT.md, DEMO_SCRIPT.md, VIVA_CHEATSHEET.md, ER.md
├── run_backend.(sh|ps1), run_frontend.(sh|ps1), README.md
```

## Patterns → location

- **Strategy**: `PriorityCalculator`; `AssignmentStrategy` (Skill/Load/RoundRobin/Experience); `ChannelSelectionPolicy`. Active assignment strategy stored in `system_settings`, switched via `PUT /admin/settings/assignment-strategy`.
- **State**: `IncidentState` subclasses expose only allowed transitions; others raise `InvalidStateTransitionError`.
- **Observer**: `EventBus` publishes `IncidentCreated`, `StatusChanged`, `Assigned`, `SLAWarning`, `SLAViolated`, `Escalated` → `AuditLogger`, `NotificationDispatcher`, `SLATracker`, `SSEBroadcaster`.
- **Factory**: `IncidentFactory`, `UserFactory`, `NotificationFactory`.
- **Repository**: interfaces in `domain/repositories.py`; SQLAlchemy + in-memory implementations.
- **Adapter**: `FakeSmtpProvider` / `FakeSmsGateway` (incompatible APIs) wrapped as `EmailChannel` / `SMSChannel` behind `NotificationChannel`.
- **Registry + decorator** for strategies/channels → new strategy = new class only (Open/Closed).

## DB schema summary (PostgreSQL 18)

| Table | Key columns |
|---|---|
| `users` | id, email (unique), full_name, password_hash, role (EMPLOYEE/TECHNICIAN/ADMINISTRATOR), admin_level (SYSTEM_ADMIN/IT_MANAGER), phone, department, is_active, created_at |
| `technician_profiles` | user_id PK/FK, skills (JSON list of category codes), experience_years, max_workload, is_available, is_team_lead, team |
| `services` | id, code, name, business_criticality 1–4, owner_team, is_active |
| `service_dependencies` | service_id → depends_on_service_id |
| `categories` | id, code, name, keywords (JSON), is_active |
| `sla_policies` | id, priority, service_id (nullable = default), response_minutes, resolution_minutes, warning_threshold_pct; unique (priority, service_id) |
| `incidents` | id, number (INC1001…), title, description, reporter_id, category_id, suggested_category_id, service_id, impact, urgency, affected_users, priority, priority_score, status, assigned_technician_id, response_due_at, resolution_due_at, acknowledged_at, resolved_at, verified_at, closed_at, resolution_summary, closure_notes, sla_status, escalation_level, parent_incident_id, created_at, updated_at |
| `incident_comments` | id, incident_id, author_id, kind (NOTE/INFO_REQUEST/INFO_REPLY/COMMENT), body, is_internal, created_at |
| `incident_links` | incident_id, related_incident_id, similarity, link_type (DUPLICATE/RELATED) |
| `audit_records` | id, incident_id (nullable), actor_id (nullable = SYSTEM), action, previous_state, new_state, description, created_at |
| `sla_violations` | id, incident_id, kind (RESPONSE/RESOLUTION), due_at, detected_at, overdue_minutes |
| `notifications` | id, recipient_id, incident_id, channel, event_type, title, body, is_read, delivered, created_at |
| `feedback` | id, incident_id (unique), employee_id, rating 1–5, comment, created_at |
| `system_settings` | key PK, value (active strategy, workload cap, round-robin cursor…) |

## Initial assumptions (copy into docs/ASSUMPTIONS.md)

1. Domain model and ORM models are separate classes with mappers in `repositories/` (keeps domain framework-free).
2. Sync SQLAlchemy + psycopg 3, not async — simpler, sufficient for demo scale.
3. Roles: inheritance only User → Employee / Technician / Administrator. "Team Lead" = Technician with `is_team_lead`; "System Admin" / "IT Manager" = Administrator with `admin_level`. Self-registration always creates an Employee; admins create technicians/admins.
4. Lifecycle NEW → CLASSIFIED → ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → VERIFIED → CLOSED, plus: IN_PROGRESS ⇄ PENDING_INFO ("request more info"), RESOLVED → IN_PROGRESS (employee rejects resolution / reopen), ASSIGNED → ASSIGNED (reassign). No state skipping.
5. NEW → CLASSIFIED is automatic on create (category + priority + SLA computed). CLASSIFIED → ASSIGNED via auto-assign (active strategy) or admin manual assign. ACKNOWLEDGED / IN_PROGRESS / RESOLVED by the assigned technician. VERIFIED by the reporting employee (optionally with feedback). CLOSED by technician/admin after VERIFIED; admin may also close a RESOLVED incident unverified for 72 h (audited as override).
6. Priority: impact, urgency, business criticality each 1–4 (criticality from the service). Base = I × U × C (1–64) × affected-users factor (≤10 ×1.0, 11–100 ×1.25, >100 ×1.5), capped at 64. P1 ≥ 32, P2 ≥ 16, P3 ≥ 6, else P4. Thresholds in one place.
7. SLA: default policy = PDF table (P1 5 m / 30 m, P2 15 m / 2 h, P3 1 h / 8 h, P4 4 h / 24 h); per-service policy overrides default; neither → `MissingSLAConfigurationError`. Response met on reaching ACKNOWLEDGED; resolution met at RESOLVED. Warning at 75 % elapsed. 24×7 clocks, no business hours; clocks do NOT pause in PENDING_INFO (documented limitation). **Superseded in Phase 1: clocks now pause in PENDING_INFO, see ASSUMPTIONS.md #7.**
8. Priority change (impact/urgency edit) recalculates deadlines from the original creation time.
9. SLA status per incident: ON_TRACK / AT_RISK / BREACHED / MET. Each breach kind recorded once in `sla_violations`.
10. SLA monitor + escalation: one asyncio background loop every 60 s inside the uvicorn process (single-process assumption; multi-worker discussed under scalability).
11. Escalation for unacknowledged P1 (and P2 if enabled in settings): each level fires after one additional response window past the response deadline. Chain: assigned Technician → Team Lead of same team → System Admin → IT Manager. Each step increments `escalation_level`, notifies, audits.
12. Duplicates: on create, compare with open incidents on the same service in last 24 h via scikit-learn TF-IDF + cosine similarity. ≥ 0.45 → RELATED link shown. ≥ 0.85 from the same reporter within 30 min → `DuplicateIncidentError` unless resubmitted with `force=true`. Other users' near-duplicates are linked, never blocked.
13. Category suggestion: keyword score + scikit-learn TF-IDF similarity to centroids of historical resolved incidents; suggested and pre-filled, employee can override. Keywords stored in `categories` table so admin-added categories work immediately.
14. Assignment: technicians with active ≥ `max_workload` (default 8) excluded; none eligible → `TechnicianUnavailableError`, incident stays CLASSIFIED for admin. Manual assign over cap → `TechnicianWorkloadExceededError`. "Active" = ASSIGNED, ACKNOWLEDGED, IN_PROGRESS, PENDING_INFO. Skill-based requires category ∈ skills. Round-robin cursor in `system_settings`.
15. Smart recommendation (separate from auto-assignment strategies): skills 40 %, workload 25 %, experience 15 %, past incidents on same service 15 %, availability 5 %; returns top 3 with human-readable reasons.
16. Channels: in-app (stored, shown in bell), Email and SMS simulated (logged + notifications row, `delivered=true`). Selection: in-app always; email for assignment/resolution/closure; SMS only for P1, SLA violations, escalations.
17. "Network failure" → `NotificationDeliveryError` (simulated provider can be configured to fail for tests/demo); delivery failure does not roll back the incident change.
18. "Database failure" → `PersistenceError` wrapping SQLAlchemy errors in repositories, returned as HTTP 503.
19. Search: 9 criteria — number/ID, created-from/to, status, priority, category, service, technician, SLA status, free text (ILIKE title/description). Paginated (default 20). Employees only see their own incidents.
20. Auth: JWT access token (HS256, 60 min), no refresh token; stored in `localStorage` (simplicity vs XSS trade-off documented in SECURITY.md). CORS allows only the Vite dev origin.
21. Real-time: SSE `/api/stream/events`; token passed as query param (EventSource cannot send headers; documented). Pushes to admin/technician dashboards and the notification bell.
22. Service dependency graph: services declare `depends_on`; correlation flags incidents whose service or upstream dependency has ≥ 3 open incidents in last 2 h as "likely common cause".
23. Tests: domain + service tests use in-memory repositories (no DB). API tests use SQLite in-memory via the same SQLAlchemy models so `pytest` needs no setup — portable column types only (JSON, not JSONB/ARRAY). Postgres used for the real app and seed.
24. Incident number = `INC` + (1000 + id).
25. Timestamps stored UTC (timestamptz); frontend displays local time.
26. One feedback per incident (rating 1–5 + comment), reporter only, at/after RESOLVED → VERIFIED.
27. Service analysis dashboard: incident count per service + mean time to resolve (MTTR).
28. Provide both `.sh` and `.ps1` run scripts.

## Phase 1 scope

Setup instructions, `requirements.txt`, `.env.example`, core config, full domain layer, repository interfaces + SQLAlchemy + in-memory implementations, Alembic migration, core services (auth, lifecycle, priority, SLA, assignment, audit, notifications), ~30 passing tests.
