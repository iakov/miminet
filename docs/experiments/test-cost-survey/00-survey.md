# Test cost & duplication survey (2026-09-08)

Data-driven survey of where CI test time actually goes and where test cases
duplicate each other's coverage/behavior. Asked: "We have big tests that touch a
lot of code, can we remove some smaller test cases?"

Question reframed by the data: the *smaller* cases are almost never the CI-time
cost, and coverage subsumption is the wrong deletion criterion. The expensive
tests are a handful of big flow/emulation tests; the maintainable-win shape is
pyramid refactoring (move input-matrix cases down to the cheap lane), not
coverage-driven deletion.

## Method

- Per-test durations parsed from GitHub Actions run logs (sub-second
  timestamps between consecutive PASSED/FAILED/ERROR markers).
- E2E ("Full test") source: fork run `34162169495` @ `23ee9f5` (the 22-file
  dedup matrix), 3 parallel shards.
- Back ("Pytest") source: fork run `34162167534` @ `23ee9f5` shard 2 (the only
  timestamped shard log retained; shards 1/3 are cheap and their wall times are
  taken from the run jobs API).
- All times are wall-test-seconds, NOT runner-minutes; shards run in parallel,
  so the CI cost of a job is `max(shard)` plus per-shard infra, not the sum.

## E2E cost: per-file (95 tests, 3 shards)

Per-file pytest wall-seconds (sum of per-test gaps across whichever shard ran
the file; shards run in parallel so column = that file's own duration):

| file | tests | sec | ms/test | note |
|---|---|---|---|---|
| test_job_limit.py | 3 | 49.0 | 16333 | 3 nets, 30 jobs each |
| test_job_edit.py | 3 | 28.9 | 9641 | 3 nets |
| test_user_options_input.py | 34 | 24.0 | 706 | class-scoped net reused |
| test_ipip_gre.py | 2 | 21.1 | 10569 | class param net each |
| test_fields_filter.py | 5 | 17.0 | 3395 | |
| test_tcp_udp.py | 2 | 15.0 | 7522 | class param net each |
| test_vlan.py | 1 | 10.9 | 10858 | |
| test_port_forwarding_tcp_udp.py | 2 | 10.7 | 5353 | |
| test_nat.py | 1 | 10.6 | 10572 | |
| test_stp.py | 1 | 9.9 | 9850 | |
| test_dhcp.py | 1 | 8.2 | 8249 | |
| test_router_cycle.py | 1 | 7.7 | 7748 | |
| test_duplication.py | 2 | 7.4 | 3690 | |
| test_sleep.py | 1 | 6.6 | 6561 | |
| test_ping_and_copy.py | 2 | 6.1 | 3025 | |
| test_packet_filters.py | 5 | 5.8 | 1166 | |
| test_down_link.py | 1 | 5.5 | 5509 | |
| test_device_configure_names.py | 1 | 3.3 | 3319 | |
| test_network_menu.py | 3 | 2.3 | 782 | |
| test_device_connecting.py | 9 | 1.6 | 172 | |
| test_basic.py | 6 | 0.1 | 12 | |
| test_quiz_organization.py | 6 | 0.0 | 2 | |

E2E total pytest-time: ~252s across shards; the critical (slowest) shard is
shard 2 at ~107s test + ~107s infra (frontend+grid boot) = ~3.9 min/job wall.

Cost shape:
- **Infra dominates**: ~107s/shard of grid+frontend boot vs ~90-107s of tests.
  Halving test time saves ~1/3 of the job; cutting tests to zero saves ~half.
- **A few big flow tests dominate test time**: test_job_limit + test_job_edit +
  test_ipip_gre ≈ 99s of the ~252s total. Each boots a fresh mininet topology
  in the browser (per-test `MiminetTestNetwork`, not class-scoped).
- **test_user_options_input is cheap per case** (0.7s): its network is
  class-scoped and reused across all 34 cases. NOT the duplication lever its
  34-case count suggests.

## Back cost

| shard | files | tests | pytest sec | job wall |
|---|---|---|---|---|
| 1 | test_jobs, test_pkt_parser (+captures?) | 69 | ~3 | 0.55 min |
| 2 | test_captures, test_miminet_back, test_tasks | 40 | ~104 | 2.25 min |
| 3 | test_duplication, test_network_ready, test_vlan | 30 | ~11 | 0.62 min |

Back cost shape:
- The ENTIRE back test time is shard 2's **21 emulation scenarios** in
  test_miminet_back.py (~5-20s each; this is the shard that flaked with the
  900s timeout on `[router]`). Shard 2 = 2.25 min job wall.
- test_miminet_back.py is 21 parametrized full-network emulations, each
  asserting exact packet-arrival output vs a golden file (`test_json/*`).
  These are feature scenarios (dhcp, vlan, rstp, vxlan, nat, ...) — NOT
  duplicates of each other.

## What the coverage data does / doesn't answer

- Per-lane `.coverage` (back-merged, front-browserfree) attributes to the
  SUITE, not to individual tests → cannot compute "test X's unique lines"
  without per-test attribution (dynamic contexts) or differential runs.
- Front e2e code coverage is NOT collected at all (container instrumentation
  is the deferred spike) → subsumption of e2e by browser-free, or vice versa,
  is currently unmeasurable.
- Therefore "delete the small tests whose lines the big tests also cover" is
  (a) uncomputable today and (b) the wrong target even if computed: the small
  tests are the cheap ones; deleting them saves seconds and loses the
  failure-localizing regression net.

## Redundancy actually found (code-level)

1. **test_user_options_input.py internal blacklist duplication** — the 7-case
   blacklist matrix is copy-pasted across 3 test functions
   (`test_ping_options_blacklist`, `test_traceroute_options_blacklist`,
   `test_link_down_option_blacklist`), with the same 6 of 7 strings and the
   7th being a near-variant. The whitelist matrices are similar-but-distinct.
   BUT the net is class-scoped so these cases cost ~0.7s each — removing the
   dupes saves ~2-4s. Maintenance win, not a time win.
2. **Browser-free vs grid double-run** (already fixed in the 22-file dedup).
3. **Front quiz unit tests vs e2e quiz tests**: test_quiz_progress (browser-free)
   and test_quiz_organization (e2e) both exercise quiz progress/org logic. The
   e2e one drives it through the real UI on a booted network (~2s net); the
   browser-free one is pure. These are complementary layers, not duplicates.

## Conclusions / options

1. **Do NOT delete small tests for coverage.** It saves ~seconds and removes
   the cheap regression/定位 layer. The gate risk is real and unmeasurable
   until per-test attribution exists.
2. **Real CI-time lever = the few big flow tests + infra, not the many small
   ones.** Options, in descending cost/benefit:
   a. Investigate test_job_limit (49s/3) — why 16s/test for a UI job-cap
      check; if it awaits emulation completion per job, add-jobs is the cost.
   b. Reduce grid+frontend boot (~107s/shard) — parallelism or reuse.
   c. test_miminet_back's 21 emulations each 5-20s — check for redundant
      topologies INSIDE a feature (e.g. multiple dhcp variants) once it stops
      being the flake source.
3. **Maintenance cleanups that are safe and nearly-free**: dedupe the 3
   copy-pasted blacklist matrices in test_user_options_input.py (parametrize
   the command + expected message).
4. If coverage-subsumption deletion is ever wanted, the prerequisite is a
   per-test attribution spike (coverage.py dynamic contexts on one lane,
   cheapest = browser-free) producing a "unique lines per test" table.

## Data sources (re-runnable)

- E2E per-file: `/tmp/opencode/fulltest_23ee9f5.log` (fork run 34162169495).
- Back shard2: `/tmp/opencode/back_pytest_23ee9f5.log` (fork run 34162167534).
- Parsing approach: gap between consecutive test-marker timestamps.
