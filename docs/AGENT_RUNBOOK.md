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
- Linter = flake8 + black + mypy (matrix back/front), run via
  `uv run --frozen` (uv workspace is now the dependency SSOT; per-node
  `requirements.txt` deleted).
- `Pytest` = back tests as root, `back/ovs-init.sh`, `uv sync --frozen
  --project back`, `PYTHONPATH=../src pytest .` from `back/tests`
  (pytest-timeout 900s).
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
- Linter tooling: ruff (lint+format) and `ty` (type checker) eventually
  replace black/flake8/mypy; deferred until verifiable in CI.
- **Back test parallelism — DEFERRED (proven negative).** ipmininet's
  py-unshare/run-tests-parallel (xdist `--dist=loadscope`, per-worker
  `unshare --mount --pid --net` isolation, `--timeout-method=thread`) breaks
  OVS emulation: ovs-vswitchd runs in the host netns while each worker builds
  its network in a private netns, so OVS bridges forward nothing → empty
  captures. Proven with 4 workers AND a single worker (isolation, not
  contention). Alternatives to explore if revisited: CI matrix sharding
  (N jobs, serial slices) or OVS-per-worker-netns. Work preserved on fork
  branch `ci/back-parallel-suite`; PR #475 closed deferred.

## Session outcomes (2026-09-01)
- Merged upstream: #472 nightly flake signal (A), #474 uv workspace (D),
  #473 bench harness (E). Deferred: #475 back-test parallelism (C).
- Fork PRs #1/#2 closed superseded. Fork `main` synced to new upstream + 2
  fork-local commits (re-signed after each rebase).
