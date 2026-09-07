# D1 — prod-CSRF reality check (executed 2026-09-06, Batch 14)

## Aim
Deferred experiment D1 (architecture review lens-A): the reviewer flagged that
`MODE=prod` sets `JWT_COOKIE_CSRF_PROTECT=True` (front/src/app.py:134) while no
browser JS ever sends `X-CSRF-TOKEN` (flask-jwt-extended double-submit) —
"under that reading every cookie-JWT write should fail in prod yet the product
works." Verify empirically with a staged `MODE=prod` app before any
auth/contract work.

## Setup (exact recipe)
- Built `miminet-front:d1-prod` from the **batch14/app-seam** branch worktree
  (PR-A seam needed so `MODE=prod` can run against a throwaway DB without
  Yandex creds). `podman build -t miminet-front:d1-prod -f front/Dockerfile .`
- Ran the staged app (Flask dev server, not uWSGI):
  ```
  podman run -d --rm --name miminet-d1i \
    -e MODE=prod \
    -e SQLALCHEMY_DATABASE_URI="sqlite:////tmp/d1.sqlite" \
    -e JWT_SECRET_KEY="d1-test-secret-..." \
    -e ALLOWED_HOSTS="http://localhost" \
    -p 18099:80 --entrypoint /bin/bash miminet-front:d1-prod \
    -c "cd /app && python3 -c 'import app as a; import miminet_model as m; m.init_db(a.app)' && exec python3 -c 'import app as a; a.app.run(host=\"0.0.0.0\", port=80)'"
  ```
  `init_db` auto-created the schema on the override sqlite (MODE=prod path skips
  Yandex bootstrap because the env seam is set).
- Minted valid access+refresh JWT cookies inside the container with the app's
  own secret (`create_access_token`/`create_refresh_token` +
  `set_access_cookies`/`set_refresh_cookies`), then drove curl with explicit
  `Cookie:` headers (cookies carry `Secure` so plain-HTTP curl needs the manual
  header; the CSRF-relevant behavior is transport-independent).

## Results
| # | Request | Result |
|---|---------|--------|
| T1 | POST `/refresh_access`, refresh cookie, **no CSRF header** | **HTTP 302 → login** (rejected) |
| T2 | POST `/refresh_access`, cookie + `X-CSRF-TOKEN` | HTTP 200 `{"msg":"access token refreshed"}` |
| T3 | GET `/host/save_config`, access cookie, no CSRF | HTTP 400 "expected POST" (**JWT accepted**, handler reached) |
| T4 | POST `/host/save_config`, access cookie, **no CSRF header** | **HTTP 302 → login** (rejected) |
| T5 | POST `/host/save_config`, cookie + `X-CSRF-TOKEN` | HTTP 400 "no net_guid" (**JWT accepted**, handler reached) |
| T6 | POST `/host/save_config`, browser-exact (`X-Requested-With: XMLHttpRequest`), **no CSRF** | **HTTP 401 `{"msg":"Missing token"}`** (rejected as CSRF) |
| T7 | POST `/host/save_config`, browser-exact + `X-CSRF-TOKEN` | HTTP 400 (handler reached) |
| T8 | POST `/refresh_access`, browser-exact, no CSRF | HTTP 401 (rejected) |
| T9 | GET `/refresh_access`, refresh cookie, no CSRF | HTTP 200 (**safe method exempt**) |

## Verdict — the reviewer's reading is CONFIRMED at code level
- Every real browser write path is cookie-JWT `@jwt_required`: the network
  editor saves go through `PostNodesEdges`/`UpdateEdgeConfiguration`
  (`netfront_f.js`, POST `/post_nodes_edges`, `/edge/save_config`) and the
  `/host/*_save_config` group; token refresh is POST `/refresh_access`. **None
  send `X-CSRF-TOKEN`; no JS reads the `csrf_access_token`/`csrf_refresh_token`
  cookie** (grep of all templates + static JS found zero CSRF usage).
- Under literal `MODE=prod` (what `run_app.sh` defaults to and
  `docker-compose-prod.yml` inherits from `.env`), **every such POST fails**
  (CSRF double-submit missing) → the client-side 401 path would chain a refresh
  POST that ALSO fails CSRF → user bounced to login. Writes are effectively
  broken under the prod config as written.
- **Why "the product works":** the current live stack (this host's compose +
  `front/.env:35`) sets `MODE=dev` → `JWT_COOKIE_CSRF_PROTECT=False`. The dev
  config is what actually runs; prod-as-configured has never been exercised via
  cookie-JWT writes. (Real miminet.ru `.env` is out of reach — not read; do not
  touch secrets.)
- Corollary: `JWT_COOKIE_SECURE=True` under prod also makes cookies HTTPS-only;
  same conditional dead-config story.

## Consequences for auth/contract work (PR-C) and beyond
1. Do NOT ship "MODE=prod fixes" blind: the correct remediation is a product
   decision (deferred). The safe, additive, low-risk step that ALSO works today
   is **adding `"headers"` to `JWT_TOKEN_LOCATION`** so an API/bearer client can
   authenticate without the cookie/CSRF path at all — headers tokens are exempt
   from CSRF double-submit by design.
2. If prod is ever truly run as `MODE=prod` with cookie auth, the browser must
   send `X-CSRF-TOKEN` from the csrf cookie — a real bug fix candidate, but it
   needs the product decision (D2) + a regression path, NOT a silent config
   flip in this batch.
3. Recording here makes the state explicit so no future batch "assumes prod
   CSRF works."

## Artifacts/cleanup
- Image `miminet-front:d1-prod` kept (reusable for later D2/auth experiments).
- Container `miminet-d1i` and earlier d1* attempts stopped/removed; logs in
  `.tmp/d1-*.log`. Host prod stack (miminet/nginx/postgres/rabbitmq/selenium)
  untouched throughout (alternate port 18099, throwaway sqlite).
