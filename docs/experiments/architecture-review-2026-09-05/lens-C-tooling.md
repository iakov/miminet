# Lens C (Tooling + Framework) review — whole miminet server stack (2026-09-05)

## Question under review

Maintainer hypothesis: "probably Flask is not the best solution for the current server."
Lens C scope: strict, evidence-based framework/tooling fit for THIS repo's real usage,
plus the tooling posture around it (uv workspace, ruff/ty gates, Selenium-e2e vs
browser-free-unit gap, front coverage infra gap), and whether FastAPI / another
WSGI/ASGI stack would be a better fit for a future non-browser (Android-like) client.

## Verified evidence

Route inventory (79 `add_url_rule`/`@app.route` registrations in `front/src`, incl.
the `image_routes` blueprint; app.py registration block `front/src/app.py:256-405`,
decorated routes `app.py:505-634`). Classified by the view functions actually read:

- HTML/redirect/sitemap (page-render or flash+redirect flows): `/`, `/home`, `/course`,
  `/information/consent`, `/examples`, `/sitemap.xml`, `/config.js` (JS),
  `/auth/login.html`, `/user/profile.html`, `/profile`, `/profile/<id>`, `/auth/logout`,
  social-login endpoints + callbacks, `/create_network`, `/delete_network` (POST is a
  redirect, `miminet_network.py:111-141`), `/web_network`, `/web_network_shared`,
  `/host|router|server|hub|switch/mimishark`, `/ai/generate-task` SUCCESS path returns a
  redirect to the new network page (`ai_generate.py:617`), and the quiz page renders
  `quiz/quiz.html`, `quiz/quizzes.html`, `quiz/sessionQuestion.html`,
  `quiz/userSessionResult.html`, `quiz/sessionResult.html`
  (`section_controller.py:58`, `test_controller.py:58`, `quiz_session_controller.py:84,138,155`).
- JSON/API-shaped: `/network/update_network_config`, `/post_network_nodes`,
  `/post_nodes_edges`, `/move_network_nodes`, `/network/upload_network_picture`,
  `/network/copy_network`, `/user/animation_filters`, `/run_simulation`,
  `/check_simulation`, `/emulation_queue/size|time`, 7× `/host|edge/*save_config`,
  `/host/delete_job`, `/refresh_access`, and the ~17 quiz JSON endpoints
  (`/quiz/test/*`, `/quiz/question/*`, `/quiz/session/*`, `/quiz/user/session/result`,
  `/quiz/images/upload`) plus blueprint `/quiz/upload`, `/quiz/images/<filename>`.
- **~10 quiz controller endpoint functions are defined but never URL-registered**
  (`create_test_endpoint`, `delete_test_endpoint`, `edit_test_endpoint`,
  `get_deleted_tests_by_owner_endpoint`, `get_tests_by_author_name_endpoint`,
  `publish_or_unpublish_test_endpoint` in `test_controller.py:23,79,95,124`;
  `create_section_endpoint`, `get_section_endpoint`, `delete_section_endpoint`,
  `edit_section_endpoint`, `publish_or_unpublish_test_by_section_endpoint` in
  `section_controller.py:22,40,78,92,112`). Nothing in app.py imports them; the admin
  uses services directly (`miminet_admin.py`). Dead-over-HTTP, but they are plain
  functions = free browser-free unit targets.

Concurrency reality:
- `front/src/uwsgi.ini`: `module = app:app`, `processes = 5`, `socket = :80`,
  `harakiri = 300`, `http-timeout = 300`, `enable-threads = true` with NO `threads = N`
  → effective HTTP concurrency ≈ 5 (one request per process).
- `front/run_app.sh:7-13`: one-shot `python3 app.py "$MODE"` (init_db + test-user
  cleanup, `app.py:637-646`), then `nohup uwsgi --ini /app/uwsgi.ini &`, then
  `exec python3 -m celery -A celery_app worker ... -Q common-results-queue,task-checking-queue`.
  → uwsgi AND a celery worker share ONE front container/process tree and one app image.
- Front celery concurrency=4 (`front/.env` `celery_concurrency=4`); back container runs
  the real emulation worker (`back/ENTRYPOINT.sh`; `back/src/tasks.py:121
  mininet_worker`; front only enqueues + consumes results: `miminet_simulation.py:57-65`,
  `front/src/celery_app.py:28-39` queues, `front/src/tasks.py:19-61,64-128`).
- Long emulation is already offloaded to celery. The slow work left in HTTP handlers is
  **`/ai/generate-task`**: up to 3 attempts of blocking urllib LLM calls with 60–120 s
  timeouts (`ai_generate.py:225,261,285`; retry loop `ai_generate.py:519-553`),
  synchronous inside a uwsgi worker. nginx special-cases `/ai/` with
  `uwsgi_read_timeout 300` (`front/default.conf.template`), uwsgi `harakiri = 300`.
  Worst-case 3×120 = 360 s > 300 s → possible harakiri kill; 5 concurrent AI requests
  saturate the whole HTTP pool. `tasks.py` (front celery) ALSO blocks up to 120 s inside
  a front worker on a nested emulation (`tasks.py:139-151`) — that is celery-side, fine.
- Everything else in the request mix is DB CRUD (psycopg2 → postgres), small JSON
  file/static IO, Pillow image validation, or enqueue-and-poll — none of it long-running
  in the HTTP worker.

Coupling that a framework change must carry:
- Celery tasks import the whole Flask app: `tasks.py:7 from app import app as flask_app`
  and run queries under `flask_app.app_context()` (`tasks.py:23,127`). Flask handlers
  import the celery app + use `app.control.revoke` (`configurators.py:7`, `:215`). The
  two serving planes (HTTP + front-celery) are mutually import-coupled through the
  module-level Flask app object.
- `app.py` import-time side effects: `app = Flask(...)` (`app.py:120`), `db.init_app`,
  `Migrate(app, db)`, `login_manager.init_app`, `JWTManager(app)` (`app.py:244-251`),
  `Admin(app, ...)` + 8 `add_view(... db.session)` (`app.py:408-428`), `CORS(app)`
  (`app.py:150`). Any process (uwsgi OR celery OR a unit test) that imports `app`
  builds all of this.
- Template layer is framework-bound: 32 Jinja `.html` + `.xml` templates, a
  `@app.context_processor` for `organization_url_for` (`app.py:463`), `url_for`/`flash`
  everywhere, `render_template_string` for `config.js` (`app.py:512`).
- Extension stack + ASGI parity: flask-sqlalchemy 3.1.1, flask-login 0.6.3,
  flask-jwt-extended 4.7.1, flask-migrate 4.1.0 (wraps alembic, already a direct dep),
  flask-cors 6.0.2, flask-admin 2.0.1 (+ wtforms 3.2.1 direct dep; 820-line custom
  `miminet_admin.py` of ModelViews/actions/forms bound to `db.session`). flask-admin has
  no first-class ASGI equivalent; a port means building a CRUD admin or keeping Flask.
- Auth is DUAL: flask-login session (`SESSION_COOKIE_NAME=mimi_session`,
  `login_manager`) for `@login_required` page flows, AND flask-jwt-extended with
  `JWT_TOKEN_LOCATION=["cookies"]` (`app.py:131`) for `@jwt_required` JSON handlers.
  `is_api_request()` (`app.py:468-478`) only gates JWT-error responses between JSON and
  redirect. A native client today cannot use these JWT endpoints with a Bearer header
  without a config change (`["cookies","headers"]`) — a framework-independent config,
  not an ASGI problem.
- Prod serving/deploy topology: nginx container → `uwsgi_pass miminet:80`
  (`front/default.conf.template`); uwsgi is **not in uv.lock** — it is
  `pip install wheel uwsgi uv` in the image (`front/Dockerfile`), `uwsgi.ini` points
  `virtualenv=/app/.venv`; deploy = ansible → `docker compose -f back/... -f
  front/docker-compose.staging.yml up -d --build` (`ansible/miminet_back_1.deploy`);
  dev on rootless podman.

Tooling posture:
- uv single-lock workspace (root `pyproject.toml` `[tool.uv.workspace]` members
  back,front; verified single uv.lock). Front dev group (`front/pyproject.toml`):
  pytest, pytest-mock, pytest-timeout, selenium, isort, mypy, types-requests, wheel,
  ruff, ty. **coverage is NOT in front dev group** (it is back-only:
  `coverage>=7.16.0` in `back/pyproject.toml`). uv.lock already resolves coverage
  7.16.0 (for back) → adding the same spec to front dev is a clean single-lock change.
- CI gates: `linter.yml` runs `ty check`, `ruff format --check`, `ruff check` for
  back+front. **mypy and isort are in both dev groups but no workflow invokes them.**
- Coverage precedent to model: `back_test.yml` 3-shard matrix runs
  `python -m coverage run --branch --source=../src --data-file=".coverage.shard${SHARD}"`,
  merges shards, asserts full shard count, then `coverage report --fail-under=75`
  (comment: gate at measured whole-suite baseline 76.15% rounded down), uploads
  coverage.json with `include-hidden-files: true`. raw coverage CLI, NOT pytest-cov.
- Tests: `full_test.yml` boots the compose app + selenium grid per shard and slices
  `find front/tests -maxdepth 1 -name "test_*.py"` into 3 shards (~6+ min, flake-prone).
  **Only 4 of 26 e2e files are browser-free** (no selenium/chrome/requester usage):
  `test_get_logs.py` (stubs `execute`), `test_config_db.py` (imports `app`, mocks
  psycopg2/init_db — proves `import app` succeeds without a DB),
  `test_quiz_progress.py` (pure `quiz/util/dto`), `test_ai_generate.py` (pure
  `_fix_topology`/`_validate_topology`). W5 measured 27% branch coverage of front/src
  from the e2e suite. `front/tests/pytest.ini`: `addopts = -vv -s`, `timeout = 300`.
- W5/decision 2026-09-04: keep Selenium e2e; targeted Playwright only.
- Dependency-review gates CVE bumps in changed manifests incl. uv.lock; Flask 3.1.3
  already the pinned clean version. requirements.txt is dead on main (uv migration) —
  never reintroduce.
- Hygiene: `back/.env` and `front/.env` are TRACKED in git (`git ls-files`) although
  `.gitignore:15` ignores `.env` (they predate the rule / were force-added). Values
  should be verified dev-only (not printed here).

## Findings

- **F1 (ADJUST — keep the framework): Flask+uwsgi is a fit for the actual workload; no
  evidence ASGI would buy measurable throughput.** Evidence: long work is offloaded to
  celery; the HTTP mix is DB CRUD + page renders + enqueue/poll; effective HTTP
  concurrency today is ~5 (uwsgi.ini) at classroom scale, and no latency/QPS problem is
  recorded anywhere in the repo. Raising `processes`/`threads` is the cheap lever.
  "Flask is not the best solution" is not supported by route mix or concurrency for the
  CURRENT server. Cost/benefit of a full FastAPI port is detailed in Option B below.
- **F2 (ADJUST): the one genuinely mis-fitted endpoint is `/ai/generate-task`** — a
  multi-minute blocking LLM call (3× up to 120 s) inside a 5-worker WSGI pool, running
  against `harakiri=300` / nginx `/ai/` timeout 300 (`front/default.conf.template`),
  theoretical worst case 360 s. Fixes, cheapest first, all framework-agnostic:
  (a) offload to the existing front celery worker (run_simulation→check_simulation poll
  pattern already exists), (b) raise uwsgi processes, (c) only under ASGI would an async
  HTTP-client rewrite apply. This is where the maintainer's instinct has real substance,
  but the fix is NOT a framework swap.
- **F3 (ADJUST → gates the 85% aim): front coverage infra gap.** coverage is back-only;
  the browser-free tests exist (4 files) but only run inside the expensive grid-booted
  e2e matrix, and no coverage number is produced for front/src. Wiring model (mirror
  back_test.yml coverage job, raw coverage CLI not pytest-cov):
  1. `front/pyproject.toml` `[dependency-groups].dev` += `"coverage>=7.16.0"`; `uv lock`
     (coverage wheel already resolved → minimal churn).
  2. New small workflow/job (no matrix, no compose, no grid), model on linter.yml:
     `uv sync --frozen` (or `--project front`), then from `front/tests`:
     `python -m coverage run --branch --source=../src -m pytest <explicit browser-free
     file list>` + `python -m coverage report --fail-under=<N>` and upload
     `coverage.json` (`include-hidden-files: true`).
  3. Fail-under N set AFTER measuring the baseline once (back precedent: measured
     76.15 % → gate 75). The e2e suite stays as-is (decision 2026-09-04); the unit tier
     grows the browser-free file list as seams land (lens B). Keep the 4 files in the
     explicit list; optionally remove them from the full_test matrix afterwards
     (watch the round-robin slice counts / empty-slice guard, §7 guardrails).
- **F4 (NICE-TO-HAVE): dormant dev deps.** mypy and isort sit in both dev groups but no
  CI job runs them (linter = ty + ruff only); isort's style philosophy conflicts with
  ruff-format. Prune or wire. (types-requests likely feeds ty/requests stubs — verify
  before removing.)
- **F5 (NICE-TO-HAVE): redundant CORS machinery.** flask-cors
  `CORS(app, ... intercept_exceptions=False)` (`app.py:150`) + a hand-rolled
  `@app.after_request add_cors_headers` (`app.py:165-180`) + a per-handler
  `CORS_header()` (`miminet_network.py:25-27`) applied in ~7 handlers. Three mechanisms
  for one job; consolidate to one.
- **F6 (NICE-TO-HAVE): uwsgi is outside the lock.** Image `pip install wheel uwsgi uv`
  floats uwsgi; reproducibility would improve by pinning it (or accepting image-layer
  pinning explicitly). uv itself stays a build-time tool (fine).
- **F7 (NICE-TO-HAVE): `.env` files tracked in git** despite `.gitignore:15` — verify
  contents are dev-only defaults, then either git-rm --cached or delete the ignore
  line's ambiguity.
- **F8 (ADJUST, low): unrouted quiz controller endpoints.** ~10 JSON endpoint functions
  defined but never URL-registered (see evidence). Either prune them or (better) treat
  them as the first browser-free coverage targets — they are pure functions over
  request.json/request.args + services, needing only request mocks for validation paths.
- **F9 (coupling to watch, lens-B material): celery ↔ Flask import coupling.**
  `tasks.py` imports the module-level Flask app and wraps DB work in
  `flask_app.app_context()`; this forces every celery process to build the full Flask
  app (admin/CORS/JWT). It is the single biggest cost driver of any future framework
  migration AND of clean browser-free celery tests. If lens B's seam work decouples the
  DB session from the app context, this shrinks both problems at once.

## Option comparison

- **Option A — KEEP Flask 3.1.3 + uwsgi** (status quo + F2 fix + coverage wiring).
  Cost: near zero for keep; F2 offload is a bounded change reusing the existing
  run/check poll pattern; F3 is a lock add + one workflow. Risk: low; preserves the
  hardened e2e suite and the celery coupling untouched.
- **Option B — Full FastAPI + ASGI (uvicorn/hypercorn) migration.** Replaces/re-writes:
  every `@app.route`/`add_url_rule`/view function (~79 routes), request/response
  plumbing (`request.form`, `request.json`, `jsonify`, `make_response`, `redirect`,
  `flash`, `url_for`, `render_template`), the Jinja + context-processor page layer, the
  JWT/login dual auth, CORS, the Admin CRUD (no ASGI parity — rebuild or keep Flask),
  Migrate→raw alembic, `uwsgi.ini`/run_app.sh/Dockerfile uwsgi layer, nginx
  `uwsgi_pass`→proxy config, and the celery coupling in tasks.py (decouple DB or keep a
  Flask shim). Weeks of churn across a verified stack for near-zero measured gain at
  this scale, and real regression risk to a flake-prone 114-test suite. FastAPI's real
  wins (async, pydantic request validation, OpenAPI docs) address problems this repo has
  not yet shown it has. **Not justified now — DEFER with a gating experiment (E2).**
- **Option C — Dual-stack (later): keep Flask server; add a NEW FastAPI ASGI service
  only for a productized external/Android API.** Isolates the future API (OpenAPI,
  pydantic, Bearer) without disturbing the verified web app; shares models/DB via
  imports. Cost: two serving stacks, two auth configs, nginx routing split,
  cross-stack model sharing. Only worth it when the product decision to ship a real
  external API exists; otherwise it is speculative complexity.
- **Cross-cutting truth for the "future Android client": the gating work is the API
  contract, not the framework.** A native client consumes HTTP+JSON; Flask serves JSON
  as well as FastAPI does. What must actually be decided/hardened (framework-independ-
  ent): Bearer vs cookie transport (`JWT_TOKEN_LOCATION=["cookies"]` today,
  app.py:131), route versioning, one error envelope (today it is mixed: `{"message"}`
  dicts, bare strings, `json.dumps` of object lists), server-wide request schema
  validation (only quiz uses jsonschema: `quiz/facade/json_schema_validation.py`; the
  rest hand-validates in `configurators.py`/`miminet_host.py`), rate limiting. A
  versioned JSON blueprint inside the existing Flask app (Option A+) satisfies an
  Android client without any framework migration.

## Recommended verdict per subsystem

| Subsystem | Verdict | Note |
|---|---|---|
| HTTP framework (Flask 3.1.3 + uwsgi) | **KEEP** | evidence F1; fix /ai gap in place (F2) |
| uwsgi entry / run_app.sh / uwsgi.ini | KEEP | add `threads`/raise `processes` only if a load measurement says so; pin uwsgi (F6) |
| flask extension stack (sqlalchemy/login/jwt/migrate/cors/admin) | KEEP | these ARE the migration cost; no ASGI parity for flask-admin; admin is 820 custom LOC |
| alembic / flask-migrate | KEEP (optionally use raw alembic) | alembic already a direct dep; no reason to churn alone |
| celery ↔ Flask import coupling | ADJUST (with lens B seam) | F9; migration enabler, not urgent |
| quiz controller/service/facade layering | KEEP | the good pattern; extend it |
| unrouted quiz endpoint functions | ADJUST | route or prune; free unit targets (F8) |
| Coverage tooling (front) | **ADJUST** | add coverage to front dev group + fast browser-free coverage job (F3) |
| Selenium e2e | KEEP | decision 2026-09-04; complement with unit tier, don't replace |
| Static gates (ty + ruff) | KEEP | mypy/isort dormant → prune or wire (F4) |
| CORS | ADJUST | single mechanism (F5) |
| requirements.txt | stays DEAD | never reintroduce |
| .env tracking | ADJUST | hygiene (F7) |

## Unverified & deferred experiments

- **E1 — 85% browser-free API coverage: file set + baseline + fail-under.**
  Question: which front/src modules can realistically reach 85% line/branch
  browser-free, and what is the honest gate number? Not settled because: current unit
  files only touch `quiz/util/dto`, `ai_generate` helpers, `app.get_database_uri`/
  `init_db`; exercising real endpoints needs a DB-session seam (app factory or
  `db.session`/`db.engine` monkeypatch) which lens B must define. Unblock chain:
  lens-B seam decision → write the first endpoint-tier tests (start with the unrouted
  quiz endpoints + validation-path handlers that need only request mocks) → measure
  baseline over the agreed file set → set fail-under at baseline−1 (back precedent:
  76.15 → 75). Aim: a number that means "API behavior is locked browser-free".
- **E2 — FastAPI-vs-uwsgi throughput decision (gate on a future migration).**
  Question: does ASGI beat WSGI for this mix, and by how much? Not settled because no
  recorded load problem or scale target exists, so a comparison would measure nothing
  real. Unblock chain: a target QPS/p95 for a classroom burst AND a load harness
  (k6/locust) replaying real routes against the compose stack; then compare
  uwsgi 5/10 processes vs uvicorn threads. Expected outcome per the request-mix
  evidence: DB and AI-gen latency dominate; WSGI is not the bottleneck.
- **E3 — /ai/generate-task fix selection.** Question: celery-offload vs more uwsgi
  workers? Unblock: front worker/uwsgi logs to measure concurrent saturation + the
  p95 latency tail; then pick the cheapest fix meeting the SLA. The offload path is
  preferred because it also removes the harakiri-300 cliff and frees HTTP workers.
- **E4 — Dual-stack (FastAPI for a future external API) cost spike.** Question: is a
  NEW FastAPI service cheaper than hardening the Flask JSON surface for a real Android
  client? Unblock chain: product decision to productize an external API + the API
  contract (auth: Bearer vs cookie; versioning; error envelope) → then a 5-endpoint
  spike (3 quiz + 2 network) on each option to produce a real LOC/time cost.
  Aim: cost/benefit on evidence, not vibes, before any dual-stack commitment.
- **E5 — uwsgi reproducibility.** Unblock: decide whether uwsgi should be a pinned
  uv dep (prod group) or an explicit image-layer pin; verify uwsgi wheels on the
  python:3.12 base before touching the Dockerfile. Aim: reproducible prod serving.
- **E6 (interacts with lens D) — auth transport for a native client.** flask-jwt-
  extended already supports `["cookies","headers"]` by config; settle whether a future
  client uses Bearer (then the JWT handlers need no framework change, only config +
  refresh-token policy). Unblock: lens D's auth contract decision.

## Ideas

- Carve an `/api/v1/` Flask blueprint that exposes ONLY the JSON handlers (versioned,
  one error envelope, Bearer-capable JWT config) as the lowest-risk path to a stable
  API for any future client — no framework migration, reuses the same test seams.
- Reuse the run_simulation→check_simulation poll pattern for AI generation (return a
  job id; JS polls) — it is proven in this codebase and removes the blocking HTTP call.
- Start the 85% unit tier with the ~10 unrouted quiz controller functions + the pure
  validation logic (configurators' ArgCheck/validators, ai_generate helpers,
  pcap_parser, quiz facade jsonschema) — highest coverage-per-effort, no DB needed on
  the failure paths.
- In the front coverage job, keep the explicit browser-free file list as a shell array
  (guardrail §7: arrays, not word-split strings), assert non-empty, and upload
  coverage.json with `include-hidden-files: true`.
- If the unit tier grows, move browser-free files under `front/tests/unit/` and exclude
  them from the e2e `find -maxdepth 1` slice (update the documented -maxdepth
  constraint) so the fast tier stops paying grid-boot cost; keep the empty-slice guard
  in both jobs.
- Do NOT let coverage fail-under be chosen before the baseline is measured; follow the
  back pattern (measured value minus ~1 point).
