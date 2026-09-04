# Lens-B review — System architecture of the whole stack, front + back + deploy (2026-09-05)

Author: architecture/system reviewer subagent (role file `docs/architecture_review_role.md` v1.0, lens B).
Scope: whole mimi-net/miminet stack — Flask web server (`front/src/*`), the quiz/ layered subpackage,
the celery/mininet emulation backend (`back/src`), DB/auth/celery wiring, and the deploy layers
(compose, ansible, systemd, nginx/uwsgi). Read-only review of fork `main` d30a3f1 == upstream `31878ff`.

## Question under review

Is the whole-stack architecture coherent for its real use — a web editor + emulation + quizzes + a
future **non-browser client** — and **what must change before an 85% browser-free front-API test
suite is worth writing**? Where is the coupling, and what is the cheapest seam work that unlocks it?

Companion question the review gates (per role §2): is the server mis-fit for its use (Flask as the
API server for a future non-browser client), i.e. should a framework/coverage investment be made at
all before the coupling below is addressed?

Bottom line up front: **the stack is coherent and Flask is not the problem.** The web tier is a page
server + thin JSON façade in front of a genuinely good async emulation core. The incoherence is not
framework-level; it is (1) import-time global app construction that freezes configuration, (2) no DB
migration tooling despite flask-migrate being wired in, (3) an auth and error-envelope design that is
entirely cookie/browser-shaped, (4) CWD-relative filesystem state mixed with module-relative state,
(5) one deploy mechanism that runs web + worker in a single container and three overlapping,
drift-prone back-end deploy paths, and (6) two synchronous emulation round-trips that sit in the web
request/worker path. None of these require leaving Flask; all of them gate the 85% browser-free aim.

---

## Verified evidence

### 1. Whole-stack component map

Process/component topology (verified from Dockerfiles, compose, run scripts, celery configs):

- **Web tier — one container, two roles.** `front/Dockerfile` builds a python image; `front/run_app.sh`
  first runs `python3 app.py "$MODE"` (DB init, exit), then `nohup uwsgi --ini /app/uwsgi.ini &`, then
  `exec python3 -m celery ... -Q common-results-queue,task-checking-queue` — so **uwsgi (5 processes,
  single-threaded, `front/src/uwsgi.ini`) and the front celery worker run in the same container and
  cannot scale independently**. nginx (`front/default.conf.template`) terminates TLS-facing HTTP and
  proxies to `miminet:80`; rabbitmq is a sibling container (`front/docker-compose-prod.yml:28-54`).
  Postgres is either a sibling container (dev, `front/docker-compose.yml:71-93`) or Yandex Cloud
  managed PG (prod, creds read at `app.py:211-233`).
- **Back (emulation) tier — mininet/ipmininet + OVS.** `back/Dockerfile` (ubuntu + mininet +
  openvswitch + mimidump); `back/ENTRYPOINT.sh` runs `ovs-init.sh` then
  `celery -A celery_app worker --concurrency=${celery_concurrency} -Q ${queue_names}`.
  `back/docker-compose.yml` runs it `network_mode: host` + `privileged`.
- **Ansible/legacy deploy for the emulation fleet.** `ansible/deploy.yml` clones the repo, `uv sync
  --frozen --no-dev --project back` with `UV_PROJECT_ENVIRONMENT=venv`, and relies on a systemd celery
  service (`ansible/miminet_back_1.service` + `miminet_back_1.conf`, `celery multi`, `-Q
  first_queue,second_queue`). `ansible/miminet_back_1.deploy` references
  `back/docker-compose.staging.yml` **which does not exist in the repo** (only
  `front/docker-compose.staging.yml` exists) — a stale deploy script. Two contradictory back-end
  queue namespaces: `ansible/miminet_back_1.conf` (`first_queue,second_queue`) vs `back/.env`
  (`queue_names=queue1,queue2,queue3`).

Message flows (verified from kombu objects and task bodies):

- Front→back emulation request: `run_simulation` (`front/src/miminet_simulation.py:57-65`) calls
  `app.send_task("tasks.mininet_worker", ...)` onto `SEND_NETWORK_EXCHANGE`
  (`Exchange(os.getenv("exchange_name"), type="x-consistent-hash")`,
  `front/src/celery_app.py:19-23`, plugin enabled in `rabbitmq/enabled_plugins`). Back worker
  `mininet_worker` (`back/src/tasks.py:120-152`) consumes its queue(s) on the same exchange
  (`back/src/celery_app.py:27-41`), runs `run_miminet`→`emulate` (`back/src/tasks.py:38-80`,
  `back/src/emulator.py:34-176`).
- Back→front result: when the front set `headers={"network_task_name": "tasks.save_simulate_result"}`
  (`miminet_simulation.py:64`), the back worker replies via `app.send_task(network_task, ...)` to
  `NETWORK_RESULTS_EXCHANGE` = `network-results-exchange` (direct) →
  `common-results-queue` (`back/src/tasks.py:140-150`, `front/src/celery_app.py:25-35`), consumed by
  the front container's own celery worker: `save_simulate_result`
  (`front/src/tasks.py:19-61`) writes animation JSON into `simulate.packets`, flips `ready=True`,
  and writes pcap blobs to `static/pcaps/<guid>/` (CWD-relative, see Finding F5).
- Quiz practice-task checking: the browser posts an answer; `check_network_task_endpoint`
  (`quiz/controller/quiz_session_controller.py:46-65`) → `create_check_task`
  (`quiz/service/network_upload_service.py:9-25`) sends to `task-checking-exchange` (direct) →
  `task-checking-queue`, again consumed by the **front** celery worker:
  `perform_task_check` (`front/src/tasks.py:64-128`), which re-enters the back emulator
  per sub-network via `create_emulation_task` (`front/src/tasks.py:131-156`), i.e. **a front worker
  does a synchronous back-and-wait round-trip (`allow_join_result(); async_res.wait(timeout=120)`) per
  sub-task**.
- Synchronous emulation inside a web request: `answer_on_session_question`
  (`quiz/service/session_question_service.py:344-419`) imports and calls
  `create_emulation_task` **inline (line 388-390)** while the request is still in a uwsgi worker —
  a blocking broker round-trip of up to 120 s per prepared sub-network, in a single-threaded worker
  pool of 5 (Finding F7).
- Configurators revoke stale jobs by `app.control.revoke(s.task_guid, ...)` from inside a web request
  (`front/src/configurators.py:215`).

### 2. DB layer

- Single SQLAlchemy instance `db = SQLAlchemy(metadata=metadata)` in `front/src/miminet_model.py:30`.
  Core emulation models (`User`, `Network`, `Simulate`, `SimulateLog`) live in `miminet_model.py:33-93`;
  quiz models (Organization/Test/Section/Question/QuizSession/SessionQuestion/Answer/PracticeQuestion/
  QuestionCategory/QuestionImage) are declared in `quiz/entity/entity.py` on the **same** `db` object
  (`entity.py:4`), with dialect-aware `GUID`/`Json` TypeDecorators (`entity.py:11-58`).
- Schema management: `db.init_app(app)` + `Migrate(app, db)` at import (`app.py:244-247`); alembic is a
  pinned dependency (`front/pyproject.toml`), **but there is no `migrations/` directory anywhere in the
  repo and no alembic revision**. The only schema path is `init_db` (`miminet_model.py:174-249`):
  `ensure_db_exists` (dev auto-creates the database via the `postgres` system DB, `miminet_model.py:96-171`)
  + `db.create_all()` **only if the `user` table is missing** + a startup data-fix that flips every
  non-ready `SimulateLog` to ready (`miminet_model.py:243-247`). Consequence: new tables appear on
  create_all, but **adding/altering a column of an existing table is not representable in the repo**
  — it is manual ALTER on prod. (Finding F2.)
- State is split between Postgres and the container filesystem: network bodies are a **single Text JSON
  blob** (`Network.network`, default `make_empty_network`, `miminet_model.py:53-69`); simulation
  animation is stored in `Simulate.packets` (Text) but **pcaps, preview images, avatars, quiz images are
  files** under `static/...` bound-mounted from the host in every compose file
  (`front/docker-compose-prod.yml:19-25`, `front/docker-compose.yml:19-25`). (Finding F5.)

### 3. Import graph / coupling (front/src)

`app.py` is the module-glue and everything funnels through it. Verified import edges (see Appendix A
for the per-module table):

- Every handler module imports the ORM: `miminet_model` (`db`, `Network`, `Simulate`, `SimulateLog`)
  is imported by `app.py`, `ai_generate.py`, `configurators.py`, `miminet_admin.py`, `miminet_auth.py`,
  `miminet_host.py`, `miminet_network.py`, `miminet_shark.py`, `miminet_simulation.py`, `tasks.py`, all
  five quiz controllers, the quiz entity module, three quiz facades/services and `quiz/util/dto.py`.
- Celery: `celery_app` (module-level `Celery(...)`) is imported by `configurators.py:7`,
  `miminet_simulation.py:4`, `tasks.py:10`, `quiz/service/network_upload_service.py:6`. `tasks.py`
  additionally imports the flask `app` (`tasks.py:7`).
- `quiz/` layering imports are strictly downward (controller→facade→service→entity/util) except two
  real upward/side edges: `quiz/service/session_question_service.py:7` imports `miminet_model`
  directly (bypassing its own layer), and `tasks.py:12` imports a quiz **service**
  (`quiz.service.session_question_service`) — i.e. the "clean" subpackage is reachable from the
  monolith's celery module and vice-versa.
- Import-time side effects (verified by execution): with `MODE=dev` and dummy PG env, `import app`
  succeeds offline with 138 registered rules; with `MODE=prod` and no Yandex creds it **raises
  ValueError at import** (verified). The import chain performs, at module scope:
  `app = Flask(...)` (`app.py:120`), reads `MODE`/`BASE_DOMAIN`/`ALLOWED_HOSTS`/expiry env
  (`app.py:124-142`), `CORS(app, ...)` (`app.py:150`), `load_dotenv()` (`app.py:184`), builds the DB
  URI from env (`app.py:191-238`), `db.init_app(app)` (244), `Migrate(app, db)` (247),
  `login_manager.init_app(app)` (250), `JWTManager(app)` (251), ~85 explicit `add_url_rule` calls
  (258-403), blueprint registration (405), and **instantiation of the flask-admin `Admin` + 7 model
  views** (408-428). `miminet_auth.py` additionally reads social-provider secret JSON files and sets
  `os.environ["OAUTHLIB_INSECURE_TRANSPORT"]="1"` at import (`miminet_auth.py:91-127`).
- Config is captured at import: `app.config["SQLALCHEMY_DATABASE_URI"]` is fixed from ambient env
  (238) and `MODE` is a module global read by the app (127) and later by `init_db`/admin/quiz paths.
  Verified experiment: mutating `app.config["SQLALCHEMY_DATABASE_URI"]` **after** import does **not**
  redirect the engine — a fresh Flask app + `db.init_app` + `sqlite://` + `db.create_all()` creates
  all 14 tables cleanly (verified), but the already-bound imported app still tries to connect to the
  original postgres URI. So the DB layer is SQLite-portable; the import-time binding is what blocks
  reconfiguration. (Findings F1/F4.)

### 4. Modularity

- Monolith (`front/src/*.py`, ~5.6 kLOC: app 646, auth 937, admin 820, network 592, host 582,
  configurators 581, ai_generate 617, model 249, simulation 107, shark 71, tasks 156, celery 60,
  pcap_parser 136, config 93) vs quiz subpackage (`front/src/quiz/`, 4.26 kLOC across 20 files in
  controller/facade/service/entity/util).
- Quiz layering: controllers are thin (read `request.args`/`request.json`, call facade/service, return
  HTTP), facades contain orchestration + serialization, services the pure logic. The pure network-graph
  checkers `quiz/service/check_host_service.py`, `check_network_service.py`, `check_practice_service.py`
  take plain dicts and return `(points, hints)` with no flask/ORM import in the deepest ones — the
  cleanest testable seam in the repo, yet W5 measured them at ~2% coverage (see §6).
- The monolith is **not** migrating toward quiz layering: the newest features (AI generation
  `ai_generate.py`, emulation queue endpoints, quiz glue) still add fat functions that mix ORM queries,
  request parsing, filesystem writes and celery sends in one function. Duplication is present within the
  monolith (e.g. `web_network`/`web_network_shared` are near-identical, `miminet_network.py:144-299`).
  quiz itself accreted a few violations (dead endpoints, direct model import in a service).
- Route/shape inventory (verbatim from `app.py:258-403` plus `@app.route` and blueprint):
  - **Auth**: `login_index` (HTML form), 4 social logins/callbacks (redirects), `logout` (redirect),
    `user_profile`/`profile` (HTML), `animation_filters` (JSON POST), `/refresh_access` (JSON POST/GET).
  - **Editor**: `create_network` (redirect), `web_network`/`web_network_shared` (**HTML pages** that
    embed the network JSON for cytoscape), `update_network_config`, `post_network_nodes`,
    `post_nodes_edges`, `move_network_nodes`, `upload_network_picture`, `copy_network`
    (**write-only JSON POSTs; there is no read-only JSON GET of a network**), host/edge `save_*` +
    `delete_job` (form→JSON), `run_simulation`/`check_simulation`/`emulation_queue/*` (JSON),
    mimishark pages (HTML), `ai/generate-task` (form→JSON).
  - **Quiz**: a mix on the same prefixes — `/quiz/test/all` renders HTML (`quizzes.html`),
    `/quiz/test/owner` returns a JSON array, `/quiz/test/get` JSON, `/quiz/section/test/all` renders
    HTML, question create/delete JSON, `/quiz/session/question/json` JSON,
    `/quiz/session/question` renders HTML, `/quiz/session/answer` returns a bare JSON *string* body,
    session start/finish JSON/text, `/quiz/session/result` HTML, image get/upload.
  - Flask-admin adds ~7 CRUD view families under `/admin/` (custom index view gates on
    `current_user.role >= ADMIN_ROLE_LEVEL`, `miminet_admin.py:288-336`).
- Auth model (browser-shaped, Finding F3): both flask-login (`login_user` + session cookie) and
  flask-jwt-extended cookies are issued at login (`miminet_auth.py:230-283`). JWT is **cookie-only**
  (`JWT_TOKEN_LOCATION=["cookies"]`, `app.py:131`); handlers are inconsistently protected with
  `@login_required` (quiz, network pages) or `@jwt_required()` (network/emulation JSON endpoints).
  CSRF protection is disabled in dev (`app.py:134`). `is_api_request()` (`app.py:468-478`) negotiates
  HTML-vs-JSON only for the JWT error handlers (401/422 redirect vs JSON).
- No server-wide request validation: jsonschema is used only for quiz practice requirements
  (`quiz/facade/json_schema_validation.py`); the network/device/simulation endpoints parse
  `request.form`/`request.json` ad hoc inside handlers. Back validates network schema via marshmallow
  only at emulation time (`back/src/tasks.py:56-57`, `back/src/network_schema.py`).

### 5. Testability facts (85% browser-free aim)

- Today's browser-free front tests: `front/tests/test_config_db.py` (7 tests, env-fixtures that mock
  psycopg2/inspect, imports `app` at module scope) and `front/tests/test_ai_generate.py` (pure-unit
  topology validators, ~137 lines). Everything else in the 114-test Selenium suite drives a real
  browser against a real compose stack.
- W5 measured the Selenium suite at **27% branch / 33.2% statement** of `front/src` (36 of 39 files
  executed); quiz checkers at ~2%. `front` has **no coverage infra or fail-under**; `back` has
  `coverage>=7.16.0` + fail-under (per `back/pyproject.toml` dev group, `back_test.yml`).
- Importability offline (verified): `miminet_config`, `pcap_parser`, `ai_generate`, `configurators`,
  `miminet_model`, and the whole quiz package import with no DB/broker connection as long as env is
  dev-shaped. `import app` works too (138 rules) — **but only with dev env; the same import raises
  under prod without Yandex creds**, and config cannot be changed afterwards without a process restart.
- DB seam feasibility (verified): all 14 tables create cleanly on `sqlite://` from a fresh app via
  `db.init_app` + `db.create_all()` — the model layer is deliberately dialect-aware
  (`entity.py` GUID/Json). The blocker for browser-free endpoint tests is not the DB engine; it is that
  the imported global app has already bound a URI and extensions, so a test process must choose its
  DB at import time (env) or the app needs a factory/URI-override.

---

## Findings

### F1 — Import-time global app construction freezes configuration  — **MUST-FIX** (for the 85% aim) / ADJUST (product)
- Evidence: `app.py:120` (`app = Flask(...)`), `:127` (`MODE` global), `:191-251` (URI from env at
  import, then db/Migrate/login/JWT init), `:407-428` (flask-admin instantiation at import). Verified:
  prod-mode import without Yandex creds raises; post-import `app.config` mutation does not redirect the
  engine (two experiments above).
- Why it matters: any browser-free test process and any non-browser client environment must pick the
  DB/auth/config at interpreter start. It blocks per-test isolation, in-memory/scratch DBs, and any
  config that differs between prod and test without forking the whole deployment env.
- Fix options and cost: (a) **app factory** `create_app(config)` moving init inside, keeping a thin
  module-level `app = create_app()` for uwsgi — ~0.5-1 d, touches `app.py` + `tasks.py` import; risk:
  decorators already applied at import of the handler modules keep referencing the module-global
  `db`/`login_manager` (which is fine — only the Flask instance needs a factory). (b) Minimal: honor an
  env override `SQLALCHEMY_DATABASE_URI` (3 lines at `app.py:238`) — enough to point a test run at
  sqlite/scratch PG at import time, cheapest, but doesn't give multi-app isolation or prod-import safety.

### F2 — No DB migrations despite flask-migrate  — **MUST-FIX** (product + test aim)
- Evidence: `Migrate(app, db)` at `app.py:247`; `alembic==1.16.5` pinned (`front/pyproject.toml`); no
  `migrations/` directory anywhere; schema change = `init_db`'s `create_all`-only-if-`user`-missing
  (`miminet_model.py:216-247`) + manual ALTER in prod.
- Why it matters: the quiz schema (13 tables beyond user/network) was added by create_all of new
  tables; the next column/table change lands on a non-representable prod diff. For a browser-free suite
  that seeds/tears down schema per run, an `alembic upgrade head`-style lifecycle is the normal
  prerequisite; today the repo can only express full-create, not delta. This is a hard gap for both the
  future client (data model evolution) and honest CI schema parity.
- Cost: introduce alembic env + one initial autogenerate revision against the dev DB, then a
  `db.create_all` fallback for tests. 1-2 d; medium risk because the prod DB must be baseline-stamped
  once.

### F3 — Auth & API shape are browser-only; no server-wide API contract  — **MUST-FIX** (future non-browser client), ADJUST (test aim)
- Evidence: JWT cookie-only (`app.py:131`), CSRF off in dev (`:134`), dual auth stacks (`@login_required`
  vs `@jwt_required` mixed across handlers), error envelope varies (`{"msg": ...}` from JWT loaders at
  `app.py:481-502` vs `{"message": ...}` from handlers vs `abort()` HTML pages in quiz controllers),
  JSON vs HTML varies even within the quiz prefix (see §4), **no read-only JSON endpoint returns a
  network document** (the editor embeds it in HTML pages), form-encoded vs `request.json` content types
  vary per endpoint (browser sends both, see `static/netfront_f.js`).
- Why it matters: an Android-like client needs (1) a bearer or header-token path or a token endpoint
  (cookies alone force a webview/cookie jar and CSRF machinery), (2) a stable error envelope, (3) JSON
  reads, (4) server-side validation so the client gets structured 400s rather than DB errors, and (5)
  CORS that does not gate native clients (CORS is browser-only; a native client is unaffected but will
  hit the cookie problem). None of this requires a framework change.
- Cost: mostly additive — accept Authorization header JWT (`JWT_TOKEN_LOCATION=["cookies","headers"]`),
  add `/api` JSON-read routes or a versioned blueprint, normalize the envelope and add a validation
  library. Orderable independently of the coverage work; ~2-4 d for a minimal bearer+JSON-read slice.

### F4 — The monolith accretes fat handlers; seams exist only where code is already pure  — **ADJUST**
- Evidence: handler functions mix ORM query + request parse + filesystem write + celery send in one body
  (`miminet_network.py:111-141` delete, `:458-508` upload, `configurators.py:215` revoke, `tasks.py`
  combined); quiz controllers stay thin by contrast. The pure checker services
  (`check_host/check_network/check_practice`) are the model of what the editor needs but are at ~2% e2e
  coverage (W5).
- Why it matters: 85% browser-free *line* coverage of the API layer is only meaningful if the logic
  under the handlers is separable; as-is, endpoint tests must either hit a real DB or mock the ORM and
  celery at very fine grain, which is exactly the high-cost, brittle style of test that the repo's
  hardened Selenium suite was built to avoid.
- Cost: extract read/write JSON serializers and filesystem helpers per resource (network/blob), then
  unit-test those; do **not** attempt to service-ize every handler before the coverage aim exists.

### F5 — Filesystem state and CWD-relative path handling  — **ADJUST**
- Evidence: `static/pcaps/` writes are CWD-relative in `miminet_network.py:191,275`, `miminet_shark.py:38`,
  `tasks.py:40`; preview images root `"static/images/preview"` is CWD-relative (`miminet_network.py:22`);
  quiz image upload folder `"static/quiz_images"` CWD-relative (`quiz/controller/image_controller.py:7`);
  but avatars hardcode `/app/static/avatar` (`miminet_auth.py:57`) and flask static is module-relative
  (`app.py:120-122`). Dev runs from repo root (DEVELOPMENT.md step 3), prod from `/app` — the same code
  writes blobs to *different* roots depending on CWD. State (pcaps/previews/avatars/quiz images) is
  bind-mounted host directories (`front/docker-compose*.yml`).
- Why it matters: CWD-dependent behavior is invisible until a test or deploy runs from the wrong
  directory; the "stateless" web tier is in fact stateful on mutable volumes, which constrains scaling
  and any future object-storage move. For tests it means browser-free tests must also pin CWD.
- Fix: resolve all blob paths off a single configured root (e.g. `app.config["STORAGE_ROOT"]`), not CWD
  or a hardcoded `/app`; cheap.

### F6 — Deploy topology conflation and drift  — **ADJUST**
- Evidence: web + front-celery worker share one container (`front/run_app.sh`), so queue-processing
  capacity and web capacity cannot scale independently and a web redeploy drains the queue consumer.
  Back deploy has three overlapping mechanisms: docker compose (`back/docker-compose.yml`), ansible +
  systemd `celery multi` (`ansible/deploy.yml`, `miminet_back_1.service/.conf`), and a `.deploy` script
  referencing a **missing** `back/docker-compose.staging.yml`. Queue/exchange names are duplicated
  across `front/.env`, `back/.env`, `ansible/miminet_back_1.conf` with contradictions
  (`queue1,queue2,queue3` vs `first_queue,second_queue`); the consistent-hash binding keys are implicit
  (`back/src/celery_app.py:18,33-36` fixed `ROUTING_KEY="1"`).
- Why it matters: not blocking today, but the 85% suite and the client work will touch CI/deploy
  surfaces (compose + CI compose at `front/tests/docker/docker-compose.yml`), and drift in queue
  topology is the classic silent-failure class this repo's infra guardrails already target.

### F7 — Synchronous emulation in the request/worker path  — **ADJUST**
- Evidence: `answer_on_session_question` (practice answers, non-exam path) performs `create_emulation_task`
  **inside the uwsgi request** with a 120 s per-sub-network broker wait (`session_question_service.py:388-390`
  + `tasks.py:131-156`); the uwsgi pool is 5 single-threaded processes (`uwsgi.ini`). Exam/check path is
  async (`check_network_task_endpoint` → celery) but the **front** worker that consumes it then blocks on
  back round-trips (`tasks.py:64-128`), tying task-check throughput to one shared consumer.
- Why it matters: an Android client submitting practice answers inherits this latency/throughput ceiling
  and the web tier can saturate on concurrent practice submits. Async-only submission + polling (as the
  exam path already does) is the coherent shape for a client.
- Cost: medium (route the synchronous practice path through `task-checking` queue and add a status
  poll, reusing `check_simulation`-style semantics); deferable but note the current request-time ceiling.

### F8 — Minor: import-time side effects in auth; role/permission model is a single integer  — **NICE-TO-HAVE**
- Evidence: `OAUTHLIB_INSECURE_TRANSPORT=1` and social-secret file reads at import (`miminet_auth.py:91-127`);
  roles are one `BigInteger` on `User` (`miminet_model.py:36`) compared against module constants
  (`ADMIN_ROLE_LEVEL=1`, `PROFILE_VIEWER_MIN_ROLE=1`). Fine for the current surface; document before a
  client exposes role-driven endpoints.

### F9 — (Basis for the lens-A/B gate, not a finding against the code): emulation core is healthy
- The back emulation stack (`emulator.py`/`network.py`/`network_topology.py`/`pkt_parser.py`, OVS
  readiness handling, retry-with-meaningful-packets logic in `back/src/tasks.py:59-117`, the 24-test
  back suite with coverage fail-under) is the most carefully built subsystem in the repo and the one
  piece that *would* be expensive to rewrite. Nothing in the front/browser story changes it.

---

## Option comparison (only where a real choice exists)

| Decision | Option A | Option B | Evidence / cost note |
|---|---|---|---|
| Server framework for the web/API tier | **KEEP Flask** (uwsgi 5×1, celery for long work) | Rewrite to FastAPI/ASGI | Long emulation is already offloaded; page renders dominate; uwsgi+celery+nginx+compose is all wired. ASGI buys nothing measurable for THIS mix (role §3a). Concurrency risk is not framework — it is F7's sync-in-request paths. KEEP; the role file's "Flask mis-fit" hypothesis is not supported by usage evidence. |
| App construction | ADJUST: module-global app → thin factory (or minimal env-URI override) | Leave as-is and point tests at a live PG via env | Cost A: 0.5-1 d. The DB layer is already SQLite-dialect-aware (verified create_all of 14 tables); the factory/override is the one missing seam for the 85% aim. |
| DB lifecycle | ADJUST: alembic baseline + `upgrade head` in deploy/test | Keep `create_all`-only | F2. |
| API/auth for non-browser client | ADJUST additively: bearer JWT + `/api` JSON reads + uniform envelope + validation | Nothing (keep cookie/HTML) | Client is a stated product direction; browser-only auth blocks it. |
| Blob/static storage | ADJUST: configurable storage root | Keep CWD/`/app` mix | F5; cheap, derisks tests + scaling. |
| Deploy of web+worker | ADJUST later: split front celery worker out of the web container; one queue namespace | Keep one container, two roles | F6; not a gate for the test aim. |

---

## Recommended verdict per subsystem

- **Web server (Flask/uwsgi/nginx/celery wiring): KEEP.** Evidence: the hard work is offloaded; the
  mix is pages + thin JSON; no measurable ASGI win for this workload; the existing compose/CI/e2e
  machinery is expensive and verified. Change Flask *now* would throw away the hardened Selenium stack
  for a framework that does not address any stated failure.
- **Flask app wiring / `app.py` module glue: ADJUST.** Introduce a configurable `create_app()` (or the
  minimal env-URI override) so browser-free tests and future clients can configure DB/auth without
  import-time env capture (F1).
- **DB models + SQLAlchemy: KEEP; DB lifecycle tooling: ADJUST (must-fix gap).** The model set is
  coherent (14 tables on one `db`) and SQLite-portable (verified); but there is no migration path (F2).
- **Auth (flask-login + flask-jwt): ADJUST.** Cookie dual-stack is fine for the browser; the client
  needs a bearer path, one error envelope, and JSON reads (F3). Keep the social providers.
- **Celery topology: ADJUST.** Front worker split from the web container and one authoritative
  queue/exchange namespace (F6); make the synchronous practice-answer path async (F7).
- **Emulation core (`back/src`): KEEP.** Healthiest subsystem; untouched by front work (F9).
- **quiz/ layered subpackage: KEEP (ADJUST-light).** The layering is the healthiest pattern; trim
  unregistered/dead endpoints and the direct `miminet_model` import in a service; unify its
  JSON/HTML/error conventions (F3).
- **Editor monolith (`miminet_network`/`miminet_host`/`configurators`): ADJUST, not REPLACE.** Extract
  pure serializers/filesystem helpers and add read-only JSON network GET; keep handlers as the seam.
  It is not migrating toward quiz layering on its own (F4).
- **Deploy (compose/ansible/systemd): ADJUST.** Consolidate the three back mechanisms, delete the stale
  staging references, reconcile queue names (F6).
- **Flask-admin: KEEP as internal tooling** (gated by role); note it is a large import-time cost for
  tests — make its registration optional under the factory.

---

## What must change before an 85% browser-free front-API suite is worth writing

Ordering (cheapest, highest-leverage first):

1. **App construction seam (F1).** Env `SQLALCHEMY_DATABASE_URI` override or factory. Verified the model
   layer then runs on sqlite; browser-free endpoint tests become a Flask `test_client` + `create_all`
   + seeded rows story instead of "must talk to a live postgres with the import-time env".
2. **Celery boundary as a test seam.** Patch `app.send_task`/`create_emulation_task` at the few call
   sites (`miminet_simulation.py:57`, `tasks.py:139`, `session_question_service.py:388`,
   `configurators.py:215`, `network_upload_service.py:19`). Because handlers call a module-global celery
   app, a single `monkeypatch` per test suffices; no broker needed. This is the cheap half of the 85%.
3. **Filesystem root seam (F5)** so tests pin a `.tmp` storage root and do not depend on CWD.
4. **Then measure honestly.** The right denominator is the handler/controller/facade/service file set
   (`app.py`-registered views + quiz), *excluding* template rendering and external (LLM/emulation)
   round-trips. Expect: quiz layers (esp. check_host/check_network/check_practice, currently ~2%) are
   the big cheap win — they are pure dict→(points,hints) functions with zero flask/ORM imports at their
   core. The editor monolith handlers reach high coverage only via the DB/celery/FS seams above.
5. **Do not chase 85% across template-heavy pages or the uwsgi-init/`__main__` paths** — that is where
   the Selenium suite already earns its keep and where line coverage is least meaningful.

Cost estimate for steps 1-4: ~1 d (F1) + ~1-2 d (test harness, fixtures, sqlite session, seeded rows,
celery-patch fixtures) + ~1 d (F5) + the quiz checker test writing (~0.5-1 d/file for the pure
functions). A realistic 85% *line* over the API/controller+service file set (not over `front/src`
globally) is plausible in ~1.5-2 focused weeks; **an 85% global-`front/src` number is not a sensible
target** and would drag in template/static and sync-emulation code that is better e2e-tested.

---

## Unverified & deferred experiments

1. **Route/template dead-code inventory.** Evidence found that several quiz controller endpoints exist
   but are not wired in `app.py` (e.g. `create_test_endpoint`, `edit_test_endpoint`,
   `create_section_endpoint`, `get_retakeable_tests_endpoint`, `get_deleted_*` — see
   `quiz/controller/test_controller.py`/`section_controller.py`); they may be reachable only via
   `url_for` in templates the browser uses. *Why not settled:* full template↔route cross-reference was
   out of budget; I did not prove each is dead. *Unblock:* a `url_for`/href/fetch cross-check script
   over `front/src/templates`+`static` against `app.url_map` (cheap, scriptable in the repo).
2. **Whether the synchronous practice-answer path (`session_question_service.py:388`) is actually hot
   in production or legacy.** *Why not settled:* no traffic data or endpoint analytics exist in the repo.
   *Unblock:* staging access/logs or the product owner stating whether quiz practice is exam-path only.
   This decides whether F7 is must-fix or nice-to-have before the client work.
3. **Live concurrency/load ceiling of the 5×1 uwsgi pool under concurrent practice submissions.**
   *Why not settled:* no load harness exists and running one needs a staging stack. *Unblock:* a small
   locust/`ab` run against staging with N parallel `answer_on_session_question` submissions.
4. **Whether flask-admin registration must be optional in tests.** *Why not settled:* the imported
   `Admin` instance works offline (verified import); only wall-clock and URL-map noise are at stake.
   *Unblock:* measure collection time with/without admin under the new factory.
5. **Flask→ASGI/FastAPI fit.** Settled directionally as KEEP by usage evidence (long work offloaded,
   pages dominate). If a future *non-browser* client ever needs websockets/push, revisit with a
   concrete push requirement; *unblock condition:* a stated realtime feature (e.g. live emulation
   streaming to a client), not a generic "FastAPI is faster" argument.
6. **SQLite parity risk for browser-free tests** (e.g. `TIMESTAMP(timezone=True)`, the `GUID`/`Json`
   TypeDecorators and `psycopg2`-only helpers `ensure_db_exists`). Verified: `create_all` of all 14
   tables on sqlite works; unverified: query semantics for the few `TIMESTAMP` comparisons
   (`session_question_service.py:21-33`, `finish_session`). *Unblock:* run the endpoint suite against
   sqlite in CI once the F1 seam lands; if tz comparisons misbehave, use an ephemeral postgres in CI
   instead (still cheap).

---

## Ideas (rough — better on the record than lost)

- A `/api/v1` blueprint mounted next to the legacy routes (mount both; legacy keeps working) would give
  the future client a versioned, JSON-only, envelope-normalized surface *without* touching the editor
  code that works. The 85% suite can then target the legacy handlers now and the new API later.
- Reuse `check_simulation` semantics for a `POST /quiz/session/answer` async submission + `GET` poll so
  browser and client share one practice-check flow (removes F7 for both).
- Consider making `app.send_task` go through one tiny `front/src/queue.py` module (send-emulate, send-check,
  revoke) so the celery boundary is a single file to patch in tests and to swap for a fake runner.
- The `config.js` route (`app.py:505-516`) already exposes `PUBLIC_CONFIG_KEYS`; extend that pattern to a
  `GET /api/config` JSON for clients instead of scraping config.js.
- W5's `.pth`/coverage mechanism is reusable to re-measure the API layer *after* the seams land — the
  per-file before/after delta is the honest success metric for the 85% investment.
- The pure checker services already implement a dict-based "answer contract"; formalizing that contract
  (the `requirements` jsonschema) as the server-side validation for quiz endpoints would unify F3's
  validation gap with existing quiz work.
- Since `Network.network` is a Text JSON blob with no schema enforcement at write time, a browser-free
  suite that seeds networks will silently bless invalid blobs; consider validating on write with the
  back's marshmallow `Network` schema (`back/src/network_schema.py`) shared as a front dependency.

---

## Appendix A — front/src import/coupling table (verified)

| module | imports ORM (`miminet_model`) | imports celery | flask-login/jwt | flask-admin | import-time side effects |
|---|---|---|---|---|---|
| app.py | yes (69) | via handlers | yes (29, 20-28) | yes (18, 407-428) | app, CORS, env, URI, db.init_app, Migrate, login/JWT init, ~85 routes, blueprint, Admin+7 views |
| ai_generate.py | yes (10) | — | login (9) | — | none (module consts/prompts) |
| celery_app.py | — | own (17) | — | — | Celery, exchanges/queues from env |
| celeryconfig.py | — | config | — | — | load_dotenv, env reads |
| configurators.py | yes (10) | yes (7) | login (9) | — | imports celery_app |
| miminet_admin.py | yes (28-29) | via network_upload_service (24-27) | login (11) | yes (5-15) | view classes at import (instantiated in app.py) |
| miminet_auth.py | yes (41) | — | yes (31-37) + jwt (24-30) | — | reads social secret files, sets OAUTHLIB env (91-127) |
| miminet_host.py | yes (19) | via configurators | jwt (18) | — | imports configurators |
| miminet_model.py | self | — | login UserMixin (5) | — | none (declarative only) |
| miminet_network.py | yes (19) | — | jwt (16) + login (17) | — | module consts (paths) |
| miminet_shark.py | yes (6) | — | login (5) | — | none |
| miminet_simulation.py | yes (7) | yes (4) | jwt (6) | — | imports celery_app |
| pcap_parser.py | — | — | — | — | none (pure dpkt) |
| tasks.py | yes (11) | yes (10) + flask app (7) | — | — | imports app + quiz service |
| quiz/entity/entity.py | yes (4) | — | — | — | none |
| quiz/controller/* | yes (5 of 5) | via services | login (5 of 5) | — | none |
| quiz/facade/* | yes (2 of 2 + json_schema_validation none) | via network_upload_service | — | — | none |
| quiz/service/* | section/test/session_question/network_upload yes; check_* no | network_upload_service (6) | — | — | network_upload_service imports celery_app |
| quiz/util/dto.py | yes (15) | — | — | — | none |

(Line numbers are the first `from` line of the relevant import in each file.)
