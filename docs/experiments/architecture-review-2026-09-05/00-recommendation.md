# Architecture & tooling review — recommendation summary (2026-09-05)

Authoring agent synthesis of three parallel lens reviews (business / system
architecture / tooling). Full evidence in `lens-A-business.md`,
`lens-B-architecture.md`, `lens-C-tooling.md` (all written by read-only
reviewer subagents; role `docs/architecture_review_role.md` v1.0).

## Question gated
"Probably Flask is not the best solution for the current server" — the
maintainer hypothesis that the front server may need a framework/architecture
change before the **85% browser-free front-API coverage** aim (motivated by a
future non-browser/Android client) is worth its investment.

## Verdict: KEEP Flask — the hypothesis is NOT supported by usage evidence
All three lenses converge independently on the same bottom line:

- **Flask is a fit.** Long work is already offloaded to celery (emulation,
  exam-task checking); the HTTP mix is DB CRUD + Jinja page renders + small JSON
  writes + enqueue/poll (lens-C concurrency reality; uwsgi 5×1 + nginx + rabbitmq
  all wired). No recorded latency/QPS problem exists at classroom scale. ASGI
  would buy nothing measurable for this mix; the real concurrency ceilings are
  sync-emulation-in-request paths (F7 lens-B, F2 lens-C), which are
  **framework-agnostic**.
- **The migration cost is prohibitive for zero measured gain.** ~79 routes,
  Jinja page layer, dual auth (flask-login + cookie-JWT), flask-admin CRUD
  (820 LOC, no ASGI parity), Migrate→alembic, uwsgi/run_app/Dockerfile/nginx
  layers, and the celery↔Flask import coupling in `tasks.py`. Weeks of churn
  across the hardened Selenium/CI/uv/compose stack. DEFER (lens-C E2 gate: a
  real load harness + target QPS first).
- **What a future Android client actually needs is NOT a framework change.**
  It is an API contract: bearer token transport
  (`JWT_TOKEN_LOCATION=["cookies"]` → add `"headers"`, `app.py:131`), one error
  envelope, JSON reads (none exists for a network document today), request-schema
  validation, route versioning. All available as Flask add-ons; none require a
  rewrite.

## The 85% aim was miscast — correct it before investing
The literal goal ("85% browser-free over `front/src`") would force coverage
theater on ~10k lines, most of which (Jinja renders, cytoscape editor chrome,
flask-admin, marketing pages, redirects, sitemap) is browser-only by nature
and already gated by the Selenium e2e suite. **Correct gate: 85% line over a
declared API/controller+service file set**, PLUS unit coverage of the grading
engine. Highest-ROI first:
1. **Grading engine** — `quiz/service/check_host_service.py` (706 LOC @ ~2%),
   `check_practice_service.py` (353), `session_question_service.answer_*`,
   `check_network_service.py`, `network_upload_service.py`. Pure dict→(points,
   hints) logic, no flask/ORM at its core; a regression silently changes every
   student's score. Cheapest, most valuable slice.
2. **The ~10 unrouted quiz controller endpoint functions** (defined, never
   URL-registered) — free unit targets needing only request mocks.
3. **The declared API slice** once the seams below land.

## MUST-FIX seams (what the coverage work actually depends on)
Ordered cheapest-first (lens-B §"What must change…"):
1. **App construction seam (F1):** `SQLALCHEMY_DATABASE_URI` env override
   (~3 lines at `app.py:238`) or a thin `create_app()` factory. Verified the
   model layer already runs on sqlite (`create_all` of all 14 tables works);
   the import-time `app = Flask(...)`/`db.init_app`/Admin construction is what
   freezes config. Cost ~0.5-1 d.
2. **Celery boundary as a test seam:** patch `app.send_task` /
   `create_emulation_task` at ~5 call sites; module-global celery app means one
   `monkeypatch` per test, no broker needed.
3. **Filesystem-root seam (F5):** CWD-relative `static/pcaps` writes etc →
   configurable `STORAGE_ROOT`, so tests pin `.tmp`.
4. **DB migrations gap (F2):** flask-migrate is wired but no `migrations/`
   dir exists; schema changes are manual ALTER on prod. Alembic baseline needed
   for both prod evolution and honest CI schema parity (1-2 d, medium risk).
5. **Auth/contract for the client (F3):** bearer JWT + `/api` JSON reads +
   uniform envelope + validation. Additive; orderable independently.

## Product/contract recommendations (from lens A)
- Freeze a **versioned JSON facade** (e.g. `/api/v1/*` blueprint delegating to
  the existing quiz service/facade layer) rather than mutating the mixed
  HTML/JSON routes the browser uses — the facade is the stable contract; legacy
  paths evolve freely. Thin blueprint + jsonify; no framework change.
- Mobile MVP slice (product decision, deferred D2) is quiz consumption +
  results + emulation status; practice/editor stay desktop. That decision fixes
  the 85% file set.
- **Live-prod risk flagged (deferred experiment D1, lens A):** MODE=prod has
  `JWT_COOKIE_CSRF_PROTECT=True` and no `X-CSRF-TOKEN` is ever sent by the JS.
  Under that reading every cookie-JWT write should fail in prod — yet the
  product works. Verify with a local MODE=prod compose before any auth work.
- Authz gaps on quiz endpoints (session ownership, is_ready, retake policy)
  are business-critical if the API opens (F2/F7 lens A).

## KEEP (do not touch)
- **Selenium e2e suite** (decision 2026-09-04 stands); the browser-free tier
  complements it on the API/grading slice.
- **Back emulation core** (`back/src`) — healthiest subsystem; the back unit
  series (#491–#494) + coverage gate already serve it.
- **uv workspace / ruff+ty / requirements.txt stays dead** (never reintroduce).

## Deferred experiments (with unblock chains — see lens files for full text)
- **D1 (lens A): prod CSRF reality.** Unblock: local MODE=prod compose, POST
  `/host/save_config` + `/refresh_access`, observe pass/fail.
- **D2: mobile MVP scope** (product decision) → fixes the 85% file set.
- **D3: synchronous practice-check latency budget** vs the 60 s nginx timeout
  → decides whether async practice-check must ship before mobile API.
- **E1 (lens C): 85% file set + baseline + fail-under** (back precedent:
  measure 76.15 → gate 75). Unblock chain: seam (1) above → first endpoint
  tests → measure → set fail-under at baseline−1.
- **E2: FastAPI-vs-uwsgi throughput** — gate on a real load harness + target
  QPS before ANY migration; evidence says WSGI is not the bottleneck.
- **E3: /ai/generate-task fix selection** (celery-offload vs more workers).
- **E4: dual-stack (new FastAPI API service) cost spike** — only after the
  product decision to productize an external API + contract choice.
- **E5: uwsgi reproducibility** (pin in uv or Dockerfile).
- **E6: bearer vs cookie auth transport** (config-level; `["cookies","headers"]`).

## Recommended next batch (awaiting maintainer gate)
**Do NOT start an 85% sweep yet.** Recommended order:
1. Land the app-construction seam (F1) as a small upstream PR + wire the front
   coverage job (lens-C F3) mirroring `back_test.yml` (coverage → front dev
   group via uv.lock only; raw `coverage` CLI, not pytest-cov; explicit
   browser-free file list as an array with the empty-slice guard).
2. Measure the honest baseline over the API/controller+service file set.
3. First coverage PRs = grading engine + unrouted quiz controllers.
4. Resolve deferred D1 (prod CSRF) before any auth-contract work.
