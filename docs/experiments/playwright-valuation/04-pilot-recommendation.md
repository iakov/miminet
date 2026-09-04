# 04 — Pilot recommendation

The pilot must **bound the two unknowns that decide the whole port**:
(1) does the DSL re-implementation over Playwright reproduce the flake-prone
interactions (stale config panels, scoped modal clicks, canvas drag), and
(2) does the session-scoped single-tab model + JS-global reads survive a
Playwright context.

## 4.1 Recommendation

**`test_stp.py` + `test_job_edit.py` + `test_tcp_udp.py`**, run as a single
"pilot PR" that also carries the new Playwright DSL core + fixtures.

Rationale per file:

- **`test_stp.py` (1 collected)** — the suite's flake epicenter
  (`RstpModal_<id>`/`VlanModal_<id>` inner-id non-uniqueness, scoped
  `wait_and_click`, `run_in_modal_context`, `refresh()` between switch configs;
  see networks.py:361-424, runbook Batch 5 #482 / Batch 8 flake). If the
  scoped-locator + modal-wait semantics survive, the DSL port is sound where it
  is hardest. Its fixture also exercises 3 switches × `enable_stp`/`disable_stp`
  + a delete.

- **`test_job_edit.py` (3 collected)** — the second flake epicenter
  (`fill_link` async row-render race, post-#486 shard-3 / #488). Exercises the
  value-level waits (`wait_until_value` → `expect.to_have_value`), dynamic-id
  locators (`#config_host_job_edit_<uuid>`, line 42), clear+retype, submit and
  `network.jobs` read-back. Auto-waiting replacing the retry loops is exactly
  the claimed payoff — the pilot proves it.

- **`test_tcp_udp.py` (2 collected)** — replaces the prior study's vaguer
  "tcp-udp-capture representative" with the file that actually carries the
  tcp/udp + capture vocabulary: parametrized (`["tcp","udp"]`) class fixture
  over **all five device types** (host/switch/router/hub/server),
  `fill_default_gw`, per-`link_id` `fill_link`, server jobs (200/201) and large
  nodes/edges/jobs comparators. It is the widest per-test DSL+breadth sample at
  the cheapest CI cost (2 tests) and is the closest the suite has to a
  "capture-side" test short of `test_packet_filters`'s synthetic-packet JS
  rig (which is a heavier, separately-sliceable batch item).

Why NOT the prior wording "ping-copy": `test_ping_and_copy.py` is genuinely 1:1
by static analysis (`03`) — it adds almost no discriminating signal (copy modal
+ comparators) and is better kept as an early batch item that validates the
DSL once the pilot has de-risked it. `test_tcp_udp.py` covers strictly more of
the NodeConfig surface (server + router + hub panels, default-gw, multi-link)
per test count. If drag/canvas fidelity is the fear, note it is NOT covered by
any of the three — `add_node(NodeType.X)` is in every fixture, so drag IS
exercised; but a deliberately-mouse-heavy file (`test_vlan.py`'s table, or a
`configure_vlan` flow) should be a fast-follow batch item if the pilot shows
drag regressions.

## 4.2 What the pilot must gate on (success criteria)

1. The three files pass on a **local Playwright run** against the CI-exact
   front compose stack (no grid) — disjoint from the Selenium slices.
2. No test-body rewrite beyond imports + the `wait_for`/`input_value`/`fill`
   adaptations catalogued in `03`; any test-body change beyond that class is a
   red flag on the API-preservation strategy and must be reported, not silently
   absorbed.
3. The scoped-modal and value-wait semantics hold **without** the stale-element
   retry loops (i.e. Playwright auto-wait is doing the work) — this is the
   flake-class claim being tested.
4. `ruff check` + `ruff format --check` + `ty check front` green on the pilot
   tree (the ty gate re-enable of Batch 9 means the new DSL must be typed the
   same way: typed read-only properties / no `Unknown | None` leaks).
5. One deliberate CI Full-test run on the pilot branch (fork `workflow_dispatch`,
   existing infra untouched) proves the branch did not disturb the Selenium
   slices, plus a browser-download step time/failure is captured (see `05`).
6. Reviewer gate (docs/review_prompt.md) with probes aimed at: scope re-find
   semantics, locator-strictness deltas (Playwright resolves to ONE element,
   Selenium returned the first), and `viewport`/window-size parity with the
   grid's 1920×1080.

## 4.3 Pilot deliverable shape

A single PR (base `upstream/main`) containing:
- deps: `pytest-playwright` + `playwright` into `front` dev group (front/pyproject.toml:33-45) + lock;
- new `front/tests/conftest.py` Playwright-backed fixtures alongside (or
  replacing) the Selenium ones, behind an env/flag switch (`RUNNER=playwright`)
  so the Selenium suite stays green on the same PR;
- the ported `MiminetTester`-equivalent wrapper + `utils/networks.py`
  (API-preserving);
- the three ported test files;
- CI workflow draft for the Playwright run (separate step/job) — staged, not
  yet wired into `full_test.yml`.

Parallel-follow-up in the same batch (independent): author the DSL's remaining
file groups (see `06`) once the pilot is green — §1b async/parallel applies.
