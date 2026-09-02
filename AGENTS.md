# AGENTS.md — Rules and Guardrails for AI agents working in this repo

These are standing instructions distilled from prior autonomous work. They apply
to every agent session. Where they conflict with a user instruction in the
current conversation, the user instruction wins for that session — otherwise
follow these.

Detailed fork-local knowledge, findings and per-batch outcomes:
`docs/AGENT_RUNBOOK.md` (branch `docs/agent-guardrails`). This AGENTS.md is the
rule layer; AGENT_RUNBOOK.md is the knowledge layer. AGENTS.md rule edits are
made in the docs worktree (tracked copy on `docs/agent-guardrails`) and then
mirrored to this repo-root file — never edit only one of the two copies.

## 0. Operating boundaries (hard constraints)
- Work only inside the project directory. No reads/writes in `/tmp`, `~/.cache`,
  `/etc`, or other outside paths. If a tool or command would touch them, redo it.
  For scratch files use the repo-local `.tmp/` directory instead of system
  `/tmp`. This applies to shell, podman and git alike — e.g. never
  `mv <file> /tmp/...`; use `.tmp/`.
- Worktrees live under `.worktrees/<branch>` and are excluded from git via
  `.git/info/exclude` (repo-local, never committed).
- Treat harness plan mode as read-only: no edits, no mutating commands. Deliver
  a plan and wait for release, even if the user says "go".
- Never call blocking/question tools during a full-auto run. If a question is
  genuinely unavoidable, defer it and include it in the final report.
- **Pre-download artifacts async and in advance.** Before starting a pipeline,
  think ahead and fetch (in the background) every artifact later steps will
  need (e.g. pull the container image for the final step while earlier steps
  run). If you cannot download async, ask the user to run the exact command
  before proceeding.

## 1. Full-auto execution rules
- Update `todowrite` continuously (add/complete items as you go; one
  `in_progress` at a time).
- Ask no questions until the final report. Report every deferred question at the
  end, with: alternatives considered, why no experiment could settle it, and
  what would unblock it.
- Match effort to confidence and verifiability (see §3).

## 1a. Test execution & log discipline (user-mandated)
These rules override any default pytest/logging habits. They exist because
every silent re-run is a large, repeated cost; the first run must produce the
evidence needed to diagnose without guessing.
- **Never run tests with `-q`.** No quiet/terse output. Use full/verbose output
  (`-v`, `-vv`, `-s` where useful) so the log captures test names, ordering,
  and per-test status.
- **Never tail command output directly; always `tee` the full stream to a log
  first**, then inspect/tail the log file. Store logs under `.tmp/<name>.log`
  (repo-local). Pattern:
  `pytest -vv -s ... 2>&1 | tee .tmp/<run>.log; tail -N .tmp/<run>.log`.
- **Always keep the log for analysis.** An unpredicted failure is expected;
  the saved log is what makes the next step diagnosis instead of a blind re-run.
  Delete logs only when the run's outcome is fully understood and recorded.
- **Log volume scales with task cost.** Longer suites (the front Selenium suite
  is ~6+ min; full CI ~30+ min) get more log detail, because a re-run costs
  minutes-to-hours. Collect browser/grid/server logs (e.g. `docker logs`
  `selenium-hub`, `chrome`, `miminet`, `nginx`) too when a failure looks
  infra-related.
- **Distinguish run *failures* from run *errors* in the log** before acting:
  `ERROR` at fixture setup ≠ `FAILED` assertion; session-scoped fixture death
  (e.g. `tab crashed` → cascade of `invalid session id`) is one incident, not N.

## 2. Deferral policy (user-mandated)
- **Defer, don't guess.** If you are biased or unsure, and experiments cannot
  prove that one of the competing alternatives is *definitely* best, defer the
  decision. Do not merge, do not create a PR for it, and record it as a
  deferred question.
- **Security risk → no PR.** If a change carries an unresolvable security risk
  (or lands in the biased/unsure/deferred bucket), skip creating/merging the
  PR and report it as deferred.
- Deferral is not failure: preserve the work (WIP commit / worktree / notes) so
  that unblocking is cheap, and state the exact unblock condition.

## 3. Decision-making discipline (how to reason)
- **Gating experiment first.** Before investing in large unverifiable work,
  run the cheapest experiment that decides feasibility. Example: before
  migrating to uv/SSOT, try `uv lock --offline`; a definitive negative meant the
  whole PR had to wait, so we did not build a broken foundation on top of it.
- **Distinguish hard blocks from transient noise.** When a service is
  unreachable, verify with multiple endpoints, retries, DNS and port checks
  before declaring it blocked. Only then defer the network-bound steps.
- **Static verification is the minimum bar before any commit.** Verify the
  target branch actually contains every API you call (`rg`), compile/syntax
  check (`py_compile`, `bash -n`), validate JSON/YAML, and confirm file modes.
- **Ship only the coherent unit.** When extracting work from a WIP branch,
  include only the intended feature; exclude unrelated downgrades, refactors,
  deleted tests, and experiments.
- **Proportional risk.** Tiny CI-only changes can be authored fast; intricate
  runners / toolchain migrations that cannot be tested locally get deferred
  rather than half-written.

## 4. Repo execution protocol (PR lifecycle)
- Base PR work on `upstream/main`, not fork `main`: the fork carries
  fork-local commits (`workflow_dispatch`, `update_uv_lock.yml`, `.gitignore`)
  that must NOT leak into upstream PRs. Rebase branches onto `upstream/main`
  before pushing.
- Per PR: branch → push to `origin` (fork) → open cross-repo PR
  (base `mimi-net/miminet:main`, head `iakov:<branch>`) → CI green →
  **review-agent gate** (senior Python + networking reviewer; must-fix resolved
  or the PR is deferred; respect reasonable trade-offs) → rewrite history into a
  clean signed commit chain → re-green → rebase-merge upstream.
- **Review-agent prompting:** verified value (2 real latent bugs across 2 small
  PRs: an empty-slice silent-full-suite case, an artifact-name collision; plus
  a lint-coverage gap). Prompt the reviewer to hunt **edge cases and coverage
  gaps the author did not check** (empty inputs, name/id collisions, tool-behavior
  deltas, AST-identity of mass reformats) rather than re-verifying happy paths
  the author already tested.
- Sign every commit with the SSH signing key
  (`-c commit.gpgsign=true -c gpg.format=ssh
   -c user.signingkey=/home/me/.ssh/id_signing_github.pub`),
  using `--no-verify` to bypass the pre-commit hook (no config file present).
- CI chain: on the FORK, `Linter` runs on push/PR; `Pytest`, `Full test`,
  `auth test` trigger off `workflow_run: Linter completed`. Upstream runs every
  workflow on `push`/`pull_request` (no Linter chain). Full test + auth test
  are the flake signal; do not gate merges on them.
- `Full test` is sharded across 3 matrix runners (#483): each runner boots its
  own frontend+grid compose and runs a round-robin file slice of
  `front/tests/test_*.py` (8/9/8 files) with an empty-slice guard, `pipefail` +
  `tee` to `.tmp/full-test-shard-<n>.log`, and per-shard artifacts. The FORK's
  `full_test.yml` additionally carries fork-local `workflow_run`/
  `workflow_dispatch` triggers and a `build.if:` gate (runs only when Linter
  succeeded, never on fork push/PR) — preserve them when editing that file or
  fork CI silently stops running it.
- After each upstream merge, rebase fork `main` (re-apply the 2 fork-local
  commits) and force-push it. Fork-local commits' signatures are dropped by
  `git rebase` — re-sign with `git ... rebase --exec 'git commit --amend
  --no-edit --no-verify' <upstream-main>` (or `commit --amend -S`).
- Merge order matters when PRs touch the same files: A → D → C → E.
- Review-gate approval cannot be given by the PR author on their own PR (GitHub
  rejects self-approval). Record the review-agent verdict as a PR comment, then
  `gh pr merge --rebase --admin` (author has ADMIN on upstream).
- **Linter/formatter migrations:** separate the tooling commit (workflow +
  dep pins + lock) from the mass autofix commit (`ruff check --fix` /
  `ruff format` sweep). Never squash them together — keeping them separate lets
  reflog/blame/`rev-list` isolate the sweep (revert it, or find which commit
  touched a line). Commit tooling first, autofix second, so no intermediate
  commit is judged by the OLD checkers.

## 5. Security rules
- Never commit or log secrets/tokens. Never commit `back/Vagrantfile.txt`,
  `opencode.json`, `static/`.
- Never leave the repo in a state that cannot install/build (e.g., deleting the
  only dependency manifest before its replacement lock exists).
- Do not create PRs for work that is deferred or carries unresolved risk.

## 6. Repo-specific operational knowledge
- **uv workspace facts (verified empirically):** the venv is always at the
  workspace ROOT (`.venv`), even with `uv sync --project back` or from a member
  dir. Root `uv sync --frozen` installs all members + all dev groups. `uv sync
  --project back` installs back runtime + back dev group only and does not need
  `front/pyproject.toml`. Single-lock workspace ⇒ all members must share
  compatible pins (conflicts fail `uv lock`).
- **prod images:** root-context build (`COPY pyproject.toml uv.lock` from
  repo root), `uv sync --frozen --no-dev --project <node>`, `ENV PATH=/app/.venv/bin:$PATH`,
  `front/src/uwsgi.ini` needs `virtualenv = /app/.venv`, and the front image
  must include `pip` (front imports `pip._vendor.cachecontrol` in
  `miminet_auth.py`). Deploy uses `UV_PROJECT_ENVIRONMENT=venv` so the venv is
  at repo root (`miminet/venv`).
- **dependency-review gating:** blocks merges on CVEs in any changed manifest
  (including `uv.lock`, and dev-group tools like black/pytest). Known resolved
  bumps: Pillow 12.3.0 (11.x has unfixable high CVEs), Flask 3.1.3,
  requests 2.33.0, black 26.x (GHSA-3936-cmfr-pm3m), pytest 9.0.3
  (GHSA-6w46-j5rx-g56g). Black 26 reformats 2 pre-existing test files
  (`back/tests/test_network_ready.py`, `front/tests/test_job_limit.py`).
- **pytest on this repo:** tests resolve `network_examples_json`/`test_json`
  relative to CWD, so run from `back/tests` with `PYTHONPATH=$PYTHONPATH:../src`
  (rootdir-relative `pythonpath = src` points at `back/tests/src`, not `back/src`).
- **VERIFIED NEGATIVE — parallel back suite:** `unshare --mount --pid --net`
  per pytest-xdist worker (ipmininet's approach) breaks OVS emulation: ovs-vswitchd
  runs in the host netns but each worker's network is created in a private netns,
  so OVS bridges forward nothing → empty captures. Proven with 4 workers AND with
  a single worker (so it is the namespace isolation, not contention). Alternative
  to explore if revisited: CI matrix sharding (N jobs, serial slices), or OVS per
  worker netns. Work preserved on fork branch `ci/back-parallel-suite`.
- **Root .gitignore starts with `.*`** ⇒ `.github`, `.venv`, `.worktrees`,
  `.tmp`, `.bench` are ignored; use `git add -f` for `.github/...` and
  `.dockerignore`. Worktree `.git` is a gitfile — no per-worktree
  `.git/info/exclude`.
- **Front Selenium e2e (local):** use the CI-exact grid compose
  `front/tests/docker/docker-compose.yml` (shm_size 2gb, GRID_TIMEOUT 60). Never
  hand-run a chrome node with the default 64MB /dev/shm — tabs crash
  (`tab crashed`) under load. Under rootless podman the host cannot reach
  container IPs: run with `TEST_TARGET_HOST=<host LAN IP> TEST_TARGET_PORT=8080`
  (rootlessport listens `*:8080`; chrome reaches the app via gateway NAT;
  container→container `172.18.0.2:80` also works).
- **Front suite is host-memory-bound:** the session-scoped `selenium` fixture is
  ONE browser for the whole run. Do not run the full 114-test suite locally in
  one go under host memory pressure (desktop chrome, opencode, the
  auto-restarting ipmininet podman machine kill a tab mid-run → a `tab crashed`
  cascade = ONE incident, not N). Verify with disjoint file slices/halves; e2e
  file independence is proven (halves 53+61; matrix 62+22+30). `podman machine
  stop ipmininet` before timing-sensitive runs (it auto-restarts via Podman
  Desktop and starves the host); `podman machine stop` REWRITES
  `~/.config/containers/storage.conf` to root paths — restore
  `[storage] driver="overlay"` without graphroot/runroot.

## 7. Infra/CI change guardrails (cross-batch distilled)
Applies to any workflow or CI-harness edit:
- **Empty-slice guard is mandatory** in any sliced job
  (`[ -n "$slice" ] || exit 1`) — without it a file-count change silently
  re-runs the WHOLE suite on one shard (#477 review catch).
- **Per-shard artifact names** (`full-test-logs-shard-<n>`) — a shared name
  lets a failed shard's log be overwritten by a later shard (#477 review catch).
- **Preserve pytest's exit code:** `set -o pipefail` before `pytest ... | tee
  log` (a bare `sudo bash -c` has no `set -e`), and funnel `find`/`sort`/`awk`
  failures into the guard so no infra error is masked by a green pytest.
- **Silent-coverage holes:** an unquoted `$slice` word-splits/globs (a filename
  with glob metachars that fails to self-match is silently dropped from that
  shard); `find -maxdepth 1` never collects a future `test_*.py` added under a
  subdir (the old `pytest front/tests` recursed). Prefer `mapfile`/arrays and
  document the `-maxdepth` constraint (#483 review nits, shared with
  `back_test.yml`).
- **Upstream PRs touch only the intended `jobs.*` section** of a workflow —
  never fork-local `on:`/`concurrency`/`build.if` blocks. Prove with
  `git diff upstream/main <branch> -- <file>` before pushing.
- **Editing fork workflows:** preserve fork-local `workflow_run`/
  `workflow_dispatch` triggers + `build.if:` gates or fork CI silently stops
  running that job.
- **Verify a matrix actually expanded** (`gh run view <id> --json jobs`) and
  download + inspect artifacts (byte size misleads); do not trust a lone green
  run conclusion for a matrix job.
- Workflow-only changes need no heavy local e2e re-runs: the cheap local gates
  are slice-math reproduction + YAML parse; the CI matrix run IS the gate.
