# Test cases

Run: `cd backend && .venv/bin/pytest` (64 test functions, 93 cases with parametrisation; all pass in under 1 s).
Types: **N** normal operation · **B** boundary · **I** invalid input · **E** exception · **A** authorization · **R** business rule · **S** state transition.

Fixture world (`tests/conftest.py`): services PAY (criticality 4), MAIL (3), WIKI (1); categories APPLICATION, NETWORK, DATABASE, HARDWARE;
PDF default SLA table; Employee E1 (reporter), technicians Asha (APPLICATION, 5 yrs), Nikhil (NETWORK, 10 yrs), Dia (DATABASE + APPLICATION, 2 yrs), two administrators.
Clock fixed at 2026-11-16 10:00 UTC and advanced explicitly.

## Domain unit tests (`tests/unit`)

| ID | Description | Input | Expected | Type |
|---|---|---|---|---|
| TC-01 | Priority score = impact x urgency x criticality | I=2, U=2, C=2, 1 user | score 8, P3, explanation shows formula | N |
| TC-02 | Priority band boundaries | scores 64, 32, 31.99, 16, 15.99, 6, 5.99, 1 | P1, P1, P2, P2, P3, P3, P4, P4 | B |
| TC-03 | Affected-users factor boundaries | 1, 10, 11, 100, 101 users | x1.0, x1.0, x1.25, x1.25, x1.5 | B |
| TC-04 | Many affected users promote priority | 3x3x3 with 10 vs 11 users | P2 (27) vs P1 (33.75) | R |
| TC-05 | Score capped | 4x4x4, 5000 users | 64, P1 | B |
| TC-06 | Invalid priority input | impact 0, urgency 5, impact `True`, 0 users | `InvalidInputError` | I/E |
| TC-07 | Full lifecycle walk (State pattern) | classify..close incl. info request | NEW to CLOSED in designed order | S |
| TC-08 | NEW to CLOSED rejected | `NewState.close()` | `InvalidStateTransitionError(NEW, close)` | S/E |
| TC-09 | Every state allows exactly its designed transitions (9 states) | each state x each of 10 actions | allowed set matches table, all others raise | S |
| TC-10 | Reopen | RESOLVED.reopen() | IN_PROGRESS | S |
| TC-11 | Service SLA policy overrides default | P1 default + P1 for service 7 | service 7 gets specific, others default | R |
| TC-12 | Missing SLA configuration | only a P1 policy, ask for P2 | `MissingSLAConfigurationError` | E |
| TC-13 | Deadlines from policy | P1 5/30 min | response +5 min, resolution +30 min | N |
| TC-14 | Breach is strict and reported once | evaluate at due, due+1 s, due+1 min | warning only, then one BREACH, then nothing | B |
| TC-15 | Warning at exactly 75 % | 20-min target at 14:59 / 15:00 | none / WARNING, status AT_RISK | B |
| TC-16 | Met vs late response | ack at 4 min / 6 min (5-min target) | MET / BREACH with 1 min overdue | R |
| TC-17 | Priority change keeps original start | P3 clock rebased on P1 policy | resolution due = start + 30 min | R |
| TC-18 | Invalid SLA policy | response 0; resolution < response; warn 100 % | `InvalidInputError` | I |
| TC-19 | Skill-based strategy | NETWORK incident, 4 candidates | least-loaded NETWORK tech (id 2) | N |
| TC-20 | Skill-based without skill | HARDWARE incident | `TechnicianUnavailableError` | E |
| TC-21 | Load-based strategy | same candidates | lowest load regardless of skill (id 3) | N |
| TC-22 | Round-robin rotates and wraps | last = none / 1 / 3 | 1, 2, 1 (4 is unavailable) | N/B |
| TC-23 | Experience-based strategy | NETWORK incident | most experienced *skilled* available (id 2) | N |
| TC-24 | Workload limit excludes technician | 3 active, max 3 | `TechnicianUnavailableError` | B/E |
| TC-25 | Strategy registry / Open-Closed | unknown key; new class registered in test | `InvalidInputError`; new strategy usable with no other change | R |
| TC-26 | UserFactory builds subclasses | roles EMPLOYEE / TECHNICIAN / "ADMINISTRATOR" | Employee / Technician / Administrator, email lower-cased | N |
| TC-27 | Polymorphic permissions | each role; deactivated admin | role-specific permission sets; none when inactive | A |
| TC-28 | Invalid user input | role SUPERUSER; email "not-an-email"; name "x" | `InvalidInputError` | I |
| TC-29 | Invalid incident | 2-char title; retired service | `InvalidIncidentError` | I/E |
| TC-30 | Event bus dispatch by class hierarchy | subscribe to `IncidentEvent` and `SettingChanged` | each handler gets only its events | N |
| TC-31 | Adapters translate provider failures | SMTP / SMS provider down | `NotificationDeliveryError`; working SMTP sends; no phone = no SMS | E |
| TC-32 | Channel selection policy | STATUS_CHANGED P1; ASSIGNED P1/P3; SLA_VIOLATED P4 | in-app only; +SMS only for P1; all three channels | R |

## Service tests (`tests/services`, in-memory repositories)

| ID | Description | Input | Expected | Type |
|---|---|---|---|---|
| TC-33 | Report payment outage | PAY, I=4, U=4, 50 users, APPLICATION | INC1001, P1 (64), deadlines +5/+30 min, assigned to Asha; audit CREATED, CLASSIFIED, PRIORITY_CALCULATED, ASSIGNED; tech gets in-app+email+SMS | N |
| TC-34 | Complete lifecycle | ack, start, note, request info, reply, resolve, verify(4 stars), close | CLOSED; 10 audited state changes in order; feedback stored; reporter notified of info request, resolution, closure | N/S |
| TC-35 | Role and ownership rules | employee acknowledges; non-assignee acknowledges; other employee views; technician assigns; unknown id | 403 x4 (`UnauthorizedOperationError`), `IncidentNotFoundError` | A/E |
| TC-36 | Illegal transition via service | resolve an ASSIGNED incident | `InvalidStateTransitionError` | S/E |
| TC-37 | Closing an unverified resolution | technician close; admin at +1 h; admin at +73 h | rejected, rejected, CLOSED with "admin override" note | R/B |
| TC-38 | Reporter rejects resolution | reopen with reason | IN_PROGRESS, resolved_at cleared | S |
| TC-39 | Technician unavailable / workload exceeded | all unavailable; manual assign unavailable tech; tech at max 1 | stays CLASSIFIED; `TechnicianUnavailableError`; `TechnicianWorkloadExceededError`; admin auto-assign later succeeds | E/R |
| TC-40 | Unknown service; missing SLA config | service 999; delete P4 default then report P4 | `ServiceNotFoundError`; `MissingSLAConfigurationError` and nothing persisted | E |
| TC-41 | Background SLA monitor | +4 min, +6 min, run twice | 1 warning, then 1 violation recorded once; BREACHED; admins notified on all channels | R |
| TC-42 | Late acknowledgement | ack at +7 min on P1 | RESPONSE violation recorded | R |
| TC-43 | Network failure during notification | SMTP down while reporting | incident still ASSIGNED; email rows `delivered=false` with error; in-app delivered | E |
| TC-44 | Priority recalculation on edit | MAIL P3 incident, urgency 1 to 4 | P2 (24), deadline from creation time, PRIORITY_CHANGED audited, assignee notified | R |
| TC-45 | Runtime strategy switch | employee sets LOAD; admin sets LOAD; unknown key | 403; next NETWORK incident goes to lowest-load tech (not the NETWORK tech); audited; `InvalidInputError` | A/R |
| TC-46 | Feedback rules | before resolution; rating 6; twice | `InvalidStateTransitionError`; `InvalidInputError`; `FeedbackAlreadySubmittedError` | R/I |
| TC-47 | Internal notes | tech adds internal + public note; employee adds internal | employee sees only the public one; employee internal note = 403 | A |
| TC-48 | Technician workload view | two incidents | Asha 1, Nikhil 0, Dia 1 | N |
| TC-49 | Register, login, authenticate | new employee | token resolves to same user; USER_CREATED audited | N |
| TC-50 | Weak passwords | "short1", "lettersonly", "12345678" | `InvalidInputError` | I |
| TC-51 | Duplicate email | existing email in different case | `EmailAlreadyRegisteredError` | E |
| TC-52 | Invalid login | wrong password; unknown email | `InvalidCredentialsError` (same error for both) | E/A |
| TC-53 | Deactivated account | login; reuse old token | both rejected | A |
| TC-54 | Token integrity and expiry | other key; tampered token; +60 min | `InvalidTokenError` each time | A/B |
| TC-55 | Argon2 hashing | hash same password twice | different salted `$argon2id$` hashes, verify works, garbage hash is false | N |

## API and persistence tests (`tests/api`, FastAPI + SQLAlchemy on SQLite; also run on PostgreSQL via `ITSM_TEST_DATABASE_URL`)

| ID | Description | Input | Expected | Type |
|---|---|---|---|---|
| TC-56 | Health check | GET /api/health | 200 `{"status":"ok","database":"up"}` | N |
| TC-57 | Register, login, me | POST register, POST login, GET me | 201, 200 + JWT, 200 role EMPLOYEE code E1 | N |
| TC-58 | Invalid login over HTTP | wrong password | 401 `INVALID_CREDENTIALS` | E |
| TC-59 | Missing / bad token | no header; "Bearer not.a.jwt" | 401; 401 `INVALID_TOKEN` | A |
| TC-60 | Token lifetime | +61 min | 401 | B |
| TC-61 | Invalid input and duplicate registration | email "nope"; password w/o digit; same email twice | 422 `INVALID_INPUT`; 422 mentions digit; 409 `EMAIL_ALREADY_REGISTERED` | I |
| TC-62 | CORS restricted | preflight from localhost:5173 and evil.example | allowed / no CORS header | A |
| TC-63 | SQL repositories round trip | report, ack, start, internal note, SLA check at +42 min, reload in new session | state, priority, SLA flags, comments, audit, violation, workload, service dependency and technician skills all preserved | N |
| TC-64 | Database failure | two services with the same code | `PersistenceError` | E |

## Spec exception coverage

| Spec situation | Exception | Test |
|---|---|---|
| Invalid login | `InvalidCredentialsError` | TC-52, TC-58 |
| Unauthorized operation | `UnauthorizedOperationError` | TC-35, TC-45, TC-47 |
| Invalid incident | `InvalidIncidentError` | TC-29 |
| Invalid state transition | `InvalidStateTransitionError` | TC-08, TC-09, TC-36, TC-37 |
| Technician unavailable | `TechnicianUnavailableError` | TC-20, TC-24, TC-39 |
| Technician workload exceeded | `TechnicianWorkloadExceededError` | TC-39 |
| Service not found | `ServiceNotFoundError` | TC-40 |
| Missing SLA configuration | `MissingSLAConfigurationError` | TC-12, TC-40 |
| Duplicate incident | `DuplicateIncidentError` | Phase 2 (duplicate detection) |
| Database failure | `PersistenceError` | TC-64 |
| Network failure | `NotificationDeliveryError` | TC-31, TC-43 |
| Invalid user input | `InvalidInputError` | TC-06, TC-18, TC-28, TC-50, TC-61 |
