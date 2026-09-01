# Agent Runbook — miminet

Knowledge that saves time when an agent (or human) resumes work on this repo
from any host. Everything here is fork-local reference; do not upstream it.

## Repo topology (critical)
- `upstream` = `mimi-net/miminet` (the real project; PRs target its `main`).
- `origin` = `iakov/miminet` (fork). Fork `main` = `upstream/main` +
  2 fork-local commits that must NEVER leak into upstream PRs:
  - `workflow_dispatch` added to `full_test/back_test/auth_test` workflows
    (fork runs its CI off a `workflow_run: Linter` chain).
  - `update_uv_lock.yml` + `.gitignore` un-ignore tweaks.
- Upstream CI is different from fork CI: upstream runs every workflow on
  `on: [push, pull_request]` (no Linter `workflow_run` chain); `auth_test`
  uses `pull_request_target` with `test_env` secrets.
- Rule: author upstream PRs against `upstream/main`'s actual files. Rebase
  branches onto `upstream/main` before pushing (`git rebase --onto upstream/main
  <fork-local-commit>`), because a plain `git rebase upstream/main` is a no-op
  ("up to date") when `upstream/main` is already an ancestor of the branch.

## Git quirks
- Root `.gitignore` starts with `.*` → `.github`, `.bench`, `.worktrees`,
  `.tmp` are ignored. `git add .github/...` prints an ignore warning and fails
  the `&&` chain even for tracked files; use `git add -f` or stage explicitly.
- Worktree `.git` is a gitfile; there is no per-worktree `.git/info/exclude`
  (it resolves to the main repo's).
- Pre-commit hook is installed but has no config → commit with
  `--no-verify` + signing flags
  (`-c commit.gpgsign=true -c gpg.format=ssh
   -c user.signingkey=/home/me/.ssh/id_signing_github.pub`).
- **Rebase drops commit signatures.** After any `git rebase`, re-sign the
  rebased commits: `git ... rebase --exec 'git commit --amend --no-edit
  --no-verify' <new-base>` (or `commit --amend -S`), then force-push.
- **Never use system `/tmp`** — use repo-local `.tmp/` (also for logs,
  downloads, scratch files; podman/shell/git included).
- GitHub rejects self-approval on your own PRs: record the review-agent verdict
  as a PR comment, then `gh pr merge --rebase --admin` (author has ADMIN on
  upstream).

## PR lifecycle (per PR)
branch (off `upstream/main`) → push to `origin` → cross-repo PR
(base `mimi-net/miminet:main`, head `iakov:<branch>`) → CI green →
review-agent gate (senior Python + networking reviewer, respect reasonable
trade-offs) → signed history → re-green → rebase-merge upstream.
After each upstream merge: rebase fork `main` (re-apply the 2 fork-local
commits), force-push, delete merged branch + worktree. Merge order when PRs
touch shared files: A → D → C → E.

## CI facts
- Linter = **ruff check + ruff format --check + mypy** (matrix back/front),
  run via `uv run --frozen` (uv workspace is the dependency SSOT; per-node
  `requirements.txt` deleted).
- `Pytest` = back tests as root, `back/ovs-init.sh`, `uv sync --frozen
  --project back`, `PYTHONPATH=../src pytest .` from `back/tests`
  (pytest-timeout 900s). **Sharded across 3 matrix runners** (#477): each job
  runs a serial slice of `test_*.py` (round-robin `NR % 3 == shard-1`), with an
  empty-slice guard and per-shard `test-logs-shard-<n>` artifacts.
- `Full test` + `auth test` are the flake signal; do not gate merges on them.
- Full test now also runs nightly (`schedule: cron '0 2 * * *'`, merged from
  PR A).
- dependency-review gates merges on CVEs in any changed manifest (incl.
  `uv.lock` and dev-group tools). Bumps that unblocked it: Pillow 12.3.0
  (11.x unfixable), Flask 3.1.3, requests 2.33.0, black 26.x
  (GHSA-3936-cmfr-pm3m), pytest 9.0.3 (GHSA-6w46-j5rx-g56g). Black 26
  reformats `back/tests/test_network_ready.py` + `front/tests/test_job_limit.py`.
- ipmininet is a git dependency pinned `@v1.2.7` (strict capture mode);
  `uv lock --offline` cannot resolve it (git fetch blocked offline).

## Standing decisions
- uv workspace = single source of truth for deps (root workspace
  `pyproject.toml`, member pyprojects, one root `uv.lock`); per-node
  `requirements.txt` deleted; CI/prod install via `uv sync --frozen`.
  Prod `ansible`/`vagrant` use `UV_PROJECT_ENVIRONMENT=venv` so the venv is
  at repo root (`miminet/venv`); sudoers/celery paths point there. Docker
  images: root build context + `uv sync --no-dev --frozen --project <node>` +
  `ENV PATH=/app/.venv/bin:$PATH`; front image ships `pip` (for
  `pip._vendor.cachecontrol`); `front/src/uwsgi.ini` sets
  `virtualenv = /app/.venv`.
- **uv venv placement:** the venv is always at the workspace ROOT (`.venv`),
  even with `uv sync --project back` or from a member dir. Root `uv sync
  --frozen` installs all members + all dev groups; `--project back` installs
  back runtime + back dev group only.
- Linter tooling: **ruff (lint+format) merged (#476)** replacing black/flake8;
  mypy kept (type gate). `ty` swap deferred — `ty check .` = 190 diagnostics
  vs mypy 0 (mypy skips untyped function bodies); the `[tool.ty]` config is now
  schema-valid so the swap can be evaluated when someone wants the stricter
  checks.
- **Back test parallelism — SHARDING MERGED (#477), unshare proven negative.**
  ipmininet's py-unshare/run-tests-parallel (xdist `--dist=loadscope`,
  per-worker `unshare --mount --pid --net` isolation, `--timeout-method=thread`)
  breaks OVS emulation: ovs-vswitchd runs in the host netns while each worker
  builds its network in a private netns, so OVS bridges forward nothing → empty
  captures. Proven with 4 workers AND a single worker (isolation, not
  contention). **Matrix sharding instead: N independent runners, serial slices
  by file, no unshare → emulation tests pass** (shard1 21/21 incl. the flakey
  `port_forwarding_tcp` on re-run; shard2 18/18; shard3 3/3). Work preserved on
  fork branch `ci/back-parallel-suite`; PR #475 closed deferred.

## Session outcomes (2026-09-01)
- Merged upstream: #472 nightly flake signal (A), #474 uv workspace (D),
  #473 bench harness (E). Deferred: #475 back-test parallelism (C).
- Fork PRs #1/#2 closed superseded. Fork `main` synced to new upstream + 2
  fork-local commits (re-signed after each rebase).
- Docs are **fork-only by decision**: AGENTS.md + runbook stay on
  `docs/agent-guardrails`, never merged upstream.

## Batch 2 outcomes (2026-09-01)
1. **Linter switch → ruff (check + format), mypy kept (#476, merged).**
   Two separated commits as planned: A = tooling (linter.yml flake8→`ruff
   check`, black→`ruff format --check`; dropped `black`/`flake8` pins + lock;
   fixed `[tool.ty]` to a schema-valid block), B = `ruff format` sweep (21
   files). **`ty` swap DEFERRED (proven):** `ty check .` = 190 diagnostics
   across ~50 files vs `mypy --ignore-missing-imports` = 0 — mypy's default
   skips untyped function bodies, ty checks them; a full swap is type-churn,
   not mechanical. CI tripped once on flake8-only flags (`--count`,
   `--statistics`) — removed. Review noted one real coverage gap: flake8 caught
   `W605` (invalid escape), ruff's `select=["E4","E7","E9","F"]` does not
   (non-blocking, repo clean today).
2. **Back-test parallelism revival — POSITIVE via matrix sharding (#477,
   merged).** 3-runner matrix, serial slices by file (round-robin
   `NR % 3 == shard-1`), no unshare/xdist. Shard 1 = 21 emulation tests passed
   (20/21 then 21/21 on re-run — `port_forwarding_tcp` flaked once with
   RST+ACK instead of a full handshake, a timing flake, passed on re-run),
   shard 2 = 18/18, shard 3 = 3/3. **Emulation works on separate runners →
   matrix sharding is OVS-safe** (the unshare approach failed outright). This
   un-deferrals the parallelism question; speedup is modest (4 test files) but
   the mechanism is proven. Hardening added from review: empty-slice guard
   (`[ -n "$slice" ] || exit 1` — prevents silent full-suite re-run if the file
   count changes) and per-shard artifact names (`test-logs-shard-<n>`).
3. **dependabot × uv.lock:** open PR #461 validated — it bumps
   `front/requirements.txt`, which no longer exists on `main` (removed in the
   uv migration). **Stale, closed as obsolete.** The live question (can the
   pip@`/` dependabot produce valid workspace-lock PRs?) stays **open** until
   the next monthly cycle.
4. **Fork branch cleanup — done.** Deleted 6 origin + 11 local stale branches
   (all abandoned experiments, zero PRs, confirmed ahead-commits were
   superseded work: poetry draft, pre-uv CI experiments). Kept `main`,
   `docs/agent-guardrails`, `ci/back-parallel-suite`, `wip/bench-emulation`
   (its worktree is outside the project dir — untouchable).

## Review-agent gate — evaluation (2026-09-01)
Ran the senior-reviewer subagent on #476 and #477. Verdicts: APPROVE + APPROVE
(both with non-blocking nits; no must-fix on either).

What it actually caught (ranked by value):
- **#477 empty-slice guard** — a REAL latent bug I shipped: an empty slice
  would make `pytest $slice` silently run the entire suite (full-duplicate
  coverage). I tested the round-robin math but never thought about the
  empty-slice case. This alone justifies the gate.
- **#477 artifact-name collision** — per-shard logs overwrite each other
  (last-wins) so a failed shard's log could be lost. Debuggability fix.
- **#476 W605 coverage gap** — flake8 caught invalid escapes, the ruff select
  set doesn't. Genuine (minor) lint-coverage regression I missed.
- **#476 AST-identity of the format sweep** — independent proof that the
  21-file reformat changed nothing semantically. High-confidence verification
  of the riskiest part of a formatter switch.
- **#476 lock coherence** — confirmed only black/flake8 + reachable transitives
  dropped, and that `pathspec`/`click`/`mypy-extensions` must stay (other
  tools' deps).

What it did NOT add: it re-verified several things I had already tested
(ruff/mypy gate, slice partitioning, ty TOML schema). Overlap is partly the
point (independent re-check) but the prompt could push harder toward
"find what the author missed" to cut redundancy.

Cost: one subagent run per PR (minutes, no blocking questions). Net: 2 real
bugs + 2 verification wins across 2 small PRs → **keep the gate**, tune prompts
toward adversarial/edge-case hunting (empty inputs, name collisions, coverage
gaps) rather than re-verifying happy paths.

## Standing guardrail update
- Linter/formatter migrations must keep the tooling commit separate from the
  mass autofix commit (reflog/blame/rev-list isolation). This pattern held:
  the `--count/--statistics` CI failure was fixed by `--fixup`+autosquash
  into commit A, keeping A/B clean.
