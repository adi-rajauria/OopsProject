# Security

| Requirement (spec) | Implementation | Code |
|---|---|---|
| Authentication | JWT (HS256, PyJWT); 60-minute access token; signature, `exp`, `sub` and `role` are required; a token stops working if the account is deactivated or its role changes | `core/security.py`, `services/auth_service.py` |
| Password protection | Argon2id (argon2-cffi, salted, memory-hard); policy: 8–128 characters with at least one letter and one digit; hashes never leave the server | `core/security.py`, `auth_service.validate_password` |
| Role-based authorization | Two layers: (1) a route guard on every endpoint, `Depends(require(Permission.X))` or an authenticated `CurrentUser`; (2) domain rules on every operation (only the assignee acknowledges/resolves, only the reporter verifies, employees only see their own incidents, internal notes hidden from employees) | `core/deps.py`, `domain/incident.py`, `domain/users.py` |
| Input validation | Pydantic models at the HTTP boundary (lengths, ranges, enums); domain constructors re-validate (defence in depth); all SQL goes through SQLAlchemy bound parameters; search text uses `contains(..., autoescape=True)` | `api/schemas.py`, `domain/validation.py` |
| Secure API access | CORS limited to the Vite origin; only the `Authorization` and `Content-Type` headers allowed; the error envelope never leaks stack traces (unexpected errors → generic 500 + server log) | `main.py`, `core/errors.py` |
| Unauthorized operations | `UnauthorizedOperationError` → 403; `InvalidTokenError` / `InvalidCredentialsError` → 401 with `WWW-Authenticate: Bearer` | `core/errors.py` |
| No secrets in code | JWT secret and DB URL come from `backend/.env` (gitignored); the app refuses to start with a secret shorter than 32 characters | `core/config.py`, `.env.example` |
| CSV / formula injection | Exported cells that start with `=`, `+`, `-`, `@`, tab or CR get a leading apostrophe, so a title like `=HYPERLINK(...)` is shown as text instead of running as a formula in Excel. Exports use the same visibility rules as search (an employee only exports their own incidents) and need a valid token | `api/csv_export.py` |
| Auditability | Every state change, admin action and login-relevant account change is recorded append-only with actor, timestamp, previous and new state | `observers/audit_logger.py` |

## Deliberate trade-offs (documented, not hidden)

- **Token in `localStorage`** (frontend): simple, but readable by injected scripts if an XSS bug existed. Mitigations:
  React escapes output by default, no `dangerouslySetInnerHTML`, short token lifetime. Production alternative: an
  httpOnly SameSite cookie plus a CSRF token.
- **SSE token in the query string** (`/api/stream/events?token=…`): the browser `EventSource` cannot send headers. The
  token can end up in server access logs. Production alternative: a short-lived, single-use stream ticket.
- **No refresh tokens or rate limiting**: the user simply logs in again after 60 minutes. Brute force is slowed only by
  Argon2's cost. Production: rate-limit `/api/auth/login` per IP and account, and lock out after repeated failures.
- **No account enumeration**: the same error and the same hashing cost apply to unknown emails, wrong passwords and
  deactivated accounts.
- **Simulated e-mail/SMS**: no real credentials are needed; providers are adapters, so real ones (with secrets in env)
  can replace them.
- **Voice reporting uses the browser's speech service**: when the browser has an on-device speech model (newer Chrome /
  Edge, experimental `processLocally`), recognition runs on the computer and no audio leaves it. Otherwise, dictated audio
  is sent to the browser vendor's cloud speech recognition (Google / Microsoft), not to our server. It only runs after the employee clicks
  "Speak instead" and the browser asks for microphone permission; typing remains the default. Production alternative
  for sensitive environments: an on-premise speech-to-text service behind the same hook.
- **Self-registration** always creates an Employee; only administrators can create technicians or administrators.
