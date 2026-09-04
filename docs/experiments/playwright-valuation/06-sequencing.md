# 06 — Sequencing / phased plan with gates

Principles from AGENTS: §1b async/parallel (author the next phase while the
previous CI runs), §3 gating-experiment-first, CI-economy (one deliberate run
per phase, no blind re-pushes), review-gate per PR (docs/review_prompt.md),
fork PR lifecycle (base `upstream/main`, fork-local commits never leak, sign
every commit, `gh pr merge --rebase --admin` after reviewer APPROVE). Full test
+ auth test stay non-gating flake signals; the **Linter (ruff+ty) is the real
gate** plus the review agent.

## Phase 0 — gating spike (no PR, repo-local, ~1 day)

Cheapest experiments that decide feasibility before any port investment.
- Local: install `playwright` + `pytest-playwright` into the repo venv
  (root `uv sync`, no lock change committed yet — a throwaway branch/worktree).
  Drive the app through the front compose with a 10-line script: session
  browser → cookie-gift JWT → open a network → `add_node` drag onto canvas →
  read `window.nodes`. Verdicts: (a) drag/drop works headless on Playwright's
  Chromium; (b) `page.evaluate` returns the same JSON; (c) cookie-gift keeps the
  session authed (R1/R2/R12).
- CI-readiness: time `playwright install chromium` on a runner once and record
  the download cost for the cache decision (R6). No Full-test run — this is
  local + one throwaway runner minute if truly needed.
- **Gate:** if drag is unsalvageable headless, STOP and report the JS-dispatch
  fallback design instead of proceeding.

## Phase 1 — pilot PR (test_stp + test_job_edit + test_tcp_udp)

Contents per `04`. Single PR on `upstream/main`:
- deps commit (front dev group `pytest-playwright`/`playwright` + `uv.lock`),
- new Playwright DSL core + fixtures **behind `RUNNER=playwright`** so the
  Selenium suite on the same PR stays green (R13 guard),
- the three ported files (import/annotation-level edits only — success
  criterion 04 §4.2 #2),
- a `playwright-test.yml` (new workflow or a temporary job on the pilot branch)
  that starts only the front compose + installs/caches Chromium + runs the 3
  files' slice with per-shard-style logging. Fork CI only.
- Gates: local green on the 3 files (no grid); `ruff check` + `ruff format
  --check` + `ty check front` 0 errors; the pilot CI job green; the untouched
  Selenium Full-test slices still green on the same branch; review-agent
  APPROVE (probes: strict-mode resolution, scope re-find, viewport parity).
- **Decision point:** pilot green + no test-body rewrites beyond the catalogued
  class → proceed to Phase 2. Any surprise rework area gets a runbook entry and
  a prompt-line, and the batch re-plans around it.

## Phase 2 — per-file-group port (batches of ~5-7 files)

API-preserving port, hard cutover per file. Proposed grouping (each ~one
reviewable PR; round-robin residue irrelevant since these run under the
Playwright workflow, not the Selenium one):

- **Group A (canonical build+compare):** sleep, down_link, dhcp, ping_and_copy,
  network_menu, basic(test_auth), device_configure_names.
- **Group B (params + breadth):** port_forwarding_tcp_udp, ipip_gre, nat,
  router_cycle, vlan (R: modal-table), device_connecting.
- **Group C (rework seams):** fields_filter, duplication (async-script), job_limit
  (promise ajax), packet_filters (wait_for adapters), user_options_input.
- **Non-port items resolved in this window:** `test_get_logs.py` decision
  (drop or re-pin), `test_basic` requester tests untouched, all 5 backend-unit
  files untouched.

Per-file-group gates: (1) local green against the app compose in disjoint
slices (never the whole suite under memory pressure — AGENTS §6); (2) full gate
set on the final tree (ruff check AND format AND ty); (3) one deliberate CI run
per PR on the fork (workflow_dispatch), red = diagnostic evidence, not a
blind re-push; (4) review agent APPROVE (carry the fix-history of every file in
the group into the prompt, runbook §4).

## Phase 3 — full-suite parity run

Whole Playwright set green in one deliberate matrix run; then **one more run
with the Selenium fixtures deleted** to prove nothing was still being
exercised by the old DSL.
- Gate: Full-test (Playwright) 3/3 green + Linter green; the delete-PR diff
  touches ONLY the removed Selenium paths (conftest selenium/chrome_driver,
  grid compose, selenium deps) — prove with `git diff upstream/main <branch>`.

## Phase 4 — CI swap + cleanup

- Rework `full_test.yml` `jobs.*` only (05 §5.2): drop grid start/wait/capture,
  add `playwright install --with-deps chromium` + cache, keep shard slicing/
  guards/artifacts. Preserve the FORK-local `on:`/`build.if:` blocks; on the
  upstream copy keep `on: [push, pull_request]` + nightly cron.
- Delete `front/tests/docker/docker-compose.yml` (grid), remove `selenium` from
  the front dev group + lock (dependency-review will re-check).
- Backfill the W5-style instrumented run to re-measure front/src e2e coverage
  under Playwright (fork-temp, budgeted as ONE run; server-side tracing recipe
  unchanged).
- Optional follow-up (separate deferred item, NOT in this plan): a
  per-test-context isolation refactor now that Playwright makes it possible.

## Phase 5 — stabilisation

Watch the first N nightly Full-test runs for a flake-profile shift (the
runbook #483 flake-watch pattern, now under Playwright). Post-merge fixes feed
the reviewer prompt (AGENTS §4). Update AGENTS §6/runbook numbers: 26 files /
118 collected (browser ≈83), 3-shard residue 8/9/9, no hub, browser cache.

## Honest estimate

- DSL+fixtures re-implementation: ~450-550 lines (`02`).
- Pilot (Phase 1): one focused PR — the de-risking investment.
- Groups A-C: 3-5 more reviewable PRs.
- Full swap + CI rework + coverage re-measure: 2-3 PRs.
- **Net**: ~6-9 review-gated PRs; the whole plan is gated at the top by the
  Phase-0 spike and Phase-1 pilot — both are cheap and deliberately bounded.
  Expected suite-time outcome is neutral-to-faster (no hub session overhead,
  auto-wait collapsing the 20s retry windows), but that is a claim to measure in
  Phase 3/5, not to promise now.
