# SpendWise — Phase Notes

Design decisions and rationale, recorded phase by phase.

## Phase 1 — Foundation

**Async everywhere.** SQLAlchemy 2.0's async engine + `asyncpg` driver, FastAPI async
endpoints throughout. There's no sync fallback path — mixing sync and async DB access in
the same app is a common source of connection-pool bugs, so it's async-only from the start.

**UUID primary keys, not auto-increment ints.** Every table (starting with `users`) uses a
`uuid4` primary key stored as native Postgres `UUID`. This avoids leaking row counts /
signup order through IDs in URLs, and sidesteps ID collisions if data is ever merged across
environments.

**bcrypt directly, not passlib.** passlib's bcrypt backend has had long-standing
compatibility breaks against bcrypt 4.x (`AttributeError: module 'bcrypt' has no attribute
'__about__'`). Calling `bcrypt.hashpw`/`bcrypt.checkpw` directly removes that dependency
entirely.

**Access + refresh tokens, both JWT, both stateless.** `python-jose` signs both with
`SECRET_KEY`/HS256; the `type` claim (`access` vs `refresh`) is checked on every decode so a
refresh token can't be replayed as an access token. No server-side session/token store yet —
acceptable for a portfolio project, called out as a gap for Phase 5 hardening if there's time
(would need a revocation list to support real logout).

**Custom `AppException` hierarchy instead of raising `HTTPException` in services.**
Services (`auth_service.py`) raise domain errors (`ConflictError`, `UnauthorizedError`, ...)
with no knowledge of HTTP. A single exception handler in `main.py` maps them to responses.
Keeps services testable without spinning up FastAPI, and keeps routers free of `try/except`
noise — this is the "no business logic in routers" rule from the project conventions.

**`get_current_user` resolves against the DB on every request**, not just decoding the JWT
claims. Slightly more expensive per-request, but means a deactivated user (`is_active=False`)
is locked out immediately rather than waiting for their access token to expire.

**Alembic wired for async from the start** (`async_engine_from_config` +
`connection.run_sync`), reading `DATABASE_URL` from the same `Settings` object the app uses,
so migrations and the app can never point at different databases by accident.
