# 07 — Recommendation: keep Selenium, no wholesale Playwright port

Date: 2026-09-04. Decision recorded after a value re-evaluation of the
Playwright-migration option for this repo's front e2e suite. Supersedes the
"author a W6 pilot no-merge PR" idea from Batch 10 planning; the studies in this
folder remain the reference for any future targeted adoption.

## Decision
- **Keep the Selenium WebDriver e2e stack.** No wholesale Selenium→Playwright
  port of `front/tests/test_*.py` + the DSL (`conftest.py`,
  `utils/networks.py`, `utils/locators.py`).
- **Playwright is allowed only for targeted scenarios Selenium does poorly**
  (network interception, download handling, multi-tab, console capture) if such
  a need ever appears — as a new narrow test, not a migration.
- Revisit only if a driver-independent reason appears (e.g. abandoning the
  grid/browser containers entirely) — and then the Phase-0 spike in this study
  (`04`, `05` R2/R6) is the gate, not a blind port.

## Why (cons against a wholesale port, grounded in this repo)
1. **Sunk-cost asymmetry.** Batches 5–10 spent five cycles de-flaking and
   hardening this exact stack (#482/#483/#484/#486/#488 + grid-readiness
   `742d79a`). The suite's dominant failure classes were and remain
   driver-agnostic: emulation/timing (OVS 0-byte captures, config-panel render
   races), host memory / `tab crashed`, and the single session-scoped tab that
   carries cross-test JS state (`nodes`/`edges`/`jobs`). Playwright changes the
   driver, not those.
2. **Session model runs against Playwright's grain** (05 R1): the suite relies
   on ONE browser across ~83 tests; replicating that must be engineered against
   per-test-isolation best practice, and any isolation "improvement" mid-port
   silently changes the #483 file-independence semantics.
3. **Flake class swap, not removal** (05 R3): auto-wait deletes the
   stale-element/render-race class but adds strict-mode single-element
   resolution — latent duplicate-id selectors Selenium's "first element wins"
   tolerated become loud failures. Trading a known profile for an unknown one on
   the most expensive job (~30 min × 3 shards).
4. **Canvas drag/drop fidelity** (05 R2): SVG mouse-event sequencing differs
   from W3C action pointers; needs a spike, and the JS-dispatch fallback already
   exists in the Selenium DSL — no clear win.
5. **Infra swap is not a clean win** (05 R5/R6): removing the grid compose +
   hub-readiness polling is offset by ~150 MB Chromium + apt deps per shard and
   a new cache/image burden.
6. **Dual-runner drift during transition** (05 R13): the safe env-flag → hard
   per-file cutover path doubles maintenance for a window and risks silent
   cross-breakage.
7. **Gate burden multiplies** (05 R11): `front/tests` is ty-gated (#486) and
   every PR faces the review-agent gate; the new DSL must replicate the typed
   read-only-property pattern across a mass churn.
8. **No runtime win expected:** suite time is bounded by mininet emulation +
   settle waits + one shared browser, not driver round-trips.
9. **Opportunity cost:** test infra has no user-facing value; the same effort
   is better spent on the now-measured/gated coverage gaps (back/src toward the
   75% gate; front/src e2e measured 27% with big low files).

## Follow-ups (kept, not lost)
- Phase-0 spike steps and residual risks are preserved in `04`, `05`, `06`.
- If a targeted Playwright need appears, scope it as its own small PR and keep
  Selenium green; never maintain both DSLs for the same file beyond one merge
  (05 R13).
