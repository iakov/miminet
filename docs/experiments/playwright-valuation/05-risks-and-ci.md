# 05 — Risks and CI implications

## 5.1 Migration risk register

| # | Risk | Severity | Mitigation / notes |
|---|---|---|---|
| R1 | **Session-scoped single-tab semantics** (one browser, cross-test tab/JS state) | High | Suite relies on ONE page carrying network JS state (`nodes`/`edges`/`jobs` globals) across tests; Playwright best practice is per-test isolation. Must replicate a session-scoped `page`+`context`. If a later isolation refactor is wanted it must be its own PR (the #483 file-independence proof only holds because each file self-builds networks via the DSL — see `06` note). |
| R2 | **Drag/drop canvas fidelity** (`add_node`, networks.py:190; `drag_and_drop` conftest:116) | High | SVG canvas + `mouse` moves; element-under-cursor and event sequencing differ from W3C action pointers. Pilot + a mouse-heavy fast-follow (vlan/duplication) gate this. Fallback if flaky: keep a JS dispatch fallback like existing `AddEdge` pattern. |
| R3 | **Auto-wait changes flake *profile*** | Medium | Playwright removes stale-element/render-race flakes (#482/#486 classes) but introduces new timing axes (actionability strictness, strict-mode single-element resolution). Strict mode will surface latent duplicate-id selectors the Selenium "first element wins" silently tolerated. Expect an initial whitelist of strict-mode fixes. |
| R4 | **`wait_for(driver-callable)` adapter churn** | Medium | ~40+ call sites (packet_filters/job_limit/duplication/networks) each need `page.wait_for_function`/`expect.poll` wrapping. Mechanical, but is where regressions hide. |
| R5 | **Headless vs grid parity** | Medium | Grid headless Chrome (141) ≠ Playwright-bundled Chromium build. Console/canvas/WebGL/`--no-sandbox` differences possible. CI-exact local run is the gate; pin Playwright's browser to a known-good revision. |
| R6 | **Browser download + OS deps in CI** | Medium | `playwright install --with-deps chromium` pulls ~150MB + apt deps per runner ×3 shards. Must cache (`~/.cache/ms-playwright`) or bake an image; otherwise each shard's first run inflates and risks GitHub runner egress flake. Pre-fetch async on the runner, and measure once in the pilot (04 §4.2 #5). |
| R7 | **`timeout = 300` per-test (pytest.ini) vs Playwright default 30s** | Low | Playwright ops inherit pytest-timeout; set explicit `expect`/action timeouts (20s parity with the old `WebDriverWait` defaults) to avoid masking slow emulation waits (the old 60s emulation wait, networks.py:243). |
| R8 | **Memory / host constraints unchanged** | Medium | Playwright Chromium is not lighter than the grid Chrome for the session-tab model. The AGENTS §6 host-memory rule (never full 114-test local run under memory pressure; disjoint slices) still applies. Local runs actually get *easier* (no podman grid), but a memory-hungry session page is the same risk. |
| R9 | **Coverage tooling interplay (W5)** | Low-Med | front/src e2e coverage is SERVER-side tracing in the app venv (`COVERAGE_PROCESS_START`, Batch 10 W5) — browser-agnostic, so unchanged. But re-measuring the "Playwright suite vs front/src" number needs a repeat of the fork-temp instrumented run once the swap lands (tracing-overhead flake watch applies). |
| R10 | **`get_logs` Selenium wire pin** | Low | test_get_logs.py pins Selenium GET_LOG behavior; decide drop vs re-pin to a `page.on("console")` recorder (01 §1.4). No e2e consumer. |
| R11 | **ty gate on the new DSL** | Medium | front/tests is ty-gated since #486 (Batch 9). The new wrapper must follow the typed read-only-property pattern — a re-architecture cannot silently regress `ty check front`. |
| R12 | **Auth/login cookie flow** | Medium | Session cookie-gift maps to `context.add_cookies`; JWT cookie flags (`sameSite`, no `httpOnly`, `expires`) must be preserved exactly or the app redirects to login mid-suite (the Selenium fixture only gifts when `expires`/name present, conftest.py:372-395). |
| R13 | **Dual-runner drift during transition** | Medium | While both suites exist (env flag), a file edited in one place can silently break the other. Sequence a hard cutover per file group; never maintain both DSLs for the same file beyond one merge. |

## 5.2 CI workflow implications

Files today (fork checkout):
- `.github/workflows/full_test.yml` — front Full test, 3-shard matrix (FORK copy
  shown here carries fork-local `workflow_run`/`workflow_dispatch` + `build.if:`
  gate at lines 6-9/17). This is the file the swap touches.
- `auth_test.yml` runs `front/src` pytest only — **unaffected**.
- `linter.yml` (ruff + ty) gates every change — the ported code must pass it.
- `back_test.yml`, `dependency_review.yml` — unaffected except dep-review will
  vet `playwright`/`pytest-playwright` pins in the changed `uv.lock`.

`full_test.yml` changes needed for the swap (per §1b/§7 CI-economy — one
deliberate run per phase, fork `workflow_dispatch`):

1. **Replace the grid:** drop `Start selenium` + `Wait for selenium grid`
   steps (full_test.yml:45-73). The hub/node compose
   (`front/tests/docker/docker-compose.yml`) and the entire
   hub-readiness/polling machinery (`742d79a` fix, node `availability=UP`
   predicate) become dead and should be deleted with the swap (or kept inert
   behind the env flag during transition). This removes a whole flake class
   (session-creation `ConnectionResetError` cascade).
2. **Add browser provisioning:** after `uv sync --frozen`, a
   `playwright install --with-deps chromium` step with a
   `~/.cache/ms-playwright` cache keyed on the playwright pin (or switch the
   shard image to one pre-baked with the browser). 3 shards each need it;
   caching makes it cheap after the first run.
3. **Keep the shard slicing verbatim:** the round-robin quoted-array file slice
   (full_test.yml:80-101) is browser-agnostic — the Selenium and Playwright
   runs use the same `pytest front/tests/test_*.py` slices, empty-slice guard,
   `pipefail`+`tee` log, per-shard artifacts (`include-hidden-files: true`,
   `path: .tmp/*-shard-<n>.log`). **Do not touch the fork-local `on:` /
   `build.if:` blocks** when editing (`git diff upstream/main` proof, AGENTS §7).
4. **Readiness:** replace grid polling with a `curl -f localhost` app check +
   a Playwright first-session warm-up inside the test job (a tiny
   `--setup-show` or a `page.goto` smoke) — there is no hub to wait for.
5. **Container-log capture** (`if: failure()`, full_test.yml:104-122): drop the
   grid-compose logs; keep `docker ps` + front-compose logs.
6. **Artifacts:** unchanged pattern (proven; don't re-invent).

Matrix residue note: 26 files today → 8/9/9 (not the 8/9/8 of the runbook — 25
files — because #487 added `test_get_logs.py`). The slice math + empty-slice
guard already absorb this; just don't rely on the historical 8/9/8 in prose.

## 5.3 Transition topology (avoid double-maintenance)

Recommended shape is a **runner env switch** only for the pilot (both suites on
one PR to prove green-on-green), then per-phase **hard cutovers**: a PR that
moves one file group from the Selenium fixtures to the Playwright fixtures and
deletes the Selenium copy of exactly that file's code path. At the end a single
"delete grid + Selenium DSL + `selenium`/`chrome_driver` fixtures" PR. Never
leave both DSLs parsing the same file for more than one merge (R13).

## 5.4 Host/harness notes that carry over

- Local Playwright runs no longer need the grid compose or the
  `TEST_TARGET_HOST` rootlessport dance (AGENTS §6): a host Chromium reaches the
  app through the front compose port the same way CI's `curl -f localhost`
  does. The **front compose stack itself is still required** (nginx+uwsgi+db).
- `podman machine stop ipmininet` before timing-sensitive runs, and the
  `/dev/shm`/`tab crashed` class disappears (no dockerized Chrome), but host RAM
  pressure still kills a session page — keep the disjoint-slice discipline.
- pytest logging discipline (§1a) unchanged: full `-vv -s`, `tee` to
  `.tmp/<run>.log`, no `-q`.
