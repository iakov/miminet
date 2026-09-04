# 01 — File/test inventory + utility import graph

All measurements on this checkout (fork `main`, upstream tip `0c20696` + 2
fork-local commits). Counts from a browser-free `pytest --collect-only -q .` in
`front/tests` (repo `.venv`): **26 files, 118 collected tests** (the "114" in
runbook/AGENTS figures predates `test_get_logs.py`'s 4 tests from #487; 114+4 =
118 exactly).

## 1.1 Split: browser-backed vs non-browser

- **True Selenium e2e (browser-backed): 20 files, ~83 collected tests.** These
  consume the `selenium` fixture — directly in the test body or transitively via
  a class/function `network` fixture built on `selenium`
  (`MiminetTestNetwork(selenium)`, e.g. `test_user_options_input.py:9`,
  `test_stp.py:10`, `test_device_connecting.py:12`). **This is the port surface.**
- **Non-browser (untouched by a migration): ~35 collected across 6 files**
  - Backend unit/mock tests parked top-level: `test_ai_generate.py` (9),
    `test_config_db.py` (7), `test_quiz_organization.py` (6),
    `test_quiz_progress.py` (3) — no `selenium`/`requester`, import back modules
    (`app`, `miminet_model`, `ai_generate`, `quiz.util.dto`).
  - `test_basic.py` 6 of 7 tests are HTTP-only (`requester`, line 17) —
    browser-free already; 1 browser test (`test_auth`, line 7).
  - `test_get_logs.py` (4) — browser-free unit tests of the MiminetTester
    log helpers with a stubbed `execute` (see §1.4 — these DO need a decision).

## 1.2 Per-file inventory (collected-test counts; browser-backed unless noted)

Sorted alphabetically; `def` = test-function count via AST; `collected` =
post-parametrization from `--collect-only`.

| file | def | collected | notes / flake class |
|---|---|---|---|
| `test_ai_generate.py` | 9 | 9 | backend unit (imports `ai_generate`); no browser |
| `test_basic.py` | 2 | 7 | 1 browser (`test_auth`, title check); 6 `requester` HTTP |
| `test_config_db.py` | 7 | 7 | backend unit (db-uri/db-exists mocks); no browser |
| `test_device_configure_names.py` | 2 | 2 | small: 2 nodes + link + names |
| `test_device_connecting.py` | 1 | 10 | 1 class-scoped `network`; 10-edge param (line 37) |
| `test_dhcp.py` | 1 | 1 | server DHCP jobs + comparator |
| `test_down_link.py` | 1 | 1 | switch link-down job + comparator |
| `test_duplication.py` | 2 | 2 | **flake history**: `assert 50 == 0` server-persistence race, fixed #482 via in-page `execute_async_script` fetch poll (line 31); edge-config `DUPLICATE_FIELD` |
| `test_fields_filter.py` | 5 | 5 | raw `find_element(...).get_attribute("value")` field-filter asserts; direct `select_by_value` (line 50) |
| `test_get_logs.py` | 4 | 4 | browser-free; pins the Selenium `GET_LOG` wire command tuple (line 33). Playwright has no such wire command → port decision needed |
| `test_ipip_gre.py` | 1 | 2 | `params=["ipip","gre"]` fixture (line 11); biggest single-fixture config (5 nodes, tunnels, routes); no `delete()` in fixture |
| `test_job_edit.py` | 3 | 3 | **flake history**: `Unable to find link` fill_link render race, post-#486 shard-3; de-flaked #488 (networks.py); still needs repeated-nightly confirmation (runbook Batch 10) |
| `test_job_limit.py` | 3 | 3 | heavy: 30-job loops; deletes a job via in-page `$.ajax` `execute_script` returning a Promise (line 168) |
| `test_nat.py` | 1 | 1 | 3-interface router NAT config + comparator |
| `test_network_menu.py` | 3 | 3 | navigation; XPATH network-button index (line 39); `current_url` asserts |
| `test_packet_filters.py` | 5 | 5 | only "capture-ish" suite: drives emulation filter checkboxes, reads JS `packets`, injects synthetic `packets`/`packetFilterState` via `execute_script`; jQuery `$('.modal.show').modal('hide')` overlay-cleanup + `ElementClickInterceptedException` fallback delete (line 28) |
| `test_ping_and_copy.py` | 2 | 2 | ping comparator + **copy-network** flow via COPY modal + URL-built network |
| `test_port_forwarding_tcp_udp.py` | 1 | 2 | `params=["tcp","udp"]`; router port-forward selects/fields + comparator |
| `test_quiz_organization.py` | 6 | 6 | backend unit (quiz dto/logo); no browser |
| `test_quiz_progress.py` | 3 | 3 | backend unit (quiz progress math); no browser |
| `test_router_cycle.py` | 1 | 1 | ring topology comparator (node/jobs only) |
| `test_sleep.py` | 1 | 1 | sleep-job levels + comparator |
| `test_stp.py` | 1 | 1 | **flake history**: stale-element modal flake, fixed #482 (scoped `wait_and_click`); re-flaked on #484 head (modal-open, runbook Batch 8/9); heaviest fixture (3 switches, `enable_stp`/`disable_stp`, 2 `refresh()`) |
| `test_tcp_udp.py` | 1 | 2 | `params=["tcp","udp"]`; 5 device types incl. hub/server; `fill_default_gw`, per-link `link_id`; the "tcp-udp capture" representative in the old R1 wording |
| `test_user_options_input.py` | 5 | 34 | 7/7/6/7/7 param cases; shell-command option whitelist/blacklist on ping/traceroute/link-down jobs; heavy `add_jobs` + JS `network.jobs[-1]` asserts |
| `test_vlan.py` | 1 | 1 | `configure_vlan` modal-table driver (networks.py:489), needs `refresh()` between switches (line 51) |

Shard residue today (26 files, `idx % 3 == shard-1`, runbook §CI facts):
shard1 8 files (`config_db`, `dhcp`, `fields_filter`, `job_edit`,
`network_menu`, `port_forwarding_tcp_udp`, `router_cycle`, `tcp_udp`), shard2 9,
shard3 9. A file add/remove reshuffles residue; the empty-slice guard + quoted
array in `full_test.yml` still protect it.

## 1.3 Utility import graph (the shared core)

Everything routes through **`front/tests/conftest.py`** and
**`front/tests/utils/`**:

```
conftest.py  ── testing_setting, MAIN_PAGE/HOME_PAGE/LOGIN_PAGE (lines 25-48)
   MiminetTester(WebDriver)  (51-309)  ← the DSL object every test receives
   fixtures: chrome_driver (session, 313), requester (session, 333),
             selenium (session, 365), mock_env_* / mock_db* (backend unit)
utils/networks.py
   imports conftest (HOME_PAGE, MiminetTester), utils.locators, Selenium
   NodeType (17-39), MiminetTestNetwork (42-266), NodeConfig (268-644)
utils/locators.py  Location/DeviceLocator/Locator model (typed read-only props)
   Location.* class-constant trees; 104 `Locator(` + 5 `DeviceLocator(` consts
utils/checkers.py  TestNetworkComparator (pure, no Selenium import)
test_*.py  → import a subset: conftest (MiminetTester/consts), utils.locators
             (Location), utils.networks (MiminetTestNetwork/NodeConfig/NodeType),
             utils.checkers (TestNetworkComparator); some add `requests.Session`
             (basic), `selenium.webdriver.common.by` (By), and 5 backend files
             import app/back modules directly.
```

Per-file shared-utility imports (non-backend files):
- MiminetTester + Location + MiminetTestNetwork + (NodeType|NodeConfig) is the
  standard 4-import pattern (e.g. `test_stp.py:1-5`, `test_vlan.py:1-5`).
- `TestNetworkComparator` additionally in the comparator files: dhcp, down_link,
  ipip_gre, nat, ping_and_copy, port_forwarding_tcp_udp, router_cycle, sleep,
  stp, tcp_udp, vlan.
- Raw `By` import (files that use Selenium `By` directly outside the DSL):
  device_connecting, duplication, fields_filter, job_edit, network_menu,
  packet_filters, ping_and_copy.
- `NodeConfig` import additionally in: vlan, tcp_udp, nat, router_cycle
  (type-annotated locals + `configure_vlan`).

## 1.4 DSL-surface consumers that are NOT plain e2e (port decisions)

- **`test_get_logs.py`** subclasses `MiminetTester` with a stubbed `execute`
  (line 23) and asserts the exact `(Command.GET_LOG, {"type": "browser"})` wire
  tuple. It is the #487/#486 regression pin for a helper only reachable on a
  WebDriver wire. A Playwright port either (a) keeps a thin `get_logs`
  shim/console-recorder and rewrites the test against Playwright `page.on
  ("console")`, or (b) drops the Selenium wire-pin (it pins Selenium-4 API
  reality, not app behavior). Low stakes either way (no e2e test calls
  `get_logs` today).
- **`test_basic.py`** `requester` fixture is pure `requests` — keep verbatim.
  The auth **cookie-gift** (conftest 365-398) is Selenium-only
  (`add_cookie`); its Playwright analog is `context.add_cookies(...)` or an
  authed `APIRequestContext` + `storage_state`.

## 1.5 Measured deltas vs prior study (refresh, don't restate blindly)

- Prior claim "~25 files / ~114 tests" → **today 26 files / 118 collected**
  (delta: `test_get_logs.py`, 4 tests, added #487). AGENTS §6's "114-test
  suite" is the pre-#487 number.
- Prior claim "no leftover `time.sleep`" → **still true**: `rg time.sleep|sleep(`
  over `front/tests/*.py utils/*.py` matches only the `test_sleep` function
  name; conftest/networks use `time.monotonic()` deadline loops
  (conftest.py:81, networks.py:333), never sleeps.
- Prior claim "DSL core ~400 lines of re-implementation" → refined estimate in
  `02-dsl-to-port.md` (~450-550 new/kept lines for the DSL+fixtures when
  preserving the test-facing API).
- Prior "grid vs local": the suite only ever runs against the **remote hub**
  (`testing_setting.selenium_hub_url`, conftest.py:30); there is no local-driver
  path today. Under Playwright this distinction disappears (see `05`).
