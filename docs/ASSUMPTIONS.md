# Cumulative assumptions

Every assumption made while building I-ITSM, numbered so the report can cite them. Updated every phase.

## Phase 0 (plan)

1. Domain model and ORM models are separate classes with mappers in `repositories/` (keeps domain framework-free).
2. Sync SQLAlchemy + psycopg 3, not async — simpler, sufficient for demo scale.
3. Roles: inheritance only User → Employee / Technician / Administrator. "Team Lead" = Technician with `is_team_lead`; "System Admin" / "IT Manager" = Administrator with `admin_level`. Self-registration always creates an Employee; admins create technicians/admins.
4. Lifecycle NEW → CLASSIFIED → ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → VERIFIED → CLOSED, plus: IN_PROGRESS ⇄ PENDING_INFO ("request more info"), RESOLVED → IN_PROGRESS (employee rejects resolution / reopen), ASSIGNED → ASSIGNED (reassign). No state skipping.
5. NEW → CLASSIFIED is automatic on create (category + priority + SLA computed). CLASSIFIED → ASSIGNED via auto-assign (active strategy) or admin manual assign. ACKNOWLEDGED / IN_PROGRESS / RESOLVED by the assigned technician. VERIFIED by the reporting employee (optionally with feedback). CLOSED by technician/admin after VERIFIED; admin may also close a RESOLVED incident unverified for 72 h (audited as override).
6. Priority: impact, urgency, business criticality each 1–4 (criticality from the service). Base = I × U × C (1–64) × affected-users factor (≤10 ×1.0, 11–100 ×1.25, >100 ×1.5), capped at 64. P1 ≥ 32, P2 ≥ 16, P3 ≥ 6, else P4. Thresholds in one place.
7. SLA: default policy = PDF table (P1 5 m / 30 m, P2 15 m / 2 h, P3 1 h / 8 h, P4 4 h / 24 h); per-service policy overrides default; neither → `MissingSLAConfigurationError`. Response met on reaching ACKNOWLEDGED; resolution met at RESOLVED. Warning at 75 % elapsed. 24×7 clocks, no business hours. **The SLA clock pauses while an incident is PENDING_INFO** (waiting for the reporter): no warnings or breaches are raised while paused, and on resume the resolution deadline moves later by the paused time. The response target is unaffected because PENDING_INFO is only reachable after acknowledgement. If a deadline had already passed when the technician requests info, the breach is still recorded. *(Changed in Phase 1 at the team's request; originally clocks did not pause.)*
8. Priority change (impact/urgency edit) recalculates deadlines from the original creation time.
9. SLA status per incident: ON_TRACK / AT_RISK / BREACHED / PAUSED / MET. Each breach kind recorded once in `sla_violations`.
10. SLA monitor + escalation: one asyncio background loop every 60 s inside the uvicorn process (single-process assumption; multi-worker discussed under scalability).
11. Escalation for unacknowledged P1 (and P2 if enabled in settings): each level fires after one additional response window past the response deadline. Chain: assigned Technician → Team Lead of same team → System Admin → IT Manager. Each step increments `escalation_level`, notifies, audits.
12. Duplicates: on create, compare with open incidents on the same service in last 24 h via scikit-learn TF-IDF + cosine similarity. ≥ 0.45 → RELATED link shown. ≥ 0.85 from the same reporter within 30 min → `DuplicateIncidentError` unless resubmitted with `force=true`. Other users' near-duplicates are linked, never blocked. *(Thresholds recalibrated in Phase 2: RELATED >= 0.18 with character n-gram TF-IDF, see #51.)*
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

## Phase 1 (backend core)

29. **Repo layout**: the plan's `i-itsm/` folder is this repository's root (`backend/`, `docs/`, run scripts at top level).
30. **Library pins**: SQLAlchemy resolved to 2.1.8 (same typed 2.0-style API). Starlette 1.10 deprecates `httpx` for `TestClient`, so `httpx2` is pinned instead. `email-validator`/`EmailStr` dropped because it rejects reserved demo domains (`.test`, `.local`); email format is validated once in the domain.
31. **AuditTrail ownership (deviation from the original plan wording)**: `Incident` composes `IncidentSLA`, its `IncidentState` and its `Comment`s. `AuditTrail` is an append-only collection keyed by incident id, written only by the `AuditLogger` observer and returned by `IncidentService.audit_trail()`. Reason: single responsibility; the Incident cannot forget or fake an audit entry, and audit also covers non-incident events (user created, setting changed).
32. Incident number is derived (`INC` + 1000 + id), not stored; "INC1005" is parsed back to id 5 for search.
33. In Phase 1 a category is required when reporting; Phase 2 adds automatic category suggestion when it is omitted.
34. Visibility: employees see only incidents they reported; technicians and administrators see all. Internal notes are visible to staff only.
35. Only the **assigned technician** may acknowledge, start work, request info and resolve. Administrators do not do technician work; they (re)assign. A VERIFIED incident may be closed by the assignee or an administrator.
36. If no technician is eligible, the incident stays CLASSIFIED (logged); an administrator can retry auto-assignment or assign manually.
37. Notifications: one stored row per channel. Users are not notified about their own actions (except the "incident received" confirmation). Failed deliveries are stored with `delivered=false` and the error text.
38. `incidents.sla_status` is a denormalised column (refreshed on every save and by the monitor) for fast filtering; the source of truth is the `IncidentSLA` domain object.
39. SLA targets are snapshotted into the incident at classification, so editing a policy does not move existing deadlines. A priority change re-reads the policy for the new priority and rebases deadlines on the original creation time.
40. Breach is strict (`now > due`); warning is inclusive (`elapsed >= threshold`). Each warning and each breach is reported once per target (response, resolution).
41. Passwords: 8-128 characters, at least one letter and one digit. Login returns the same error for unknown email, wrong password and deactivated account (no user enumeration; a dummy hash is verified for unknown emails to equalise timing).
42. JWT signature is verified by PyJWT; expiry is checked against the injectable `Clock` so it is testable. A token stops working if the user is deactivated or their role changes.
43. Round-robin cursor = id of the last auto-assigned technician (`system_settings`), updated by every automatic assignment.
44. Skill-based assignment does not fall back: if no skilled technician is free it raises `TechnicianUnavailableError` (admin may switch strategy or assign manually). Experience-based prefers skilled technicians and falls back to anyone eligible.
45. Reopen is only possible from RESOLVED (the reporter rejects the resolution); it clears `resolved_at`, and the resolution clock keeps running from the original start (minus any time paused in PENDING_INFO).
46. Feedback: once per incident, by the reporter, when RESOLVED/VERIFIED/CLOSED; `verify` can carry the rating directly.
47. Error-to-HTTP mapping: 401 authentication, 403 unauthorized operation, 404 not found, 409 invalid transition / conflict / assignment failure, 422 invalid input or missing SLA configuration, 502 notification delivery, 503 database failure. Body: `{"error": {"code", "message", "details"}}`.
48. All datetimes are normalised to UTC when loaded (SQLite returns naive values; PostgreSQL returns the session time zone).
49. Phase 1 HTTP surface is `/api/health` and `/api/auth/*`; all other routers arrive in Phase 2.
50. The `.ps1` script mirrors the `.sh` script but could not be executed here (no PowerShell on the dev machine).

## Phase 2 (API, search, dashboards, intelligence, monitor, seed)

51. **Duplicate thresholds recalibrated**: word-level TF-IDF scored the spec's own related payment examples at only 0.05-0.09, so the detector uses character n-grams (3-5, `char_wb`) and RELATED >= **0.18** (unrelated same-service tickets scored <= 0.04, related ones 0.19-0.34). DUPLICATE stays >= 0.85; the strongest duplicate becomes `parent_incident_id`. Evidence in `docs/ALGORITHMS.md`.
52. A category suggestion is computed for every report and stored as `suggested_category_id` (suggested vs chosen can be analysed). The reporter's choice always wins; with no choice and no suggestion >= 0.12 the report is rejected with "please choose a category".
53. Escalation level 1 fires as soon as the response deadline has strictly passed, then one level per response window. Levels are walked one at a time (each audited and notified). If unassigned, level 1 goes to system administrators. "Team Lead" = team leads in the assignee's team, falling back to any team lead.
54. P2 escalation is an administrator setting (default off) stored in `system_settings`.
55. Dashboards are computed in Python from the repositories. This is fine at demo scale; the report's scalability section explains moving them to SQL aggregates.
56. MTTR = mean(resolved_at - created_at) in hours over resolved incidents (paused time included). SLA compliance per priority = resolution target met / incidents whose resolution target is settled (resolved or already breached).
57. Search: the in-memory repository evaluates SLA status live; the SQL repository filters on the denormalised `sla_status` column, refreshed on every save and every monitor pass (at most about 60 s stale).
58. Search by number accepts "INC1005" or "1005"; free text is a case-insensitive substring match on title + description (wildcards escaped).
59. Technicians (staff) may view correlation, SLA risk, workload, recommendations and suggested resolutions; overview/service/SLA/trend reports and all `/api/admin` endpoints are administrator-only.
60. Technicians can toggle their own availability; administrators can change any technician profile.
61. Default (service-less) SLA policies cannot be deleted, only edited, so every priority always has an SLA; service overrides can be deleted.
62. Service dependencies must stay acyclic (depth-first search on every change).
63. Real-time: SSE messages are published only after a successful commit. Staff receive every incident event; other users only events for incidents they reported (or that escalate to them). The in-memory broadcaster assumes a single API process (multi-instance would need Redis pub/sub or Postgres LISTEN/NOTIFY).
64. Correlation: a hotspot is >= 3 open incidents on one service in the last 2 h; "upstream cause" looks one hop along the dependency graph.
65. Seed data is generated by replaying history through the services, relative to the seeding time; every demo account uses the password `Demo@1234`. Because times are relative, re-seed shortly before recording the demo.
66. The SLA risk score caps the elapsed contribution at 150 % so very late incidents remain comparable.
67. `POST /api/admin/sla/check-now` runs one monitor pass on demand (for the demo); the background monitor still runs every 60 s.
68. Code is formatted with ruff (120 columns); ruff is a dev tool only, not a project dependency.

## Phase 3 (frontend)

69. The UI calls the API through the Vite dev-server proxy (`/api` → `127.0.0.1:8000`), so the browser sees one origin (no CORS needed for the UI, and it is still restricted for direct calls). `ITSM_API_URL` overrides the proxy target.
70. Action buttons on an incident come from the backend's `available_actions`, which the domain computes (`Incident.available_actions`). The frontend holds no business rules beyond input hints, and the backend stays the authority.
71. A distinct GUI per role: its own navigation, home page, portal name and accent colour (employee blue, technician green, administrator violet). Shared screens (search, incident detail, notifications) adapt to the role.
72. Live updates use one SSE connection per signed-in session; pages refetch when a relevant event arrives. The notification bell also polls every 60 s as a fallback.
73. On any 401 (expired or revoked token) the app clears the token and returns to the login page.
74. Date filters use the user's local time zone and are converted to UTC day boundaries before calling the API.
75. No chart or component library: charts are CSS bars and inline SVG (fewer dependencies, as planned).
76. The login page has one-click demo-account buttons for the recorded demo; they use the published demo password.
77. Frontend stack verified on Node 26.13 / npm 11.20: React 19.3, React Router 8.5 (declarative mode), Vite 8.3, Tailwind 4.3, TypeScript 7.0 (native compiler), all exact-pinned with a lockfile.
78. UI verification is a headless-browser smoke test (Playwright, outside the project) that visits every page for every role, runs one full cross-role workflow and checks phone width (390 px). There are no automated frontend unit tests: the testing budget goes to the backend, where the business rules live.

## UI redesign (21 Nov 2026)

79. **Supersedes 71 (accent colour part).** All roles share one brand colour (petrol). Roles stay visibly distinct through their shell (sidebar console for technicians and administrators, top-bar portal for employees), portal name, navigation and a neutral role marker. Red, amber and green carry meaning only (priority, SLA, success).
80. Colours are semantic CSS tokens (`bg-surface`, `text-muted`, `border-line`, `bg-brand`, `text-critical` …) defined once in `src/index.css` with light and dark values; components never use raw Tailwind palette classes.
81. Theme follows the operating system by default; a System / Light / Dark toggle (sidebar footer, employee page footer, sign-in page) stores an explicit choice in `localStorage`, applied before first paint.
82. Fonts are IBM Plex Sans and IBM Plex Mono, self-hosted through `@fontsource` (latin subset) so the UI looks the same offline. These are the only two new dependencies.
83. The nine incident states share five colour tones (waiting, active, pending info, resolved, closed); the state name is always shown as text.
84. Icons are a small inline-SVG set (`components/icons.tsx`); no icon library.
85. Wide tables keep horizontal scrolling on phones, inside their panel (the page itself never scrolls sideways).
86. In staff incident lists the SLA badge and the next deadline share one column; "Created" is hidden below 2xl (1536 px) when deadlines are shown, because it is the least actionable column. It is always on the incident detail page.
87. On small screens the incident detail shows the SLA clocks directly under the actions; on desktop they sit in the side rail.
88. Redesign verification: `npm run build`, a headless Edge sweep of every page for all three roles in light and dark at 1440 / 1024 / 768 / 390 px (no console errors, no failed API calls, no horizontal page overflow), and one full cross-role workflow through the new UI.
89. Self-service fixes on the report form reuse the resolution suggester (same 0.15 similarity threshold, top 3). Employees see the past incident's title and fix only, never its id or number. Showing a tip never blocks submitting.
90. Predicted resolution time = median working time (resolved minus created, minus time paused waiting on the reporter) of resolved incidents with the same priority and category, falling back to the same priority. It needs at least 3 samples, otherwise no estimate is shown. It is visible to everyone who can view the incident, and it is advisory only: it never changes SLA deadlines.
91. A recurring problem = 3 or more incidents on the same service within 30 days, linked by TF-IDF similarity >= 0.25 (single-link), whose first and last are at least 24 h apart. It is visible to staff only (technicians and administrators) on the Service health page. It is a report, not a stored "problem record": nothing is created or changed in the database.
92. The seed gains one closed VPN incident (6 days ago), so the demo data contains a real recurring problem. That makes 43 incidents; category suggestion now matches 39 of 43.
93. Reporter ratings count towards the technician recommendation (10 %, taken from workload and service-history weight), credited to the technician assigned to the rated incident. Fewer than 2 ratings counts as neutral. Ratings only affect the explained recommendation, not the automatic assignment strategies.
94. Impact / urgency hints are English phrase rules kept in code (`severity_hints.py`), not admin-editable data like category keywords. They are a hint only: the server never changes the impact or urgency the reporter submits.
95. Voice reporting (innovation: "voice-based incident reporting") uses the browser's Web Speech API, in the browser's language. Each finished phrase is appended to the description; the first also fills an empty title. The button is hidden in browsers without the API (e.g. Firefox), and nothing changes on the server: a dictated report is an ordinary report. Audio privacy is covered in `SECURITY.md`.
96. CI runs on GitHub-hosted Ubuntu runners with the same versions as local development (Python 3.14, Node 26, PostgreSQL 18). The CI database password and JWT secret are throwaway values used only inside the runner, not real secrets. CI checks the code but deploys nothing: the system stays local, as the project requires.
