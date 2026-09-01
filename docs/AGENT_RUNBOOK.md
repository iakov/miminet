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

## PR lifecycle (per PR)
branch (off `upstream/main`) → push to `origin` → cross-repo PR
(base `mimi-net/miminet:main`, head `iakov:<branch>`) → CI green →
review-agent gate (senior Python + networking reviewer, respect reasonable
trade-offs) → signed history → re-green → rebase-merge upstream.
After each upstream merge: rebase fork `main` (re-apply the 2 fork-local
commits) and force-push. Merge order when PRs touch shared files: A → D → C → E.

## CI facts
- Linter = flake8 + black~=24.0 + mypy (matrix back/front).
- `Pytest` = back tests as root, `back/ovs-init.sh`, venv +
  `pip install -r back/requirements.txt`, `PYTHONPATH=../src pytest .`
  from `back/tests` (pytest-timeout 900s). xdist workers need
  `--timeout-method=thread`.
- `Full test` + `auth test` are the flake signal; do not gate merges on them.
- ipmininet is a git dependency pinned `@v1.2.7` (strict capture mode);
  `uv lock --offline` cannot resolve it (git fetch blocked offline).

## Standing decisions
- uv workspace = single source of truth for deps (root workspace
  `pyproject.toml`, member pyprojects, one root `uv.lock`); delete per-node
  `requirements.txt`; CI/prod install via `uv sync --frozen`.
  Prod `ansible`/`vagrant` keep `back/venv` paths via
  `UV_PROJECT_ENVIRONMENT=venv`. Docker images: root build context +
  `uv sync --no-dev --frozen --project <node>` + PATH to `.venv`.
- Linter tooling: ruff (lint+format) and `ty` (type checker) eventually
  replace black/flake8/mypy; deferred until verifiable in CI.
- Back test parallelism: port ipmininet's py-unshare/run-tests-parallel
  (xdist `--dist=loadscope`, per-worker `unshare` isolation,
  `--timeout-method=thread`).
