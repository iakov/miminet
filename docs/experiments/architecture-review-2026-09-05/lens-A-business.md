# Lens A (business/product) review — whole-stack API + future non-browser client fit (2026-09-05)

Reviewer: business/product lens (role file `docs/architecture_review_role.md` v1.0).
Scope: whole stack, viewed through the maintainer's stated product direction — a
future non-browser (e.g. Android) client will talk to the "front server", so its
API must be stable, robust and browser-free-testable at 85% line coverage.
Evidence was gathered by reading repo files only (read-only run). Numbers below
are from `front/src` on fork `main` d30a3f1 (== upstream 31878ff).

---

## Question under review

From a BUSINESS/PRODUCT perspective: is investing in (a) a stable machine-readable
API contract and (b) an 85%-line browser-free test gate the right call for Miminet,
and what API/product contract does a non-browser client actually need?

Framed more sharply: **what does Miminet actually sell, which slice of the server
does a mobile client genuinely consume, and is "85% of front/src, browser-free"
the correct gate — or a category error that would burn the Selenium-hardened
investment on the wrong file set?**

## Verified evidence

### Product reality (what Miminet serves today)
- Public marketing + corporate-education site (`miminet.ru`), README title: "эмулятор
  компьютерных сетей на базе ОС Linux, предназначенный для образовательных целей".
  Landing `front/src/templates/index.html` currently frames an "IT-стажировка в YADRO"
  banner (corporate/university course partner model); `/course`, `/examples` (13 curated
  network GUIDs hard-coded in `app.py:560-580`), `/web_network_shared` (shareable
  read-only network pages).
- **Core student loop**: build/configure a network in a browser canvas editor
  (`/web_network` → `network.html` → `static/netfront_f.js`, cytoscape-based), emulate it
  (celery `tasks.mininet_worker` on back/rabbitmq; `run_simulation`/`check_simulation`),
  watch a packet animation and inspect per-interface pcaps in **MimiShark**
  (`mimishark.html`, 5 routes in `app.py:334-338`).
- **Quiz/exam platform**: teacher-authored `Test → Section → Question(→PracticeQuestion)`
  (multi-tenant `Organization`), students take timed sessions with theory questions
  (variable/sorting/matching, graded in-request) and practice questions (student builds a
  network, answer = the network_guid; graded by emulating variants and comparing against
  `requirements`, `quiz/service/check_*`). Exam practice answers are checked **async via
  celery** (`/quiz/session/check_network_task` → `create_check_task` →
  `tasks.check_task_network`); in-session practice self-check is **synchronous in the HTTP
  request** (`/quiz/session/answer` → `answer_on_session_question` →
  `create_emulation_task(...).wait(timeout=120)` per variant, `session_question_service.py:388-390`,
  `tasks.py:139-156`).
- **AI task generation** for teachers (`/ai/generate-task`, role ≥ 1): long upstream LLM
  calls (nginx gives `location /ai/` a 300 s uwsgi timeout, `front/default.conf.template:15-20`).
  Endpoint returns a **302 redirect** to the editor page, not JSON (`ai_generate.py:617`).
- Quiz authoring lives in **flask-admin** (`miminet_admin.py`, ~820 lines) — HTML only,
  browser-only by nature; NOT part of any JSON API.

### Route surface (registered, from `front/src/app.py` + `quiz/controller/image_controller.py`)
Rough inventory by return kind (see also the HTML/JSON counts the authoring agent can
regenerate with `app.url_map`):
- **HTML page renders / editor chrome (≈25 route-methods)**: `/`, `/home`, `/course`,
  `/examples`, `/web_network`, `/web_network_shared`, `/auth/login.html` (GET),
  `/user/profile.html`, `/profile`, `/profile/<user_id>`, 5× `/…/mimishark`, `/quiz/test/all`
  (`quizzes.html`), `/quiz/section/test/all` (`quiz.html`), `/quiz/session/question`
  (`sessionQuestion.html`), `/quiz/session/result` + `/quiz/user/session/result`
  (`sessionResult.html`/`userSessionResult.html`), `/sitemap.xml`, `/config.js`, flask-admin `/admin/*`.
- **JSON write/query handlers (≈30 route-methods)**: network (`update_network_config`,
  `post_network_nodes`, `post_nodes_edges`, `move_network_nodes`, `upload_network_picture`,
  `copy_network`, `delete_network` POST), simulation (`run_simulation`, `check_simulation`,
  `emulation_queue/size`, `emulation_queue/time`), host config (`…/host/{host,router,server,hub,
  switch,textbox}_save_config`, `/edge/save_config`, `/host/delete_job`), quiz JSON
  (`/quiz/test/owner`, `/quiz/test/get`, `/quiz/question/create|delete|all`,
  `/quiz/session/start`, `/quiz/session/answer`, `/quiz/session/check_network_task`,
  `/quiz/session/finish`, `/quiz/session/finishold`, `/quiz/session/question/json`),
  `/quiz/upload` + `/quiz/images/upload`, `/user/animation_filters`, `/refresh_access`.
- **Auth**: browser auth is **two parallel systems**.
  - flask-login session cookie `mimi_session` (server-side session) decorates `@login_required`:
    **all** quiz controllers (`quiz/controller/*.py`), `create_network`, `user_profile`,
    `animation_filters`, `generate_ai_task`, `home`.
  - flask-jwt-extended **JWT in cookies only** (`JWT_TOKEN_LOCATION=["cookies"]`, `app.py:131`)
    decorates `@jwt_required()`: the network/simulation/host-config JSON API.
  - `login_index` sets both cookies on form POST; social callbacks (Google/VK/Yandex/TG)
    `login_user()` + set JWT cookies; `/refresh_access` (`@jwt_required(refresh=True)`) is
    cookie-refresh only. `auth_tests/` prove the flask-login/JWT config split.
  - **CSRF**: `JWT_COOKIE_CSRF_PROTECT=True` when `MODE=prod` (`app.py:134`). No JS/template
    anywhere sends an `X-CSRF-TOKEN` header (searched `static/`, `templates/`, netfront, quiz
    scripts). See deferred experiment D1 — this is unverifiable from the repo and potentially
    a live prod bug for cookie-JWT writes.
- **Content-type discipline is absent**. Quiz list endpoints return raw
  `json.dumps([obj.__dict__…], cls=UUIDEncoder)` strings (`test_controller.py:51`,
  `question_controller.py:19`) — body is JSON but `Content-Type` is Flask's default
  `text/html; charset=utf-8`. `answer_on_session_question_endpoint` also returns a raw JSON
  string body (`quiz_session_controller.py:30`). Host "config" writes accept
  **form-urlencoded** input (`miminet_host.py` `get_data()` → `request.form`), not JSON.
  `/quiz/session/answer` POSTs JSON but the exam path returns Russian text strings, not JSON
  (`quiz_session_controller.py:58,65`).
- **Error envelope inconsistent**: `{"message": …}`, `{"error": …}`, `{"msg": …}` (JWT
  callbacks, `app.py:481-502`), plain text, `abort()` (→ HTML error page), plus non-standard
  HTTP `210` for "simulation in progress" (`miminet_simulation.py:107`).
- **Dead / likely-broken registered handlers**: `/quiz/test/get` returns
  `make_response(jsonify(res), res[0])` where `res = (SQLAlchemy model, 200)` —
  `jsonify` of a model tuple is not serializable → runtime error (`test_controller.py:37-43`).
  No template/JS references it. Several **controller functions that are never registered as
  routes** exist (create/edit/delete test, publish/unpublish, retakeable/deleted lists,
  create/edit/delete section, get_section … in `test_controller.py`/`section_controller.py`).
- **Authz gaps on consumption endpoints** (business-critical if exposed to an API client):
  `start_session` does not check section.test.is_ready, org membership, or re-attempt policy
  (`quiz_session_facade.py:208-255`); `session_result` does not check session ownership
  (`quiz_session_facade.py:296`); `finish_session` checks `created_by_id != user.id` **before**
  the `is None` guard (`quiz_session_facade.py:258-264`, ordering bug → AttributeError on
  nonexistent session). `get_questions_by_section_endpoint` doesn't gate that the section's
  test is the caller's/published.

### Testing/cost baseline (measured by W5 + repo facts)
- W5 instrumented Full-test run: **27 % branch-weighted coverage of `front/src`** by the whole
  Selenium e2e suite (statements 33.2 % = 1596/4811; branches 7.7 %; 36/39 files executed).
  Worst big file `quiz/service/check_host_service.py` at **2 %** — i.e. the scoring engine is
  the least-covered code (see `docs/experiments/w5-front-e2e-cov/README.md`).
- `front/tests/*` are almost entirely Selenium e2e (conftest drives a real grid against the
  compose stack; suite ~6+ min, host-memory-bound, one shared browser). Unit-test seams that
  already exist: `front/tests/test_config_db.py`, `front/tests/test_ai_generate.py` (imports
  pure functions, no HTTP/DB), and `front/src/auth_tests/` (standalone Flask app fixture +
  mocked `db.session`/`User` for `miminet_auth` handlers — the pattern to generalize).
- `front/src` ≈ 10 200 Python lines incl. `quiz/` (≈4 260) + `auth_tests/`; `quiz/` is the only
  layered subpackage (controller → facade → service → entity/util) with DTOs
  (`quiz/util/dto.py`, 596 lines) and one jsonschema validator
  (`quiz/facade/json_schema_validation.py`). The monolith handler modules
  (`miminet_network.py` 592, `miminet_host.py` 582, `configurators.py` 581, `miminet_auth.py` 937,
  `miminet_admin.py` 820, `app.py` 646, `ai_generate.py` 617) mix rendering, request parsing,
  DB access and business rules in one file.
- **No app factory**: `app = Flask(...)` + `db.init_app(app)` + `Admin(app,…)` all run at import
  of `app.py` (`app.py:120-428`). Importing `app.py` requires DB env and would register admin.
  Controllers/services do NOT import `app.py` (verified import graph), so unit tests can build
  their own app/context — the auth_tests pattern. `tasks.py` DOES `from app import app` (celery
  side needs the Flask app context).
- Coverage infra: `back` has `coverage>=…` + fail-under; **front has none** (`front/pyproject.toml`
  dev group has no coverage/pytest-cov). W5 had to pip-install coverage into the image.
- Front test DB: tests today run against the real compose Postgres (MODE=dev). Entity layer is
  sqlite-portable by design (`GUID` TypeDecorator, `quiz/entity/entity.py:11-39`).

---

## Findings

F1 — MUST-FIX (product framing): **The "85% browser-free of front/src" goal is miscast.**
`front/src` is ~10 k lines of which a mobile client can consume at most ~2–3 k (quiz
consumption + result/progress + emulation status + auth). The rest is: browser canvas chrome
(`/web_network` page + cytoscape + animation JS driving HTML), flask-admin authoring, marketing
pages, sitemap, config.js, social-OAuth HTML redirect dance. None of that is "API", none is
mobile-relevant, and most of the Python behind it is only reachable through a browser. Setting a
whole-`front/src` 85 % browser-free gate would force either (a) grotesque mocking of
template-rendering/redirect handlers to fake coverage on non-API code, or (b) rewriting HTML
flows as JSON for the sake of the number. Both waste the hardened Selenium investment (decision
2026-09-04: Selenium stays). Correct gate: **85 % line over a *declared API slice*** (see F8),
defined as the file set a non-browser client can call, plus unit coverage of the **grading
engine** (which is pure logic and 85 % is cheap and enormously valuable there). For the
editor/admin/browser layers, the Selenium suite remains the gate.

F2 — MUST-FIX (business value): **The score-correctness engine is the crown jewel and the least
tested.** `quiz/service/check_host_service.py` (706 lines, the per-device grading), 
`check_practice_service.py` (353, score + hints), `session_question_service.answer_*`
(grading write-path), `check_network_service.py`, `network_upload_service.py` (task
preparation/modification semantics) sit at ~2–17 % coverage and are only exercised via slow e2e
that clicks through a full practice build. These functions decide a student's score. A grading
regression silently changes marks for every student using the platform. This is the single
highest-ROI browser-free test target, it needs no HTTP at all (pure dict + DB-light logic), and
it should be the first 85 % slice. Evidence the engine is subtle: jsonschema requirements
validation + 3 retry/mutation paths in `ai_generate`, `get_configured_tasks` modification
semantics (`remove_edge`, `add_ping`, `network_upload_service.py:70-224`), `EXCLUDED_JOB_IDS`.

F3 — MUST-FIX (contract precondition): **A mobile client cannot authenticate today.**
Quiz endpoints (the mobile-relevant slice) run on flask-login `@login_required` = server-side
session cookie; the network API runs on cookie-only JWT. Bearer tokens are not accepted anywhere
(`JWT_TOKEN_LOCATION=["cookies"]`, `app.py:131`). An Android app cannot do CSRF-double-submit
cookies reliably, cannot keep a flask-login session + JWT cookie pair as its auth model, and
social login is a browser redirect loop (Google/VK/Yandex/TG, `miminet_auth.py`) with no mobile
flow. Minimum contract: JSON login (email+password) → access+refresh tokens returned in body;
add `"headers"` to `JWT_TOKEN_LOCATION`; a single auth decorator for API routes (JWT), leaving
flask-login for page renders/admin only. Until then every "API hardening" commit tests a
contract that a mobile client can't use.

F4 — MUST-FIX (robustness for any client, incl. today's browser): **Inconsistent/undefined
wire contract.** Mixed `Content-Type` (JSON bodies served as `text/html`), mixed error keys
(`message`/`error`/`msg`), raw `json.dumps` lists, HTML-on-abort, `210`-style ad-hoc codes,
form-encoded "config" writes vs JSON elsewhere, and no schema validation on most write bodies
(ad-hoc `request.json["name"]` key accesses → 500 on malformed input). The quiz subpackage
*already solved this locally* (DTOs + one jsonschema validator for practice requirements,
`json_schema_validation.py`) but the pattern is not applied server-wide. A stable API means
freezing: (1) one error envelope `{"error": {"code","message",…}}`, (2) `application/json` both
ways, (3) HTTP semantics (202 for accepted async, 200/201 otherwise), (4) request-schema
validation, (5) response DTO schemas. Browser can keep its HTML routes; the *new* versioned
JSON surface should be the frozen one (F8).

F5 — MUST-FIX (async honesty): **Practice self-check is a synchronous up-to-120 s emulation
inside the HTTP request.** `/quiz/session/answer` for a practice question runs
`create_emulation_task().wait(timeout=120)` per variant in the request thread
(`session_question_service.py:388-390`, `tasks.py:150`). Nginx default uwsgi timeout for `/quiz/*`
is 60 s (only `/ai/` gets 300 s). So large practice checks can exceed the proxy timeout → 504 →
"Ошибка. Повторить?" on an idempotency-less path (answer is re-graded each retry; scoring is
recomputed). For a mobile client this is doubly wrong: phones die mid-request, and the exam path
already demonstrates the right pattern (submit → celery → poll). Before freezing an API on this
route, the mobile-relevant practice-check API should be job-based (submit → id → poll), reusing
the exam/`perform_task_check` machinery.

F6 — ADJUST (scoping insight): **Only the quiz-consumption + emulation-status + results slice is
genuinely mobile.** Android can list tests/sections, start/finish timed sessions, answer theory
questions (variable/sorting/matching are all JSON-answerable today), view results/progress and
poll emulation state. It cannot meaningfully *build* networks (drag-drop canvas is a desktop
interaction) nor author quizzes (flask-admin). Practice questions therefore need a product
decision: either mobile = "theory + results, practice done on desktop", or a web-view falls back
to the editor for practice tasks (which means that flow is never truly "browser-free"). This
decision bounds the API file set and the 85 % gate.

F7 — ADJUST (multi-tenancy posture): `Organization`/org subdomains exist (`organization_url_for`,
cookie domain `.BASE_DOMAIN`, `quizzes.html` per-org branding, org logo resolution in dto.py) but
the service layer does **not** scope quizzes by org or by "published" state
(`get_all_tests` lists every `is_ready` test of every org; `start_session` skips
`is_ready`/retake policy; authoring ownership checks use only `created_by_id`, and
`Question`/`Answer` have no ownership at all). If orgs are a real revenue segment (schools buy
their own space), an open API makes this a *reachable* data boundary, not just a UI one. Needs a
product decision on the org model before the API is opened, plus a policy test suite.

F8 — ADJUST (route/versioning): Today route paths conflate page and data (`/quiz/section/test/all`
returns HTML; `/quiz/test/all` HTML while `/quiz/test/owner` JSON; `/quiz/session/question` HTML
vs `/quiz/session/question/json` JSON). A non-browser client needs *data variants* of several
HTML routes (published test list, section list with progress, question payload, results) and a
guarantee those stay stable. Cheapest robust pattern: a versioned JSON facade (e.g. `/api/v1/…`
delegating to the existing service/facade layer) rather than mutating the current routes — the
existing paths keep serving the browser and may evolve freely; the facade is the frozen contract.
No need to touch the Flask app internals for this (thin blueprint + jsonify). Route "versioning"
otherwise means freezing the current mixed paths forever, which is a worse constraint.

F9 — ADJUST (auth token economics for mobile): current token lifetimes (access 1 h, refresh 2 h,
`app.py:136-141`) are fine for a web session, tight for a phone app; refresh-rotation + storage
policy (Keychain/Keystore) must be designed, and `/refresh_access` must be callable with a
*refresh token in the body/header*, not only as an HttpOnly cookie. CORS is already configured and
is irrelevant to native apps (only matters for a future web/JS client). Rate limiting is absent
anywhere; for a public mobile client, login/refresh and `/ai/generate-task` need throttling
(cheapest at nginx level; no app change).

F10 — NICE-TO-HAVE (value of the 85 % gate, correctly scoped): a deterministic, seconds-fast,
browser-free net on the API slice replaces the slow/flaky e2e as the *developer loop* for API
changes (the Selenium suite stays the integration gate for UI flows). E2E today gives 27 % branch
and each run costs ~6+ min and host memory. The marginal cost of coverage on top of the layered
quiz code is low because controller/facade/service boundaries and DTOs already exist, and the
auth_tests pattern (own Flask app + sqlite or mocked session) is proven. This is real value **if**
and only if the gate is over the declared API slice (F1/F6), not `front/src` wholesale.

F11 — NICE-TO-HAVE (AI endpoint contract): `/ai/generate-task` is registered as a JSON-era POST
but returns a 302 to `/web_network?guid=…`, reads `request.form`, and requires role ≥ 1 +
per-user stored API keys. It is today's only "generative teacher" feature and plausibly the next
mobile/differentiator product. Its contract (form-input → redirect) is neither API nor robust
(`ai_generate.py:459` reads form, returns `jsonify({"error"…})` on failure but redirect on
success). If AI tasks stay strategic, give it a JSON contract (task params in, `{guid}` or async
job out) in the v1 facade.

F12 — DEFER (Flask vs "not best"): business-lens view only — the deeper framework verdict is the
system-architecture lens's job (lens-B). From product economics: page renders dominate the
request mix, heavy compute is already offloaded to celery, and the concurrency model is real
uwsgi workers; nothing in the mobile-client slice is throughput-bound. The actual *deficits* for
a stable API (typed schemas, docs, error envelope, bearer auth) are all available as libraries on
Flask (pydantic/marshmallow + apiflask/smorest + flask-jwt-extended headers) at a fraction of a
rewrite's regression risk against the hardened e2e/CI stack. My prior is KEEP Flask + add a
versioned JSON facade; do not REPLACE on a business basis. Deferred to lens-B for the
architecture verdict; the cost comparison table is below.

---

## Option comparison

Option 1 — Contract-first versioned JSON facade on Flask (recommended shape):
- What: thin `/api/v1/*` blueprint delegating to existing service/facade layers; JSON login +
  bearer (headers added to JWT locations); jsonschema request validation server-side; canonical
  error envelope registered at blueprint level; 85 % line coverage gate on the *declared API
  slice* + grading-engine units; OpenAPI spec (hand-written v1 or generated) frozen as the
  contract; CI contract test asserting every facade route returns `application/json` + a valid
  response schema.
- Cost: low-to-moderate. No framework change; reuses quiz layering + auth_tests seam; does not
  touch nginx/uwsgi/celery/ansible topology; e2e suite untouched (runs in parallel as the UI
  gate). Main new code = facade controllers (~300–600 lines) + schema files + tests. Estimated
  one focused batch series.
- Risk: none to the running product; browser routes untouched.
- Business payoff: unblocks Android/third-party integrations, gives deterministic API regression
  net, protects the score engine, does not burn Selenium investment.

Option 2 — Full 85 % browser-free gate over all of `front/src` (the stated aim taken literally):
- What: coverage target over ~10 k lines incl. HTML/redirect/admin handlers; forces JSON-ification
  or heavy mocking of non-API code to satisfy the metric.
- Cost: high; low value. Large mock surface (render_template, redirects, session, current_user),
  brittleness, and duplicated parallel logic for pure metric-chasing. Risks derailing the 
  maintainer's real goal (stable mobile contract) into a coverage theater exercise. Would need
  substantial seam surgery (app factory, DI) that the codebase currently avoids with a working
  simpler pattern.

Option 3 — Rewrite/replace server framework first (FastAPI etc.), then add API:
- Cost: very high; regression risk to the hardened e2e/CI/uv/compose/ansible stack; defers the
  mobile client by months. Only justified if lens-B finds Flask *structurally* unfixable, which
  I don't expect given the layered quiz subpackage already works inside it. DEFER unless lens-B
  says otherwise.

Recommendation: Option 1, with the coverage gate defined over the API slice + grading engine
(not whole `front/src`), and grading-engine units shipped first (highest ROI, cheapest).

## Recommended verdict per subsystem (business lens)

- **quiz/ layered subpackage (controller/facade/service/entity/util/dto/validation)** — KEEP
  the layering; it is the pattern the monolith should follow. ADJUST: content-type/error-envelope
  discipline at controllers; clean up dead controller functions (unregistered test/section
  create/edit/delete/publish endpoints) or wire them deliberately; add ownership guards
  (F2/F7); move the synchronous practice self-check to the async job pattern for the facade
  surface (F5).
- **Monolith network/host/simulation handlers (`miminet_network.py`, `miminet_host.py`,
  `configurators.py`, `miminet_simulation.py`, `tasks.py`)** — KEEP (they are the working
  emulator API the browser uses; Flask handles this fine). ADJUST: do NOT expose them raw as the
  mobile contract; fold the JSON-write semantics they already have into the v1 facade with JSON
  bodies + schemas. The canvas page itself stays browser-only.
- **`miminet_auth.py` (dual flask-login + cookie-JWT + 4 social providers)** — ADJUST: add
  JSON login + bearer (`headers` token location) + refresh-in-body; keep cookie/social paths for
  browser unchanged. Only REPLACE if a future SSO/OIDC product decision lands (defer).
- **`app.py` module-level monolith** — KEEP for now (no app-factory refactor required for the
  recommended path; tests can build their own app as auth_tests do). If the API slice grows, an
  app-factory refactor is the *second* step, gated on the contract tests, not a prerequisite.
- **flask-admin authoring (`miminet_admin.py`)** — KEEP (teacher desktop tool, HTML by nature);
  explicitly out of API scope and out of the 85 % browser-free set.
- **Selenium e2e suite** — KEEP as the UI/integration gate (decision 2026-09-04 stands); the new
  browser-free suite *complements* it on the API/grading slice, it does not replace it.
- **Flask itself** — KEEP (business lens; defer final word to lens-B; see F12/Option 3).
- **nginx/uwsgi/celery/rabbitmq topology** — KEEP; only additive nginx rate-limit + `/api/v1`
  pass-through + (async work) nothing else required.

## Unverified & deferred experiments

D1 — **Prod-mode CSRF reality.** Claim: with `JWT_COOKIE_CSRF_PROTECT=True` (MODE=prod) and no
`X-CSRF-TOKEN` ever sent by the JS, every cookie-JWT non-GET call (`/host/save_config`,
`run_simulation`, `/post_nodes_edges`, `/refresh_access`) should be CSRF-rejected in production —
yet the product appears to work. Either prod doesn't run MODE=prod as configured here, or my
reading of flask-jwt-extended CSRF is wrong, or writes genuinely fail and are unexercised.
Why not settled: no prod env/access in the repo; CI forces MODE=dev (`full_test.yml` sed) so
nothing ever tests prod CSRF. Unblock: run a local MODE=prod compose (point YANDEX_* DB vars at a
local Postgres with sslmode=disable), log in, POST `/host/save_config` and `/refresh_access`,
observe pass/fail; if failing, that is a live prod bug and the #1 priority before any auth design.

D2 — **Which mobile slice is the real MVP.** I infer "theory quiz + results + emulation status"
from code, but the maintainer's actual Android scope (theory-only? practice-in-webview? progress
dashboard? notifications for async exam grading?) is a product decision, not a code fact.
Unblock: a short product-scope doc/interview listing the target screens; this fixes the API
file set that the 85 % gate covers (F6) and which HTML routes need JSON variants.

D3 — **Synchronous practice self-check latency budget.** Actual p50/p95 of `/quiz/session/answer`
(practice) on production hardware under real celery queue load, vs the 60 s nginx/uwsgi default
timeout, determines whether the async job path (F5) must ship *before* any mobile API for
practice. Unblock: instrument a real stack run (server logs + timing on the practice answer
endpoint), plus a timeout map of nginx→uwsgi→celery for `/quiz/*`.

D4 — **Org/multi-tenancy product model.** Whether per-org test spaces are a sold segment and
whether "published + in-org" scoping must be enforced server-side before the API opens (F7).
Unblock: product decision on the org model + a policy test suite; today's thin enforcement may be
intended (all tests public) or a gap.

D5 — **Which API host/domain.** One central `api.miminet.ru`, same-origin per org subdomain, or
per-org API domains? This interacts with cookie domain `.BASE_DOMAIN`, org `domain` columns and
CORS/`ALLOWED_HOSTS`. Unblock: D2 + deployment/nginx topology decision; only then can token/cookie
scoping and CORS policy be finalized.

D6 — **Framework verdict (Flask-fit).** Business lens prior = KEEP (F12), but the final word is
lens-B's system-architecture analysis against the actual request mix (share of `/web_network`,
`/quiz/*`, `/ai/*`, JSON-vs-HTML from real nginx access logs). Unblock: lens-B report + real
access-log request-mix profile. If Flask stays, only Option 1 is on the table.

D7 — **API docs/SDK generation tooling.** OpenAPI spec + (later) a generated Android client is
unblocked only by the contract decision (F8) and the versioned facade existing. Cheapest gate
experiment before any tool: hand-write the OpenAPI YAML for the v1 slice and confirm the facade
routes satisfy it mechanically (a contract test), before adopting a generator.

## Ideas (rough — on the record)

- **Grading-engine unit suite first.** Start the browser-free 85 % investment at
  `check_host_service`, `check_practice_service`, `session_question_service.answer_*`,
  `network_upload_service`, `json_schema_validation`, dto serializers: pure-logic, DB-light,
  currently ~2–17 % covered, business-critical. Cheap win, immediately useful, no app seam needed.
- **A "route contract test"** in CI that iterates the declared API-slice route table and asserts:
  response `Content-Type` is `application/json`, body parses, and a JSON-schema (or OpenAPI ref)
  validates. Cheap, catches the exact classes of bugs in F4 the day they land.
- **Reuse quiz DTOs as the wire format** for the v1 JSON variants of HTML routes (test list with
  progress, section list, question payload, session results already exist as `*Dto.to_dict()` /
  `session_result` dicts). Do not write a second serialization layer.
- **Job-based practice check as an evolution of the exam path** — exam async check
  (`check_network_task` → celery → poll session_question.is_correct) is the existing template; the
  in-session self-check should converge on it, which also kills the retry-re-grades and timeout
  classes at once (F5). The mobile client then only needs "submit → poll" semantics.
- Standardize HTTP codes now (200/201/202/4xx), drop `210` ("in process" → 202 with a status
  body), because a frozen spec can't contain ad-hoc codes.
- Put nginx-level rate limits on `/auth/*`, `/refresh_access`, `/ai/*` before any public mobile
  client; keep them out of app code.
- Consider exposing `/ai/generate-task` as JSON in v1 (`{technologies,difficulty,masks,model}` →
  `{guid}` or async `{job_id}`) since teacher-facing AI is a plausible differentiator and its
  current form (302 + form fields) is the least API-like route on the board.
- If org subdomains keep a separate cookie domain, an `api.*` host can reuse `.BASE_DOMAIN`
  cookies for web and bearer for native — one auth story, two transports.
- Moscow-hardcoded timezone logic (`session_question_service.py`/`dto.py` MOSCOW_TZ,
  `results_available_from` comparisons) is fine for a RU product but belongs in a config seam
  before international orgs use it.
