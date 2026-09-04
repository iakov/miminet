# Playwright-migration valuation study — miminet front Selenium e2e suite

Date: 2026-09-04. Repo: fork checkout at `~ /home/me/projects/miminet`
(origin `iakov/miminet`, upstream `mimi-net/miminet`); docs mirror lives in the
`docs/agent-guardrails` worktree (this directory).

Scope: value whether/how the Selenium WebDriver e2e layer
(`front/tests/test_*.py` + the DSL in `front/tests/conftest.py` and
`front/tests/utils/`) can be ported to Playwright, and how to sequence such a
port without burning CI.

Why it exists: a first valuation of identical scope (Batch 10, deferred item
W6 / R1) was lost because it was delivered only as a final message and never
persisted. This run is the re-run with the same conclusions re-verified against
the current tree (several counts have drifted — see `01-inventory.md`) and is
written to disk so it is durable.

How to use this study:
- `01-inventory.md` — file/test inventory + utility import graph (authoritative
  counts are measured on this checkout: `pytest --collect-only`).
- `02-dsl-to-port.md` — the DSL surface with file:line anchors and a Playwright
  line-sizing estimate.
- `03-transferability-matrix.md` — per-DSL-area and per-file transferability.
- `04-pilot-recommendation.md` — the pilot trio + rationale (re-affirms R1 with
  one amendment).
- `05-risks-and-ci.md` — migration + CI/workflow risk register.
- `06-sequencing.md` — phased plan with per-phase gates.

Task id / context: re-run of the Playwright-migration valuation (prior result
lost to a non-persisted final message). Read-only research; the only writes are
these files. Nothing was pushed, no PRs opened, the e2e suite was NOT run, no
CI was burned. The one execution artifact used is a browser-free
`pytest --collect-only` for exact test counts.

Key sources referenced throughout (short names):
- AGENTS.md (repo root and docs worktree — identical).
- `docs/AGENT_RUNBOOK.md` (docs worktree) — flake history batches 5-10 and CI
  facts; "runbook" below.
- `docs/review_prompt.md` — the review gate the port PRs must pass.
- Code under `front/tests/` and `.github/workflows/` (fork `main` checkout;
  note `full_test.yml` as checked out here is the FORK copy with fork-local
  `workflow_run`/`workflow_dispatch` + `build.if:` gate).
