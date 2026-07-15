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

## Phase 4 — Advisor & alerts

**Budget alerts key off `(budget_id, threshold)`, not `(budget_id,)`.** A `Budget` row is
already scoped to one category+month, so this constraint means each of the 80%/100%
thresholds fires its email exactly once per budget, ever — checked via a plain `SELECT`
before insert rather than a `try/except IntegrityError` race, since alert checks happen
inline after a single user's own write (no concurrent-write risk to guard against here).
Only the *highest* threshold crossed in one pass emails (checked 100 before 80) so pushing an
expense that jumps a category straight past 100% doesn't send two emails back to back.

**Alert checks run on manual expense writes, not on bulk CSV import.** `create_expense` and
`update_expense` call `check_and_trigger_alerts`; `import_service.import_csv` inserts `Expense`
rows directly and does not. Importing a year of bank history would otherwise fire a wall of
threshold-crossing emails for old, already-known spending — alerts are for *new* spending
decisions, not retroactive ones.

**LLM advisor talks to OpenAI/Gemini over raw `httpx`, not their SDKs.** Both providers
implement one `LLMProvider.ask(system_prompt, question) -> str` interface
(`app/services/llm/`), so swapping providers is a one-line change in `get_llm_provider()` and
the app doesn't carry two heavyweight SDK dependencies for what's ultimately one JSON POST
each. A `NullProvider` is the fallback when no API key is set — it returns the grounded data
summary itself instead of erroring, so `/advisor/ask` stays useful (and honest about not
having a real model behind it) with zero config.

**The advisor is only as grounded as the prompt.** `advisor_service.build_spending_summary`
assembles real numbers (3-month trend, this month's category breakdown, top merchants,
budget status) into the system prompt and instructs the model not to invent figures — but
this is a prompt-level constraint, not a hard guarantee. Documented here as a known limitation
rather than something Phase 4 claims to have solved.

**Savings goal "progress" is a projection, not a ledger.** SpendWise has no bank/savings
account integration, so there's no actual "amount saved" to read. Progress is estimated as
`(monthly_income − recent 3-month average expense) × months remaining until deadline`,
which needs `monthly_income` to be set (`PATCH /auth/me`) to produce anything other than zero.
This is called out explicitly in the API response (`estimated_monthly_savings`,
`avg_monthly_expense` are both returned) so the projection's inputs are visible, not hidden
behind a single confident-looking percentage.

**PDF reports use reportlab's Platypus layer (`SimpleDocTemplate` + `Table`), not raw
canvas drawing.** Platypus handles page breaks and table layout automatically — a category
breakdown or budget table that overflows one page just continues on the next, which
raw `canvas.drawString` coordinate placement doesn't give you for free.

## Phase 5 — Quality & ship

**Tests share one schema per test session, not a fresh rollback-per-test transaction.**
`tests/conftest.py` creates all tables once (session-scoped, `Base.metadata.create_all`) and
each test gets its own `db_session` but writes really commit. Isolation instead comes from
every fixture and test creating a fresh randomly-named user (`user_<uuid4>@example.com`) —
since every table is owner-scoped, tests can't see each other's data even though the schema
persists across the run. This is simpler than the savepoint/nested-transaction pattern and
was sufficient for "important paths, not 100% coverage" per the brief; a slower but more
isolated setup is a reasonable Phase 6 upgrade if the suite grows.

**A real Python-version bug was caught during this phase, not left latent:** `ExpenseBase`
had a field literally named `date` typed `date` (`date: date`). Under Python 3.14's deferred
annotation evaluation (PEP 649/749), a class attribute name shadowing its own type name in
the same class body broke forward-reference resolution (`TypeError: unsupported operand
type(s) for |: 'NoneType' and 'NoneType'`) — invisible on Python 3.12 (this project's target,
which evaluates annotations eagerly) but a real landmine for anyone who runs it on newer
Python later. Fixed by aliasing the import (`from datetime import date as date_`) everywhere
a field shares a name with the `datetime.date` type, matching the pattern the models already
used. Caught by actually booting the app and hitting `/openapi.json` — a `python -m
py_compile` syntax check does not catch this class of error, since the annotation is valid
syntax and only fails at class-construction / schema-generation time.

**`DATABASE_URL` normalizes `postgresql://` to `postgresql+asyncpg://` in `Settings`
(`app/core/config.py`).** Render's `fromDatabase.property: connectionString` (used in
`render.yaml`) hands out a plain `postgresql://` URL; without this normalization the app
would fail to boot in production with a driver-not-found error that has nothing to do with
the actual config mistake. Caught before deployment rather than after, by reading what
Render's env var injection actually produces.

**Verified against a real PostgreSQL instance, not just SQLite-shaped assumptions.** All 8
tables were autogenerated correctly via `alembic revision --autogenerate`, the migration
applied cleanly, and all 36 tests plus a manual curl-driven pass through signup → income →
expense → savings-goal projection → LLM-advisor fallback → CSV export → PDF export ran
against it end-to-end. This matters because several features (native `UUID` columns,
`extract()`-based analytics, case-insensitive `ILIKE` category lookups) are genuinely
Postgres-specific and would have given false confidence if only smoke-tested against SQLite.

**CI runs lint and tests as separate jobs** (`.github/workflows/ci.yml`) so a lint failure and
a test failure are distinguishable in the Actions UI rather than one job dying at whichever
step comes first. The test job spins up a real `postgres:16-alpine` service container — the
same asyncpg-specific behavior above would silently not be exercised by a mocked or
in-memory DB in CI either.

**Dockerfile is multi-stage and runs as a non-root user.** The builder stage installs
dependencies with `pip install --user`; the runtime stage copies only the resulting
`~/.local` site-packages and the `app`/`alembic` source, not the build toolchain
(`build-essential`) — keeping the shipped image smaller and reducing its attack surface. The
container's `CMD` runs `alembic upgrade head` before starting `uvicorn`, so a fresh deploy
never serves traffic against an unmigrated schema.

## Phase 6 — Web UI

**Vanilla HTML/CSS/JS, no build step, no framework.** `frontend/` is three plain files
(`index.html`, `css/styles.css`, `js/{api,charts,app}.js`) plus one giant single-page shell —
no npm, no bundler, no node_modules. For a project this size that's a feature, not a
shortcut: it deploys as static files FastAPI already knows how to serve, there's nothing to
break between "works on my machine" and "works in Docker," and every line is inspectable
without a build step standing between the source and what ships.

**Served by FastAPI itself, same-origin, mounted last.** `app.main` mounts
`StaticFiles(directory="frontend", html=True)` at `/` — but only *after* every `/api/v1/*`
router and `/health` are registered, because Starlette matches routes in registration order
and a root-level `Mount` would otherwise shadow everything. Same-origin means the frontend's
`fetch("/api/v1/...")` calls never touch CORS at all — one deployable service, one URL, no
cross-origin token-passing to get wrong.

**Brand chrome (navy/beige/gold) is deliberately separated from chart data color.** The
dataviz skill's rule is "compute the palette, don't eyeball it" — so `chart-*` CSS custom
properties in `styles.css` reuse the skill's pre-validated, colorblind-safe blue
sequential/categorical hues for actual data encoding (trend line, bars, chart dots), while
brand navy/gold/beige is reserved for UI chrome (nav, buttons, cards). Budget status
(good/warning/critical) uses the skill's fixed status palette for the same reason — a status
color is never allowed to double as a series color, and I didn't want to hand-guess whether a
gold progress bar was distinguishable enough from a critical-red one.

**Category-breakdown and top-merchants "charts" are direct-labeled horizontal bar lists, not
a pie/donut.** A magnitude comparison across up to 10 categories is exactly the case the
dataviz skill flags against rainbow categorical pies — instead every bar carries its own
label and value, so identity never depends on distinguishing similar hues, and a user with 10
categories doesn't need a legend to read it.

**JWT refresh is transparent to the rest of the frontend.** `api.js`'s `request()` catches a
401, attempts one silent `/auth/refresh` (de-duplicated via a shared in-flight promise so
five simultaneous 401s don't fire five refresh calls), retries the original request once, and
only then gives up and fires `sw:unauthorized` to force a re-login. No view code — expenses,
budgets, goals, anything — has to know tokens can expire mid-session.

**Budgets view shows every category, not just budgeted ones.** `loadBudgets()` diffs the
user's full category list against this month's `Budget` rows and renders an inline "Set
budget" prompt for anything missing, pre-filling that category in the form. The alternative
(only showing categories that already have a budget) would hide the exact information a
budgeting app exists to surface: *what haven't I budgeted for yet*.

**File upload is a real native `<input type="file">`, not a JS-managed drag-drop widget.**
`import_service.import_csv` already does all the real work (parsing, categorizing, skip
reasons); the frontend's only job is to hand it a `FormData` blob and render the returned
summary. Reinventing file-picker UI would be complexity with no payoff here.

**Known gap, called out rather than hidden:** there's no client-side route guard beyond
`bootApp()` checking for a token on load — a user who never logs in only ever sees the auth
screen because `#app` stays `.hidden`, but there's no deep-linking (e.g. `/expenses` as a
real URL) since the whole app runs as view-toggling under a single `/` route. Fine for a
portfolio project's scope; a real product would want `history.pushState`-based routing so
back/forward and shareable URLs work.
