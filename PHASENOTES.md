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

## Phase 2 — Core domain

**Default categories are real per-user rows, not a shared global table.** The spec calls for
"sensible defaults seeded per user" — seeding 10 `Category` rows (flagged `is_default=True`)
at signup, rather than a nullable `owner_id` "global category" concept, keeps every query a
single `WHERE owner_id = :user_id` with no special-casing, and lets a user freely rename or
delete a default category without affecting anyone else.

**Categories can't be deleted while expenses reference them.** `delete_category` checks for
any `Expense` row pointing at the category first and raises `ConflictError` — a hard 409, not
a silent cascade. Losing the category label on historical spending data silently would make
past analytics wrong without any signal to the user.

**Budgets are a separate `(owner, category, year, month)` row, not a field on `Category`.**
Storing `year`/`month` as plain ints instead of a `first-of-month` date keeps the uniqueness
constraint and querying simple (`year=2026, month=7`) without timezone-boundary edge cases
that a `DATE` column would introduce.

**"Spent vs budget" is computed on read, not stored.** `BudgetRead` is a hand-built Pydantic
model (not `from_attributes` off the ORM row) because `spent`/`remaining`/`percent_used`
don't exist as columns — they're a `SUM(amount) WHERE category, year, month` query run at
response time via `budget_service._compute_spent`. Always correct, no risk of a stored
running total drifting from the underlying expenses after an edit or delete.

**Recurring expenses use a catch-up loop, not a single materialize-and-done.** If the app (or
its scheduler) is offline past a rule's `next_run`, `materialize_due_expenses` creates one
`Expense` per missed cycle and advances `next_run` each time, capped at 366 iterations so a
stale daily rule can't spin forever. `relativedelta` (not fixed-day `timedelta`) handles
monthly/yearly cadence so a rule anchored on the 31st doesn't drift across shorter months.

**APScheduler over Celery**, per the spec — this workload is a single recurring background
job (materialize due expenses hourly), not a distributed task queue. `AsyncIOScheduler` runs
in-process inside the FastAPI event loop via the `lifespan` context, with its own
`AsyncSessionLocal()` session per run since it executes outside request scope.

## Phase 3 — Import & analytics

**CSV parsing is split from import orchestration.** `csv_parser.py` only knows about bytes,
encodings, header aliases, and date/amount string parsing — it has no idea what an `Expense`
is. `import_service.py` owns the business decisions (skip a credit row, fall back to "Other",
what counts as a valid amount). This split is what makes "handles messy headers/encodings"
testable in isolation: a `parse_amount("(1,234.50)")` unit test doesn't need a database.

**Encoding detection tries a fixed list, not `chardet`/`charset-normalizer`.** UPI/bank export
CSVs are overwhelmingly `utf-8-sig` (Excel's BOM-prefixed UTF-8) or `cp1252`/`latin-1`
(legacy Windows exports with rupee symbols or accented merchant names). Trying four known
encodings in order and taking the first clean decode is simpler and faster than a statistical
detector, and covers what these exports actually look like in practice.

**Header detection is alias-set matching, not fuzzy string matching.** Bank exports vary
("Txn Date" vs "Value Date" vs "Date", "Narration" vs "Particulars") but the vocabulary is
small and known. A hardcoded alias set per logical column is predictable and debuggable — a
fuzzy-match/similarity-score approach would occasionally guess wrong in a way that's hard to
explain to the user.

**Debit/credit split columns are handled, and credit-only rows are skipped, not imported as
negative expenses.** Indian bank statements commonly report `Withdrawal Amt.`/`Deposit Amt.`
as two columns rather than one signed `Amount`. A credit row is income, not spending — SpendWise
tracks expenses, so those rows are counted in `rows_skipped` with an explicit reason rather
than silently dropped or wrongly imported as a expense.

**Auto-categorization checks learned overrides before the global keyword map, and the
longest matching keyword wins among overrides.** Per-user `CategoryKeywordRule` rows are
written automatically whenever a user changes an expense's category via `PATCH
/expenses/{id}` (see `expense_service.update_expense` → `categorizer.learn_override`) — no
separate "teach me" endpoint needed, the correction *is* the training signal. The global
map (`GLOBAL_KEYWORD_CATEGORY_MAP`) is deliberately Indian-market-flavored (Swiggy, Zomato,
IRCTC, BigBasket, ...) since that's this project's target user base.

**Analytics are pure SQL aggregations (`GROUP BY` + `func.sum`/`func.count`/`extract`), never
a Python loop over fetched rows** — required by the spec, and it's also just correct: pushing
the aggregation to Postgres means the app never pulls a user's full expense history into
memory to compute a monthly trend.
