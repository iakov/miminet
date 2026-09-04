# 02 — DSL surface to port + Playwright sizing

The port surface is `front/tests/conftest.py` (MiminetTester + fixtures) and
`front/tests/utils/networks.py`. `utils/locators.py` and `utils/checkers.py` are
framework-agnostic and transfer almost untouched. Test files change only at
imports/call sites that reference Selenium `By` or WebDriver-typed annotations.

## 2.1 `MiminetTester` (conftest.py:51-309) — method inventory

Subclasses `WebDriver`, so tests and `utils/networks.py` freely use WebDriver
methods *plus* the helpers below. Methods to re-implement over a Playwright
page/context (file:line of definition, current Selenium idiom):

| method (line) | Selenium idiom today | Playwright idiom |
|---|---|---|
| `wait_and_click(by, el, timeout, scope)` (57) | loop + `EC.element_to_be_clickable` + re-find on `StaleElementReference`; scoped variant re-finds a container (95) | `locator.click()` — auto-waits actionable & auto-retries on detach. Scope = locator chaining `container.locator(sel)`. Whole 45-line loop collapses |
| `drag_and_drop(src, dst, x, y)` (116) | `ActionChains` click_and_hold/move/release + stale retry | `page.mouse.down/move/up` after resolving bboxes (`bounding_box()`); element-under-cursor differs (SVG canvas). Small rework (~20 lines) |
| `exist_element(by, el)` (154) | `len(find_elements) > 0` | `locator.count() > 0` |
| `wait_until_appear` (165) | `EC.visibility_of_element_located` | `locator.wait_for(state="visible")` |
| `wait_until_disappear` (178) | `EC.invisibility_of_element_located` | `expect(locator).to_be_hidden()` / `state="hidden"` |
| `wait_until_text(by, el, text)` (191) | `EC.text_to_be_present_in_element` | `expect(locator).to_have_text(text)` or `.to_contain_text` |
| `wait_until_value(by, el, value)` (204) | poll `get_attribute("value")==value`, stale-safe | `expect(locator).to_have_value(value)` |
| `wait_for(condition)` (228) | `WebDriverWait(...).until(condition)` — condition takes the driver | `expect.poll` / `page.wait_for_function` (conditions that call `driver.execute_script` need an adapter — see §2.4) |
| `run_in_modal_context(by, el)` (237-254) | wait appear → yield element → wait disappear | contextmanager over `locator.wait_for(state="visible")` … `expect(...).to_be_hidden()`; element handle → scoped locator, no yield of a DOM handle needed |
| `select_by_value(by, el, value)` (256) | `Select(...).select_by_value` + stale retry | `locator.select_option(value=value)` (auto-wait) |
| `get_logs`/`get_console_messages` (281/298) | wire `Command.GET_LOG` (remote WebDriver has no `get_log` in Selenium 4 — #486 latent bug) | no direct analog; Playwright records via `page.on("console")`/`context.on` — see 01 §1.4 |
| WebDriver methods used *directly* by tests/networks | `find_element(s)`, `get(url)`, `refresh()`, `.title`, `.current_url`, `execute_script`, `execute_async_script`, `add_cookie`, `close/quit` | mapped: `page.locator`, `page.goto`, `page.reload`, `page.title`, `page.url`, `page.evaluate`, cookie via `context.add_cookies` |

## 2.2 `MiminetTestNetwork` (networks.py:42-266)

- `__build_empty_network` (112) → goto HOME, click `#new-network-button`, wait
  for `#network_scheme`, capture URL. ~1:1.
- `nodes`/`edges`/`jobs` properties (68-83) read the global JS graph
  (`execute_script("return nodes")`) → `page.evaluate("() => window.nodes")`.
  Same serialization semantics; JSON returns unchanged.
- `__calc_panel_offset` (85-110) reads `panel.rect` (Selenium geometry) →
  `element.bounding_box()`. Pure math, unchanged.
- `add_node` (162-197) drags a palette item onto the panel at a %-offset.
  Uses `drag_and_drop` → Playwright mouse. **Highest-fidelity risk.**
- `add_edge` (199-218) is already JS-driven (`AddEdge`, `DrawGraph`,
  `PostNodesEdges`) → evaluate, then wait for `len(edges)` to grow.
- `open_node_config`/`open_edge_config` (131/148) → `ShowHostConfig(node)` etc.
  evaluate + wait for config form. 1:1.
- `run_emulation` (230-248): defined but **called by no test** today (verified:
  only `test_packet_filters` reads `packets` after clicking the emulate button
  path itself); click + wait + `execute_script("return packets")`.
- `delete` (250-265): OPTIONS → DELETE modal → submit. Plain clicks.

## 2.3 `NodeConfig` (networks.py:268-644) + `NodeType` (17-39)

- `NodeType.*` are `(By.CSS_SELECTOR, "#…")` tuples (17-39). Playwright needs
  engine-bearing locator specs; a thin `By`-compat translation in the DSL keeps
  the ~79 `add_node(NodeType.X)` call sites byte-identical (Batch 9 typed these
  as `tuple[str, str]` — keep that annotation, add a translation step).
- `name`/`default_gw` (284-303) → `input_value()`.
- `fill_link`/`__fill_link_field`/`fill_links` (305-359) — the #488 de-flaked
  path: waits for the async-rendered ip/mask xpath rows, then a clear+type
  re-find loop. Playwright `locator.fill()` (auto-wait + real value set) replaces
  the whole retry loop; xpath rows still valid (`xpath=…`).
- `enable_stp`/`disable_stp` (361-424) — `run_in_modal_context` + scoped
  `wait_and_click` inside `#RstpModal_<id>`; inner ids (`#stp`, `#none`,
  `#rstpConfigurationSubmit`) are NOT globally unique (#482 lesson) → the
  scoped-locator pattern must be preserved; Playwright chaining makes this
  cleaner, not harder.
- `add_jobs` (426-459) — dispatch on tag (`input`/`select`), clear+send_keys
  vs `select_by_value`. `fill()` + `select_option`; the tag-name introspection
  can disappear.
- `configure_vlan` (489-556) — table-row xpath walking + per-row `<input>` and
  `<select>`. Locator + `.row` indexing; needs the same `get_table_row_xpath`
  (locators.py:202). Moderate rework.
- `submit` (557-570) — click submit, then wait until its "Сохранить" text is
  back (i.e. save finished). `expect(locator).to_have_text("Сохранить")`.
- `__open_config`/`__check_config_open` (587-643) — JS show-* + wait for form +
  error-modal scan. 1:1.

## 2.4 The two real "rework" seams

1. **`wait_for(condition)` conditions that call `driver.execute_script`** — used
   heavily (`test_packet_filters.py:49-53,75-79,135-138,…`; `networks.py:196`,
   `test_duplication.py:64,95`). Each `lambda driver: driver.execute_script(...)`
   needs an adapter to `page.wait_for_function(js)` or `expect.poll(lambda:
   page.evaluate(js))`. Mechanical but touches every call site.
2. **`execute_async_script`** (only `test_duplication.py:31`) — Selenium's
   callback-based in-page fetch poll. Playwright `page.evaluate` awaits promises
   natively, so the `_server_edge_duplicate` helper becomes a promise-returning
   `page.evaluate(fetch → parse)` + `expect.poll`. Same semantics, less code.

## 2.5 Auth/login flow (conftest.py:25-48, 312-398)

- `testing_setting` reads `TEST_TARGET_HOST`/`TEST_TARGET_PORT` (default
  `172.18.0.2:80`) and `SELENIUM_HUB_URL`. Playwright removes the hub var;
  host/port still needed (CI reaches the app at `localhost`).
- `requester` (session) — `requests.Session`, POST `//auth/login.html`, cookie
  capture. **Pure HTTP; keep unchanged** (also `test_basic`'s 6 HTTP tests).
- `chrome_driver` (session) — the headless WebDriver against the hub. Replaced
  by a session-scoped Playwright `browser`/`context`/`page`.
- `selenium` (session) — gifts `requester`'s JWT cookies
  (`access_token_cookie`, `refresh_token_cookie`) into the browser via
  `add_cookie`. Playwright: `context.add_cookies(...)` (cookie domain/path/
  sameSite fields map 1:1), or pre-auth via an authed APIRequestContext and
  `storage_state`. The session-scoped **single-tab** model is load-bearing (see
  `05-risks`); keep it.
- Mock fixtures (`mock_env_dev/prod`, `mock_psycopg2`, `mock_db`) are backend
  unit-test support (conftest 407-456) — unchanged.

## 2.6 Grid vs local-driver differences

Today there is **no local-driver path** — everything goes through the remote
hub (`front/tests/docker/docker-compose.yml`, selenium/hub:4.37.0 +
node-chrome:141.0; runbook Batch 6/7 grid facts). Playwright kills this axis:
a Playwright Chromium launched directly on the CI runner (or in its own
container) replaces hub+node, so hub-specific concerns — readiness race
(`/wd/hub/status` polling, `742d79a`), no-HEALTHCHECK, session-create reset
cascades, GRID_TIMEOUT — all vanish. What must instead be handled is
Playwright's own browser download + OS deps (`05-risks`).

## 2.7 Playwright equivalent sizing (lines)

Preserve the public DSL API so the ~20 e2e files need only import/annotation
edits (not body rewrites):

- strategy translation (`By.CSS_SELECTOR/XPATH/ID/TAG_NAME` → Playwright engine
  strings, incl. a `By` shim so existing imports/`NodeType` tuples keep
  working): ~40
- `MiminetTester`-equivalent wrapper over `page` (helpers in §2.1 + evaluate/
  navigation/cookie shims): ~200-260 (many methods shrink to 2-5 lines because
  auto-wait absorbs the retry loops; the `wait_for` adapter + drag_and_drop are
  the growth points)
- conftest session fixtures (browser/context/page + auth injection + console
  recorder if kept): ~70-90
- `utils/networks.py` re-implementation with the same class/API (loops collapse
  to `fill()`/`select_option()`/locators): ~300-360 (vs 644 today)
- `locators.py` (412) and `checkers.py` (78): unchanged

**Total new/rewritten DSL+fixture code ≈ 450-550 lines** for the
API-preserving port — consistent with (slightly above) the prior study's
"~400 lines" ballpark, because the auto-wait absorption only pays off once
`utils/networks.py` is converted too. If instead every test is rewritten to
idiomatic Playwright (drop the DSL, `page.get_by_role` etc.), expect higher
total diff but a net *smaller* long-term DSL; that is the Phase-6 option
(`06-sequencing`), not the pilot.

Framework-agnostic and reusable verbatim: all 109 `Locator`/`DeviceLocator`
consts in `locators.py`, `TestNetworkComparator` (checkers.py), the JSON
fixtures (nodes/edges/jobs literals) inside each test class, the `requester`
fixture, and pytest structure/parametrization.
