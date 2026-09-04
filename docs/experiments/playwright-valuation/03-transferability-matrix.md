# 03 — Transferability matrix

Classification: **1:1** = semantics preserved with a direct Playwright
equivalent (possibly inside the DSL wrapper, no test-body change);
**rework** = a test/helper body must change (mechanism differs, intent same);
**drop/blocked** = mechanism has no Playwright analog or pins Selenium-only
behavior and must be decided.

## 3.1 Per DSL surface area

| Surface | Ref | Transfer | Notes |
|---|---|---|---|
| CSS selectors (`Location.*.selector`) | locators.py:29-31, all 104 `Locator(` | 1:1 | Valid Playwright CSS. Value on `#` ids unchanged. |
| XPATH locators / generated xpaths | locators.py:34-36, 86-91, 202-207, 378-392 | 1:1 | Playwright `xpath=` engine. Fragile `/html/body/...` absolute paths (e.g. `get_ip_field_xpath`, locators.py:384) transfer as-is (fragility is orthogonal to the driver). |
| Text-bearing locators (`text=`) | locators.py:103, 168, 213, 253, 262 (`Locator(selector, text=…)`) | rework (small) | Today only used as the *expected* text in `submit()`'s `wait_until_text` (networks.py:565) — becomes `expect(...).to_have_text`. Playwright `text=`/`get_by_text` exists if wanted later. |
| `NodeType` tuples + `add_node` | networks.py:17-39, 162-197 | 1:1 (via `By` shim) | Keep `tuple[str, str]` API (ty-gate, Batch 9) + translate inside DSL. Drag-onto-canvas fidelity is the risk (see drag). |
| wait helpers (`wait_until_*`, `wait_for`) | conftest.py:165-235 | 1:1 / rework | `appear/disappear/text/value` are 1:1 (`wait_for`+`to_have_*`). `wait_for(callable-taking-driver)` needs a per-call-site adapter (02 §2.4) — rework. |
| `wait_and_click` + `scope=` | conftest.py:57-114 | 1:1 | Auto-wait + actionability replaces the retry loop; `scope` = locator chaining. **Also removes the #482/#488 stale-element flake class** that motivated `scope=` in the first place. |
| `run_in_modal_context` | conftest.py:237-254 | 1:1 | contextmanager over hidden/visible states. Modal inner ids not globally unique (#482) → scoping preserved. |
| `select_by_value` | conftest.py:256-279 | 1:1 | `select_option(value=…)`. |
| `exist_element` | conftest.py:154-163 | 1:1 | `count() > 0`. |
| `drag_and_drop` (ActionChains) | conftest.py:116-152; networks.py:190 | **rework** | Playwright `mouse` needs element `bounding_box()` + `page.mouse.down/move/up`; SVG-canvas element-under-pointer semantics differ from W3C action pointers. Pilot must validate (04). |
| JS reads of graph globals (`nodes/edges/jobs/packets/packetFilterState`) | networks.py:68-83,246; packet_filters.py:99-115,145,160 | 1:1 | `page.evaluate("() => window.nodes")` etc. Same page-main-world execution. |
| `execute_script` with jQuery (`$.ajax`, `$('#edge_source').val()`, `.modal('hide')`) | job_limit.py:168-191; device_connecting.py:48-49; packet_filters.py:22,31 | 1:1 | Playwright evaluate runs in the same main world where jQuery loads. Return-value serialization identical for plain JSON. |
| `execute_async_script` fetch poll | duplication.py:18-32 | rework (small) | Promise-awaiting `evaluate` + `expect.poll`. Same server-parse regex. |
| `get_logs`/`get_console_messages` (GET_LOG wire) | conftest.py:281-309; get_logs.py | **drop/decision** | No Selenium wire command in Playwright. Console capture moves to `page.on("console")`. No e2e test consumes it today (01 §1.4) → recommend dropping the browser helper, re-pinning console behavior only if ever needed. |
| session-scoped single-tab fixtures + cookie gift | conftest.py:312-398 | rework | Playwright normally isolates per-test contexts; suite semantics depend on ONE tab carrying network JS state. Keep session `browser`/`context`/`page` + `context.add_cookies`. |
| comparators (`TestNetworkComparator`) | checkers.py:9-78 | 1:1 | Pure Python; zero Selenium references; JSON fixtures untouched. |
| `requester` HTTP fixture | conftest.py:332-362 | 1:1 | Pure `requests`; keep for basic.py + as the auth source. |
| pytest structure / parametrized class fixtures | all `network` fixtures | 1:1 | pytest unchanged; Playwright fixtures must nest under pytest session scope. |

## 3.2 Per file (browser-backed)

Shorthand: J = heavy JSON comparator, C = class-scoped `network` fixture, R =
needs helper rework beyond imports, e = uses `execute_script`.

| file | transfer | why |
|---|---|---|
| `device_configure_names.py` | 1:1 | Build + fill + submit; no raw driver reads. |
| `device_connecting.py` | 1:1 | 10-edge class fixture; only driver use is `$('#edge_source').val()` evaluate (48-49). |
| `dhcp.py` | 1:1 (J, C) | Standard config + comparators. |
| `down_link.py` | 1:1 (J, C) | Standard config + comparators. |
| `duplication.py` | R | `execute_async_script` poll (18-32) → promise evaluate; edge-config duplicate field fill. |
| `fields_filter.py` | R (light) | Raw `find_element(...).get_attribute("value")` asserts (31-36, 59-65) → `input_value()`; direct `select_by_value` (50) fine; `add_jobs` w/ raw-string field ids (82-86) — typo-prone ids unchanged. |
| `get_logs.py` | drop/decision | Pins Selenium GET_LOG wire tuple (33); see 3.1. |
| `ipip_gre.py` | 1:1 (J, C, param) | Giant fixture is pure DSL calls + comparators. No `delete()` (leak on the current Selenium path too — carry over, don't "fix" in port). |
| `job_edit.py` | R (light) | Dynamic-id click `#config_host_job_edit_<id>` (42) → locator; `wait_until_value`+clear/send_keys (46-57) → `fill()` after value-wait. The #488 render race it used to trigger is the flake class auto-wait should eliminate. |
| `job_limit.py` | R (light, e) | Promise-`$.ajax` delete (168-191) → evaluate; 30-job loops unchanged. |
| `nat.py` | 1:1 (J) | DSL + comparators only. |
| `network_menu.py` | 1:1 | Navigation, `current_url` asserts, `.text` read (29-31). |
| `packet_filters.py` | R (e) | Heaviest `wait_for(lambda driver: execute_script)` use (49-96, 135-138, 204-322) → `page.wait_for_function`/`expect.poll`; jQuery modal-hide cleanup + JS-click fallback (22-46); reads `packets`/`packetFilterState`. Best end-to-end stress of the evaluate-adapter. |
| `ping_and_copy.py` | 1:1 | Copy-network modal (52-61) + URL-built `MiminetTestNetwork(selenium, url)` (61) + comparators (64-66). |
| `port_forwarding_tcp_udp.py` | 1:1 (J, param) | Router selects + fields + comparators. |
| `router_cycle.py` | 1:1 (J) | DSL + comparators. |
| `sleep.py` | 1:1 (J, C) | DSL + comparators. |
| `stp.py` | 1:1 (C) | Exercises `enable_stp`/`disable_stp` → the scoped-modal DSL (networks.py:361-424) and 2 `refresh()`. **Pilot file** (modal scoping is the #482/#484 flake epicenter). |
| `tcp_udp.py` | 1:1 (J, param) | 5 device types, `fill_default_gw`, per-link masks, server/host tcp+udp jobs. **Pilot candidate** for device/job breadth. |
| `user_options_input.py` | 1:1 (C, 34 tests) | Only DSL calls + JS `network.jobs[-1]` asserts; the 7-case params re-run the same path. Cheap to include in a batch. |
| `vlan.py` | R (C) | `configure_vlan` modal-table driver (networks.py:489-556) + `refresh()` between switches (51). The xpath table-row walk is the fiddly bit. |
| `basic.py` (`test_auth` only) | 1:1 | `selenium.title` → `page.title()`. |

Backend-unit files (`ai_generate`, `config_db`, `quiz_organization`,
`quiz_progress`) and `test_basic`'s 6 `requester` tests: **not part of the
port** (no browser).

## 3.3 Selenium-isms → Playwright idioms cheat-sheet

| Selenium-ism | where | Playwright replacement |
|---|---|---|
| implicit `WebDriverWait` + `EC.visibility_of_element_located` | conftest 165-176 | `locator.wait_for(state="visible")` |
| `EC.element_to_be_clickable` | conftest 90 | `locator.click()` actionability auto-wait |
| stale-element re-find loops (`StaleElementReferenceException`) | conftest 100-101, 151-152, 278-279; networks 333-347 | auto-retry built into locators; loops deleted |
| `find_element(...).get_attribute("value")` | fields_filter 36,64; networks name/default_gw | `input_value()` |
| `Select(...).select_by_value` | networks 546; fields_filter 50 | `select_option(value=…)` |
| `.text` | network_menu 31 | `text_content()` / `inner_text()` |
| `.refresh()` | stp 45,50; vlan 51 | `page.reload()` |
| `.title` / `.current_url` | basic 11; network_menu 24,42 | `page.title()` / `page.url` |
| GET_LOG wire hack | conftest 295 | none (console events) |
| `chrome_options.add_argument("--headless")` etc. | conftest 315-322 | `chromium.launch(headless=True, args=["--no-sandbox"])`; `--window-size` = `viewport` on the context |
| remote hub session create/readiness | CI + conftest 30, 324 | no hub; direct browser launch |

Bottom line: **~2/3 of the browser-backed suite is import/annotation-only
1:1**; the remaining third clusters in: (a) `wait_for(driver-callable)` adapters
(packet_filters, job_limit, duplication, networks), (b) the 3 mouse/canvas
paths (`add_node` drag, VLAN table, STP modal inner clicks), (c) auth/session
fixtures, (d) the `get_logs` decision. That concentration is exactly what a
3-file pilot can bound.
