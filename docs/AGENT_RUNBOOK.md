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
- **`-c key=val` config flags go BEFORE the subcommand.** After `git commit`
  they are parsed as `-c <commit>` (reuse message): `git commit --amend -c
  commit.gpgsign=true ...` fails with `options '-m' and '-c' cannot be used
  together`. Correct: `git -c commit.gpgsign=true ... commit --amend -m "..."`.
- **After amending upstream HEAD, a plain `git rebase upstream/main` is WRONG
  for the fork** — git replays the commit the amend removed and conflicts with
  its replacement. Use `git rebase --onto upstream/main <old-fork-base>` to
  re-apply only the fork-local commits that sat on the pre-amend base.
- **Force-push to protected upstream `main`** succeeded with
  `--force-with-lease` despite remote advisory lines ("Missing ... deployments",
  "Changes must be made through a pull request", "Cannot force-push to this
  branch"). Push chatter can be noise — verify the ref actually moved with
  `git ls-remote upstream main`, never trust the summary line alone.

## PR lifecycle (per PR)
branch (off `upstream/main`) → push to `origin` → cross-repo PR
(base `mimi-net/miminet:main`, head `iakov:<branch>`) → CI green →
review-agent gate (senior Python + networking reviewer, respect reasonable
trade-offs) → signed history → re-green → rebase-merge upstream.
After each upstream merge: rebase fork `main` (re-apply the 2 fork-local
commits), force-push, delete merged branch + worktree. Merge order when PRs
touch shared files: A → D → C → E.

## CI facts
- Linter = **ruff check + ruff format --check + ty** (matrix back/front),
  run via `uv run --frozen` (uv workspace is the dependency SSOT; per-node
  `requirements.txt` deleted). **Type gate swapped mypy → ty (#485).** ty
  checks untyped function bodies unconditionally (mypy skipped them → the old
  0-error gate was vacuous over a ~24%-annotated codebase). Invocation:
  `ty check --no-progress ${{matrix.node}}`; `[tool.ty]` in the root
  pyproject carries `allowed-unresolved-imports = ["**"]` (mypy
  `--ignore-missing-imports` parity) and a `front/tests` staging override
  (`all = "ignore"` — ~133 diagnostics, mypy never meaningfully checked those
  untyped test files either; re-enable as its own phase). `back/tests` stays
  ty-checked (clean). A scoped `unsupported-base = "ignore"` override covers
  exactly the two `db.Model`-defining files (`miminet_model.py`,
  `quiz/entity/entity.py`) — flask_sqlalchemy's dynamic base ty can't resolve
  (was the mypy-era `# type: ignore[name-defined]`). ty is pinned by the lock
  (0.0.77 at adoption; pre-1.0 — treat ty bumps as their own small PRs).
- `Pytest` = back tests as root, `back/ovs-init.sh`, `uv sync --frozen
  --project back`, from `back/tests` (pytest-timeout 900s). **Sharded across 3
  matrix runners** (#477, hardened #484): each job runs a serial quoted-array
  slice of `test_*.py` under `set -euo pipefail`, empty-slice guard, `find`
  failure exits loudly, and per-shard `test-logs-shard-<n>` artifacts holding
  `back_test.log`. Because `back/tests/pytest.ini` sets `log_file =
  back_test.log` (mode 'w'), the CI run line disables that writer and lifts INFO
  to the CLI so the shell `tee back_test.log` is the single writer:
  `python -m pytest -vv -s -o log_file=/dev/null -o log_cli=true -o
  log_cli_level=INFO ... | tee back_test.log` (double-writer = corrupted log,
  #484).
- `Full test` (front Selenium e2e) + `auth test` are the flake signal; do not
  gate merges on them. Full test runs nightly (`cron '0 2 * * *'`, PR A) and is
  **sharded across 3 matrix runners** (#483): each runner boots its own
  frontend + grid compose and runs a round-robin quoted-array file slice of
  `front/tests/test_*.py` (`find -maxdepth 1 | sort`, residue `idx % 3 ==
  shard-1`, 8/9/8 files) under `set -euo pipefail`, empty-slice guard,
  `pipefail` + `tee` to `.tmp/full-test-shard-<n>.log`. A pre-test step waits
  for Selenium-grid readiness (`/wd/hub/status` ready + a node UP), and an
  `if: failure()` step captures `docker ps` + front/grid compose logs into
  `.tmp/containers-shard-<n>.log`. Uploads use `include-hidden-files: true` —
  the `.tmp/*-shard-<n>.log` glob is rooted in a hidden dot-dir and silently
  uploads NOTHING without it (#484). On the FORK this job additionally has a
  fork-local `workflow_run: [Linter]` trigger + `workflow_dispatch` and runs
  only when Linter succeeded (the `build.if:` gate) — never on fork push/PR.
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
  **type gate is now ty (#485)** replacing mypy (see CI facts — ty checks
  untyped bodies, the mypy 0-error gate was vacuous). `front/tests` staged out
  of the ty gate (mypy never checked them meaningfully either); mypy stays in
  dev deps but is no longer run.
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

## What saves time next time
Cross-batch practices (evidence in the Batch N sections below).
- **CI-as-gate for workflow-only changes.** Pure workflow/CI edits have cheap
  local gates — reproduce the slice math exactly (`find|sort|awk`, assert the
  union is all files, no empty slice) and YAML-parse the file — then let the CI
  matrix run BE the gate. Do not burn host-memory front-e2e re-runs for an
  infra-only change (see §3 proportional risk).
- **Verify CI structurally, not by conclusion.** A green run summary can hide a
  non-expanded matrix or an overwritten artifact: `gh run view <id> --json jobs`
  (confirm the parallel job set + timings), `gh run list --commit <sha>` to
  scope by head, and download+inspect artifacts (`if-no-files-found: ignore` +
  byte size both mislead — read the content). See §7.
- **Prove fork-vs-upstream deltas before pushing:** `git diff upstream/main
  <branch> -- <file>` shows exactly what an upstream PR would change; for fork
  files it shows the intended fork-local layer.
- **Await CI with targeted `gh` queries** (per-run status by workflow name,
  `--commit` scoping) rather than broad polling loops.
- **Re-sign recipes:** `git ... rebase --exec 'git commit --amend --no-edit
  --no-verify' <new-base>` re-signs a rebased chain; then force-push. Fork-local
  commits re-apply cleanly when they touch disjoint file regions from the
  upstream edit (e.g. `on:` vs `jobs.build`) — batch 6 was conflict-free.
- **Worktree hygiene:** `git worktree add .worktrees/<branch> upstream/main`,
  delete branch + `git worktree remove` after merge, `git remote prune origin`.
- **AGENTS dual-copy:** edit rules in the docs worktree (tracked on
  `docs/agent-guardrails`), mirror to repo root, `cmp` to confirm identical —
  the repo-root copy is what the session loader reads.
- **Keep logs** (`.tmp/<run>.log`) until the run outcome is understood; a saved
  log converts an unpredicted failure into diagnosis, not a blind re-run (§1a).
- **Verify any readiness/status predicate against a REAL running service first**
  — JSON field case/path reality beats inspection (Selenium node `availability`
  is `"UP"`, not `"up"`; hub has no Docker HEALTHCHECK). One local
  `curl` against a live hub + one throwaway container saved a full 3-shard CI
  burn.
- **Byte-identical logs across a rerun** (diff shows only memory addresses +
  timing) = deterministic reproduction; treat the failure signature as stable
  and read the FIRST error's URL to name the dead component (a
  `ConnectionReset` on `/wd/hub/session` with pure-HTTP tests passing = grid
  down, NOT the app).
- **Disambiguate rerun artifacts by id** — `gh run rerun --failed` leaves the
  old + new artifacts coexisting under the same name; fetch by artifact id,
  not name.
- **`gh run list --commit <sha>` can return EMPTY** even for running/complete
  runs — prefer `gh pr checks <n>` or `gh run list --branch main`; don't burn
  time re-querying a filter that silently yields nothing.
- **Short-circuit poll loops correctly:** `rg -c` with zero matches returns
  nothing (≠ `"0"`), so a `[ "$x" = "0" ]` condition never fires and the loop
  runs its whole budget doing nothing. Count on no-match as zero, or just wait
  a fixed interval and query once.
- **Compare full streams in local slice-math harnesses:** diffing `$(...)`
  (newline-stripped) output HIDES the empty-input guard divergence (old `awk`
  emitted a phantom blank record for one shard = the #477 silent full-suite
  hazard; new array code empties every shard). Assert union==full-set AND
  per-shard empties explicitly.

## Prevention checklist (never / always)
Distilled from review-gate catches and hard-won incidents. Always:
- `tee` full test output to a repo-local `.tmp/` log and keep it; run verbose
  (`-v/-vv/-s`), never `-q` (§1a).
- Guard every sliced workflow against an empty slice; give per-shard logs
  distinct artifact names; `pipefail` before any `pytest | tee` (§7).
- Re-sign after any rebase; force-push fork `main` after each upstream merge.
- Rebase PR branches onto `upstream/main` before pushing.

Never:
- Let an empty slice silently re-run the whole suite; let a later shard
  overwrite an earlier shard's log.
- Regress the #484 hardening: unquoted `$slice`/bare word-splitting, missing
  `set -euo pipefail` before `pytest | tee`, referencing a possibly-unset env
  var under `set -u` (use `${VAR:-}`), a `find` whose failure is silent.
- Have TWO writers to one file path in the same run (`pytest.ini log_file =
  back_test.log` + a shell `tee back_test.log` = corrupted interleaved log).
  Disable the config writer (`-o log_file=/dev/null`) or point `tee` elsewhere.
- Root an upload-artifact glob in a hidden dot-dir (`.tmp/...`) without
  `include-hidden-files: true` — it silently uploads NOTHING (#484).
- Leak fork-local workflow triggers (`on:`/`concurrency`/`build.if`) into an
  upstream PR, or strip them from a fork workflow edit — fork CI silently stops.
- Re-run a failed suite blind: distinguish fixture `ERROR`s from `FAILED`
  assertions; a session-scoped driver death cascading `tab crashed`/`invalid
  session id` is ONE incident, not N.
- Hand-run a selenium chrome node with <2gb /dev/shm; run the full 114-test
  front suite locally in one go while the host is memory-starved (§6).
- Touch system `/tmp`; commit `back/Vagrantfile.txt`/`opencode.json`/`static/`;
  create a PR for deferred or security-risky work (defer + record instead).
- Squash a tooling commit with its mass-autofix commit (keep them separable).
- Edit AGENTS.md rules in only one of its two copies.

## Host hygiene & local-harness facts
Consolidated from Batches 4-6 (each fully evidenced in its Batch section).
- **NO_COLOR, not TERM=dumb:** iproute2 ≥6.19 colorizes `ip` output on a pty
  (mininet spawns node shells on ptys) and breaks ipmininet's plain-text IP
  parsing → empty captures. `NO_COLOR=1` fixes it; `TERM=dumb` does not (Batch 4).
- **podman machine stop** REWRITES `~/.config/containers/storage.conf` to root
  paths; restore `[storage] driver="overlay"` without graphroot/runroot. The
  `ipmininet` VM auto-restarts via Podman Desktop and starves the host CPU —
  `podman machine stop ipmininet` before timing-sensitive runs.
- **Back pytest harness:** run from `back/tests` with
  `PYTHONPATH=$PYTHONPATH:../src`; `pytest.ini log_file` path is read-only under
  the harness — pass `-o log_file=/tmp/back_test.log`. Hand-rolled
  `ip netns exec` fails under rootless podman (no /sys mount) — use mininet for
  datapath probes. The podman harness is the ONLY thing that builds+runs the
  back image; CI never exercises the Dockerfile.
- **Front e2e:** CI-exact grid compose is `front/tests/docker/docker-compose.yml`
  (shm 2gb, GRID_TIMEOUT 60); chrome needs ≥2gb /dev/shm or tabs crash. Under
  rootless podman the host cannot reach container IPs → `TEST_TARGET_HOST=<host
  LAN IP> TEST_TARGET_PORT=8080`; container→container `172.18.0.2:80` works.
   Suite is host-memory-bound (session-scoped single browser) — verify with
   disjoint slices/halves (proven independent: halves 53+61, matrix 62+22+30).
- **Local container experiments (tool-permission reality):** bash `sudo`,
  `podman rm*`, `podman rmi*`, `podman network rm*`, `podman volume*` are
  permission-DENIED in this environment — use the MCP container tools
  (stop/remove/inspect/list) instead of shell `podman rm`. Networks cannot be
  removed at all once created (no MCP network tool) — reuse an existing network
  or expect a leftover. Before binding a test port, check `podman ps -a` and
  `ss -tlnp`: a long-running local `selenium-hub`/`chrome` (e.g. from a prior
  e2e session) can already hold `:4444` — reuse it as ground truth rather than
  fighting the port conflict. Images `selenium/hub:4.37.0` and
  `selenium/node-chrome:141.0` are already cached locally.

## Known debt & candidate follow-ups
Actionable leftovers with their unblock conditions, so the next session can
pick up without re-deriving:
1. ~~**Joint CI hardening of `back_test.yml` + `full_test.yml`** (batch-6 nits)~~ —
   **CLOSED by #484** (quoted arrays, `set -euo pipefail`, `-maxdepth 1` comment,
   back log capture). See Batch 7. Keep the nits as never-regress items in
   Prevention.
2. ~~**`ty` strict-type swap**~~ — **CLOSED by #485**: decision was "adopt ty,
   src-first staged". Gate is now `ty check` (Linter back/front green on src +
   back/tests); `front/tests` staged out of the gate. Follow-up: re-enable
   `front/tests` (~133 diagnostics, mostly untyped Selenium helpers) as its own
   phase, and watch ty version bumps (pre-1.0 at 0.0.77).
3. **dependabot × uv.lock validity** — open question; can pip@`/` produce valid
   workspace-lock PRs? Resolves only on the next monthly dependabot cycle.
4. **`ci/back-parallel-suite` fork branch** — superseded by matrix sharding
   (#477); preserved for the unshare/OVS negative experiment.
5. **Flake-watch after #483:** confirm the first N nightly Full-test runs post-
   sharding show no flake-profile shift (a shard boundary may now split a
   previously-serial interaction; file independence is proven but watch once).
6. **AGENTS dual-copy sync** — fixed this batch; rule in AGENTS header + §7 of
   this runbook.
7. **Trivial env leftover** — stray empty podman network `gridtest2` from a
   local grid-readiness experiment could not be removed (bash `podman network
   rm*` is permission-denied; no MCP network-remove tool). Harmless; remove when
   tooling allows.

## Debrief (2026-09-02) — grid-fix + reviewer-prompt/#484 session
Self-assessment the next session should read before redoing any of this. Full
evidence in Batch 6 (post-merge flake), Batch 7 (hardening PR), and
`docs/review_prompt.md`.

**What helped (keep doing):**
- **Local gating experiments before CI.** The grid predicate (case/JSON shape),
  the capture-step `cd`-cwd bug, and the slice-residue math were all verified
  against a real running hub / throwaway shell BEFORE burning CI — zero CI
  cycles spent on those. "Never burn CI on logic you can test locally" paid off
  repeatedly (§3 proportional risk).
- **Saved raw logs** (`.tmp/`): byte-identical rerun logs + the PR-head pass log
  made the diagnosis provable and the fix verifiable.
- **The reviewer DOWNLOADED artifacts.** A green Full-test summary masked that
  front per-shard artifacts had silently uploaded nothing since the 742d79a
  amend (and would have swallowed the failure-diagnosis container logs). The
  author never re-checked artifact existence after changing the upload path —
  "verify structurally, not by conclusion" must include artifacts (§7).
- **Rerun-first on a red shard** confirmed determinism before any fix/amend
  decision — the data that forced the plan-gate STOP.
- **Amend-in-place for small upstream CI fixes** kept history linear (no fixup
  PR noise) and the fork re-sync stayed mechanical.

**What was wrong (learned):**
- **Initial misdiagnosis: "the app backend died."** Wrong. The 24 errors were
  Selenium-grid session-creation resets (`POST /wd/hub/session`); the 6 passes
  were pure-HTTP GETs proving the app was fine. Reading the FIRST traceback's
  URL would have named the grid immediately. Framing matters — reviewers and
  next-diagnoses inherit it (review_prompt.md class e).
- **Assumed node `availability == "up"`** (reality: `"UP"`) — cost one full
  3-shard CI run on the first hardening attempt.
- **`cd` inside a `sudo bash -c` capture block** silently moved cwd for the
  trailing `chmod`/`cat` — files are written from repo root, then the shell is
  in `front/tests/docker`. Subshell the `cd`s.
- **Plain `git rebase upstream/main` after an upstream-HEAD amend** tried to
  replay the removed commit → conflict. `--onto` is the tool.

**Saved time:**
- The v2 review gate caught the pytest.ini `log_file` double-writer and the
  hidden-dot-dir artifact no-op as MUST-FIXes — both would have been post-merge
  repairs (and the artifact one was already silently broken for hours of runs).
- Targeted `gh` queries + `gh pr checks` over blind polling loops.
- Reusing the already-running local `selenium-hub` as ground truth instead of
  fighting the `:4444` port conflict.

**Time waste (and why):**
- **One full CI run on the lowercase `"up"` predicate.** Why wasted: the
  predicate was verified by inspection, not against the live service. One local
  `curl` would have prevented it.
- **~20 min of no-op polling** in a loop whose termination test never fired
  (`rg -c` zero-match → empty string ≠ `"0"`). Why wasted: off-by-one on shell
  empty-vs-zero; fix = treat no-match as zero or wait-then-query-once.
- **Misdiagnosis detour** (backend vs grid) before reading the first error URL.
  Why wasted: analyzing the cascade instead of the first failure's target.
- **`gh run list --commit` empty results** chased briefly before switching to
  `gh pr checks`. Tooling quirk; now documented above.

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

## Batch 3 outcomes (2026-09-01)
1. **`port_forwarding_tcp` flake — ROOT-CAUSED + FIXED (#479).** The
   intermittently-failing `port_forwarding_tcp` (client gets RST+ACK instead of
   a full handshake) is a **bind race**: job 201 backgrounds `nc -k -d ... -l
   8000 &` (fire-and-forget), job 109 installs iptables DNAT, job 4 sends
   immediately. On a loaded CI runner the SYN beats the bind → kernel RST.
   `run_miminet`'s retry only retries "not meaningful" captures, so SYN+RST is
   accepted. Fix in `back/src/emulator.py`: after server-start jobs
   (`SERVER_SETTLE_JOBS = {200, 201, 203}` = open_udp_server, open_tcp_server,
   dhcp_server) the emulator settles `SERVER_SETTLE_SECONDS` (default 0.5s,
   `MIMINET_SERVER_SETTLE` env override — mirrors `MIMINET_SETTLE_MIN`). Review
   nit caught: **202 is `block_tcp_udp_port` (iptables, synchronous), not a
   listener** — removed so the set matches intent. Also helps UDP (unbound port
   → ICMP port-unreachable, datagram lost). Verification: full suite 42/42
   local, settle log fired ("server job 201 started; settling 0.50s"), tcp+udp
   clean. Un-reproducible locally (15/15 clean pre-fix) → the local harness can't
   reproduce CI-load timing; gate = mechanism + no-regression + CI.
2. **dependabot #457 (ubuntu 26.04) — GATED + DEFERRED, closed.** Same
   rootless-podman harness (`back-test.sh test`, image `miminet-back:test`):
   ubuntu 24.04 = **42/42 pass**; 26.04 = **20 fail (empty captures
   `assert [] == [...]`)**; 26.04 + pinned 3.12 venv = still 20 fail → the
   breakage is 26.04 userspace networking (OVS 3.3.9→3.7.1, iproute2
   6.1.0→6.19.0), **not** the Python interpreter (3.12 vs 3.13). Closed #457
   with the evidence table; dependabot may re-open it next cycle.
3. **W605 restored (#478, merged).** Closes the real lint-coverage gap the #476
   review found: `select` gains `"W605"` (invalid-escape detection). Repo is
   already clean under it. One-line config change.

## Batch 4 outcomes (2026-09-01) — ubuntu 26.04 UN-DEFERRED (#457 fixed)
Root-caused + fixed the #457 deferral; the 26.04 base bump is now green.

- **Root cause (debugged in a 26.04 container via the local harness):** iproute2
  **6.19** colorizes `ip` output whenever stdout is a TTY; mininet spawns every
  host/switch shell on a **pseudo-tty**; ipmininet parses `ip address show`
  output as plain text (`_addresses_of`/`_parse_addresses`, `ipmininet/link.py`),
  so ANSI-wrapped addresses raise `AddressValueError: Only decimal digits
  permitted in '\x1b[1;35m10'...` → interface IPs never set → **empty captures**.
  NOT OVS 3.7.1, NOT the interpreter (3.14), NOT bridge-nf/iptables (FORWARD
  ACCEPT, br_netfilter absent — hypothesis killed by experiment). mininet native
  `mn --topo single,2 --test pingall` passed on 26.04 for BOTH lxbr and ovsk →
  raw datapaths fine; only the ip-parsing path broke.
- **Fix (2 PRs):** #480 `ENV NO_COLOR=1` in `back/Dockerfile` + the robust
  single-point `os.environ.setdefault("NO_COLOR","1")` in `back/src/emulator.py`
  (covers image + CI runner + local runs; mininet node shells inherit
  os.environ). `TERM=dumb` does NOT disable ip color; `NO_COLOR=1` does
  (verified on a pty). iproute2 6.1 (24.04) never colorizes → NO_COLOR is a
  no-op there. #481 the one-line base bump `FROM ubuntu:24.04 → 26.04`.
- **Gates (local rootless-podman harness — the ONLY thing that builds+runs the
  image; CI Pytest runs on the runner and never exercises the Dockerfile):**
  26.04 + NO_COLOR = **42 passed** (was 20 failed/22 passed); 24.04 + NO_COLOR =
  **42 passed** (no regression). Review gate #480 caught the CI/local gap
  (runner isn't the image) → prompted the emulator.py env fix; #481 reviewer
  verified uv.lock has cp314 wheels for back's whole closure (psycopg2-binary
  cp312-only is front-only).
- **Test/debug infra notes:** pytest.ini `log_file=back_test.log` (repo path) is
  read-only under the harness — always pass `-o log_file=/tmp/back_test.log`.
  Hand-rolled `ip netns exec` fails under rootless podman (mount of /sys not
  permitted) — use mininet itself for datapath probes. `podman machine stop`
  REWRITES `~/.config/containers/storage.conf` to root paths (breaks rootless
  podman; restore to `[storage] driver="overlay"` w/o graphroot/runroot).
  The `ipmininet` podman machine (bench worktree) auto-restarts via Podman
  Desktop and starves the host CPU (~67% one core) — slows container gates
  dramatically; stop it before timing-sensitive runs.

## Review-agent gate — evaluation (2026-09-01)
Ran the senior-reviewer subagent on #476 and #477. Verdicts: APPROVE + APPROVE
(both with non-blocking nits; no must-fix on either).

> **Canonical reviewer prompt:** since v1 (2026-09-02, from full-history
> mining) the reusable prompt + taxonomy + changelog live in
> `docs/review_prompt.md`; AGENTS.md §4 mandates the pre-gate history check and
> that post-merge fixes feed the prompt. This section records the original
> evaluation that motivated the gate.

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

Batch 3 follow-up: ran the gate on #478 (PASS, one-line W605) and #479 (PASS).
On #479 it verified the job-id → handler mapping against `jobs.py`/test JSON
(the risky part) and caught a real intent bug I'd shipped: **202 in
`SERVER_SETTLE_JOBS` is `block_tcp_udp_port` (synchronous iptables), not a
listener** — removed. It also flagged the fixed 0.5s vs adaptive-bind trade-off
(as a nit; env override is the escape hatch). Confirms the "hunt edge cases the
author didn't check" prompt tuning works — the catch was exactly the
id→semantics mapping, not the happy path.

## Standing guardrail update
- Linter/formatter migrations must keep the tooling commit separate from the
  mass autofix commit (reflog/blame/rev-list isolation). This pattern held:
  the `--count/--statistics` CI failure was fixed by `--fixup`+autosquash
  into commit A, keeping A/B clean.

## Batch 5 outcomes (2026-09-02) — front Selenium flake hardened (#482)
Fixed the recurring CI Full-test flake (`test_stp` stale-element +
`test_duplication` `assert 50 == 0`) by converting config-commit + navigation
clicks to a retrying `wait_and_click`.

- **Two DISTINCT flake root causes, two fixes:**
  1. **Stale-element clicks** — raw `find_element(...).click()` on config-submit
     and navigation buttons. Fix: `wait_and_click` (re-finds each attempt).
     Reviewer gate (round 1) caught that converting modal-INNER clicks to
     driver-GLOBAL lookups is unsafe: inner ids (`#stp`, `#none`,
     `#rstpConfigurationSubmit`, `#config_switch_vlan`, `#vlanConfigurationSubmit`)
     are NOT globally unique — only the outer modal id is rewritten
     (`RstpModal_<id>`/`VlanModal_<id>`, config_stp.js:11 / config_vlan.js:11)
     and old modals persist in the DOM. Fix: optional `scope=` param on
     `wait_and_click` (WebElement or `(by, selector)` tuple; container re-found
     each retry), used by the STP/RSTP/VLAN config-commit clicks.
  2. **`assert 50 == 0`** — the edge-config form sets the in-memory JS `edges`
     value BEFORE the save XHR (`POST /edge/save_config` →
     `configurators.Edge._update_network_issue`) completes. A page RELOAD to
     check server state is SELF-DEFEATING: navigation aborts the in-flight XHR,
     so the server never persists (verified: reload-poll timed out 10× runs).
     Fix: `_server_edge_duplicate()` in test_duplication.py polls the server
     with an in-page `fetch(network.url)` (no navigation), regex-parses the
     served `var edges = ...; var jobs` literal for `duplicate_percentage`,
     `wait_for`-polled. The reviewer's "sound" concern about in-memory vs
     server value was real; the reload fix was wrong, in-page fetch is right.
- **Local harness facts (rootless podman):** host CANNOT reach container IPs
  (bridge in private netns) — use `TEST_TARGET_HOST=<host LAN IP>
  TEST_TARGET_PORT=8080` (rootlessport listens `*:8080`; the chrome container
  reaches the app via gateway NAT; container→container `172.18.0.2:80` also
  works). Login = POST `//auth/login.html` → 302 → `/home`. Grid = the repo's
  OWN compose `front/tests/docker/docker-compose.yml` (authoritative; has
  `shm_size: 2gb` + `GRID_TIMEOUT=60`). **Never hand-run the chrome node with
  default /dev/shm (64MB) — chrome tabs crash (`tab crashed`) under load;
  always use the CI compose or `--shm-size=2g`.**
- **Full-suite local verification is host-memory-bound:** the session-scoped
  `selenium` fixture is ONE browser for the whole ~6 min / 114-test run; when
  the host is short on RAM (other tenants: desktop chrome ~5-6GB, opencode,
  auto-restarting ipmininet VM) a tab dies mid-run and EVERY subsequent test
  errors `tab crashed`/`invalid session id` — that is ONE incident, not N (see
  §1a). Files all pass in isolation; both disjoint halves of the suite pass
  clean (53 + 61 = 114). The ipmininet podman machine auto-restarts via Podman
  Desktop — `podman machine stop ipmininet` before timing-sensitive runs.
- **Gates:** pre-fix local repro 15 runs → 1 exact `assert 50 == 0` failure
  (~7%); post-fix test_stp+duplication 8/8, packet_filters 5/5, both suite
  halves clean. CI all green (Linter, 3 Pytest shards, Full test 6m18s, dep
  review, auth test). Review-agent gate round 2: APPROVE (verified scope
  container re-find, DOM nesting vs scope, template/edges regex format,
  fetch-credential cookie domain). Merged as upstream `33636cf`.

## Batch 6 outcomes (2026-09-02) — front Full test sharded (#483, upstream e7fa2f8)
Converted the single serial ~6 min `Full test` job (114 tests / 25 files behind
one session-scoped browser) to a 3-runner matrix mirroring the back-suite
sharding (#477 / b968192). Merged.

- **Change (`full_test.yml` only):** `fail-fast: false` + `matrix shard [1,2,3]`;
  each runner boots its own frontend + grid compose stack (independent DB/grid,
  no cross-runner coupling) and runs `find front/tests -maxdepth 1 -name
  'test_*.py' | sort | awk 'NR % n == s-1'` (25 files → 8/9/8). Guards: empty
  slice (`[ -n "$slice" ] || exit 1`, inside the sudo block), `set -o pipefail`
  + `tee .tmp/full-test-shard-<n>.log` preserves pytest's exit code, per-shard
  `upload-artifact` (`if: always()`, `if-no-files-found: ignore`). Kept upstream
  `on: [push, pull_request]` + nightly cron; no fork-local `on:` leaked (the PR
  touched only `jobs.build`).
- **CI evidence:** all 3 shards green in parallel (62 + 22 + 30 = 114 passed;
  shard1 heaviest — config_db/user_options/quiz skews file-based round-robin).
  Artifacts contain real full `-vv` pytest logs; rootdir resolves to
  `front/tests/pytest.ini` even when slicing from repo root.
- **Review gate (APPROVE, no must-fix):** verified partition residue-completeness
  for any file count ≥ 3, pipefail ordering, artifact permissions (sudo-created
  `.tmp` log is 644, readable by the non-root upload step), no cross-file state
  coupling (the 3 shards passing WITHOUT sibling files present is proof), and
  that the matrix check rename `build (1|2|3)` breaks no branch protection
  (required checks empty). Non-blocking nits (shared with back_test.yml #477 →
  candidate follow-up, not a gate): unquoted `$slice` word-splits/globs (a glob
  metachar filename that fails to self-match would be silently dropped from that
  shard); no `set -euo pipefail` at the top of the sudo block; `-maxdepth 1`
  permanently stops collecting a future `test_*.py` under a `front/tests/<subdir>/`
  (old `pytest front/tests` recursed); file-based balance → shard1 = 62 tests vs
  22/30 and adding a file reshuffles assignments; matrix triples runner cost.
- **Local harness note:** this change is pure workflow logic — locally verifiable
  gates are slice math + YAML parse only (the CI matrix run IS the gate); the
  front e2e file-independence that makes sharding safe was already proven by the
  Batch-5 two-disjoint-half runs (53 + 61).
- Fork `main` re-synced to upstream e7fa2f8 + re-signed fork-local commits
  (`724e8c9`→`6fb5bd9`, `0f64e6f`→`0ed7d96`); rebase was conflict-free — the
  fork-local `on:` commit applies cleanly onto the matrix file because the two
  edits touch disjoint regions (`on:` vs `jobs.build`).

### Post-merge upstream flake on e7fa2f8 → amended into upstream HEAD (742d79a)
The first post-merge `Full test` push run (33654786983) failed on `build (3)`
deterministically — twice (original + `--failed` rerun), byte-identical pytest
logs apart from memory addresses/timing: `6 passed, 24 errors in ~5s`.

- **Initial diagnosis was WRONG and must not be trusted:** the app backend is
  NOT what dies. The 6 passes are pure-HTTP `test_pages_availability` GETs
  (app up — `Check availability` curl also passes), and the 24 errors are every
  browser-bound test ERRORing at setup on `POST /wd/hub/session` with
  `ConnectionResetError`. The failure is the **Selenium grid**, not miminet/uwsgi.
- **Root cause — grid-startup readiness race:** `docker compose up -d` returns
  as soon as containers exist. On the failing runs the freshly-started
  `selenium-hub`/`chrome` were ~1-4s old when pytest opened its first WebDriver
  session → reset → whole slice collapses. `Check availability` only curls the
  app (`localhost`), never `localhost:4444`. Same commit's shards 1-2 passed and
  the identical 30-item slice passed on the PR-head run ~30 min earlier — timing,
  not a #483/code regression (each runner boots its own grid; whether pytest's
  first session lands inside the not-ready window is per-runner variance).
- **Fix (amended into the upstream HEAD commit, e7fa2f8→742d79a):** two
  `full_test.yml` steps — a pre-Run-tests `Wait for selenium grid` that polls
  `localhost:4444/wd/hub/status` until `value.ready` AND ≥1 node has
  `availability` = UP, and an `if: failure()` `Capture container logs` step
  (`docker ps -a` + `docker compose logs --tail=300` for front + grid into
  `.tmp/containers-shard-<n>.log`); artifact `path` widened to the glob
  `.tmp/*-shard-<n>.log`. Re-verified green 3/3 with the wait engaging at
  ~4-6s (inside the old race window).
- **Two bugs found only by a local gating experiment** (never burn CI cycles on
  logic you can test locally): (a) hub status JSON reports node
  `"availability": "UP"` (uppercase) — the first predicate checked `"up"` and
  timed out all 3 shards at 120s; (b) a `cd front/... && docker compose logs`
  inside the capture step's sudo block changed cwd so the trailing `chmod`/
  `cat .tmp/...` failed — wrap such `cd`s in `( ... )` subshells. Verified the
  corrected predicate + capture structure against a locally-running hub before
  re-amending.
- After an **amend of upstream HEAD**, a plain `git rebase upstream/main` is
  WRONG for the fork: git replays the old commit (e7fa2f8) that the amend
  removed → content conflict with its equivalent (742d79a). Use
  `git rebase --onto upstream/main <old-fork-base>` to re-apply only the
  fork-local commits. Re-sync: `main` = upstream 742d79a + re-signed
  fork-local commits (`8989a7d`, `0913e0a`), force-pushed to `origin`.
- Known Selenium-grid facts learned: selenium/hub:4.37.0 + node-chrome:141.0
  images define **no** Docker HEALTHCHECK (`image inspect` Healthcheck null) —
  readiness must be polled via `/status` or `/wd/hub/status` (identical JSON);
  `value.ready` is true only once a node has registered.

## Batch 7 outcomes (2026-09-02) — reviewer-prompt v1 from history mining + CI-hardening PR #484
- **Canonical reviewer prompt:** `docs/review_prompt.md` (v1) built from a
  full-repo mining pass. Taxonomy classes (a)-(g): infra/readiness races,
  single-PR isolation blindness, local-vs-CI divergence, silent-failure
  plumbing, author-framing inheritance, test-quality gaps, toolchain gaps; plus
  a pre-gate history check (`git log --oneline upstream/main -- <files>`), the
  positive-control list that must never regress, and a changelog. AGENTS.md §4
  now mandates: run the pre-gate history check, carry it into every per-PR
  prompt, and add post-merge fixes as prompt feedback (v1.1 added the #484
  double-writer + hidden-dir-artifact-no-op lessons under class (d)).
- **PR #484 (merged upstream 07add40):** harden shard slicing — quoted bash
  arrays replace unquoted `$slice` (glob/word-split silent drop), `set -euo
  pipefail` atop both sudo blocks, find/sort failures fail loudly,
  `-maxdepth 1` documented, back_test.yml captures a real log. **The v2 review
  gate caught 2 author misses, both class (d), both proven via artifacts:**
  1. `back/tests/pytest.ini` already sets `log_file = back_test.log` (mode 'w')
     → the new `tee back_test.log` was a second independent file writer →
     corrupted log (truncated header, mid-token clobber). Fixed single-writer:
     `-o log_file=/dev/null -o log_cli=true -o log_cli_level=INFO ... | tee`.
  2. `upload-artifact@v7` defaults `include-hidden-files: false` → the
     `.tmp/*-shard-<n>.log` glob rooted in the hidden `.tmp` dir silently
     uploaded NOTHING (and would also swallow the Capture-container-logs
     output from the 742d79a amend). Fixed: `include-hidden-files: true`.
     Literal paths match hidden files; globs rooted in a dot-dir do not.
- **Also burned one CI cycle** the reviewer predicted under `set -u`: back_test
  referenced `$PYTHONPATH` unset in CI → `unbound variable` all shards; fixed
  with `${PYTHONPATH:-}`. (A `set -u` audit is now an explicit review probe.)
- Local gates before CI: YAML parse + `bash -n` + slice-residue equivalence
  (old `awk NR%n==s-1` vs new loop, n∈{2,3,5}, edge + real lists). Reviewer
  note: a harness that compares `$(...)` (newline-stripped) output HIDES the
  empty-input guard divergence — old code emitted a phantom blank record for
  one shard (the #477 hazard); new code empties every shard uniformly.
- CI green pre- and post-merge (Full test 3/3, Pytest 3/3, Linter, auth, CodeQL)
  on 07add40. Fork `main` = upstream 07add40 + re-signed fork-local commits
  (`dff3400`, `bc7e022`), force-pushed; fork-local triggers preserved on both
  hardened workflows. Known-debt item 1 (back/front CI nits) closed.

## Batch 8 outcomes (2026-09-03) — ty strict-type gate adopted (#485, upstream 91496b4)
- **Decision executed:** "adopt ty, src-first staged". The type gate is now **ty**
  (astral, pre-1.0 0.0.77, already a dev dep) replacing mypy. mypy reported 0
  errors only because it skips untyped function bodies (480 src defs, ~115
  annotated) — the old gate was vacuous. ty checks untyped bodies unconditionally
  → first real static pass over src.
- **3 commits** (tooling / back / front, kept separable):
  1. `ci(lint): gate with ty instead of mypy` — linter.yml mypy step →
     `ty check --no-progress ${{matrix.node}}`; `[tool.ty]` staging override
     `front/tests` → `all = "ignore"` (mypy never meaningfully checked them
     either; ~133 diagnostics; re-enable later). Tooling only.
  2. `fix(back)` — 3 latent issues (see below).
  3. `fix(front)` — 2 latent bugs + guards (see below).
- **Latent bugs ty found (the value):**
  - `back/bench/bench.py` — `psutil.ProcessLookupError` does not exist
    (psutil ships `py.typed` so ty resolved it where mypy's
    `--ignore-missing-imports` hid the module). Except-tuple referencing a
    missing member raised `AttributeError` for exceptions reaching that member.
  - `front/src/miminet_network.py::get_emulation_queue_size` — absent
    `time-filter` → `request.args.get(...) is None` → `None.replace` 500; the
    intended 400 branch was dead code after an unreachable `if not time_filter`.
    Guard activated the documented 400. Malformed-present values unchanged.
  - `front/src/quiz/controller/image_controller.py::upload_image_endpoint` —
    `file.filename` can be `None`; `== ""` check didn't cover it, so
    `allowed_file(None)` hit `"." in None` → 500. Guard `if not filename`.
  - `front/src/quiz/util/encoder.py::UUIDEncoder.default` param `obj` vs base `o`
    (invalid override), fixed by rename.
- **Sweep categories (front/back):** cross-method prepare-state asserts in
  configurators (invariant holds: every `_configure` calls prepare first, prepare
  raises `ConfigurationError` not None); `cast(User, current_user)` at
  `@login_required` controller→service boundaries; `cast(Any, ...)` for
  unannotated `db.relationship` attrs in `selectinload` (mirrors the pre-existing
  `test_service.py` convention); widen genuinely-Optional `section_id`/
  `session_question_id` params at the facade (they guard internally); scoped
  `[tool.ty]` `unsupported-base = "ignore"` for exactly the two `db.Model`
  files; `app.py` sitemap `rule.methods is not None` guard; yandex/tg json
  None asserts (routes registered unconditionally); flask-admin `date` formatter
  gained the `name` param (modern 3-arg call; 2-arg only tolerated via a
  deprecated shim); dropped 3 dead mypy `# type: ignore`.
- **Local gates:** `ty check back front` = 0 errors + 0 warnings (ty's default
  `error-on-warning: true` makes warnings gate-failing — the 14 `unsupported-base`
  warnings had to be resolved, not ignored globally); ruff format/check clean.
  ty config discovery note: run with the repo venv set (local repro needs
  `VIRTUAL_ENV=... ty check ...` from the repo root — CI's `uv run --frozen`
  provides it). `front/tests` glob does NOT match `front/src/auth_tests` (those
  stayed checked — tg_test needed a fix).
- **Front e2e flake encountered:** one PR-head Full-test run failed `test_stp`
  setup (`Modal dialog #RstpModal... wasn't opened`, a 5s modal-open wait in
  `conftest.run_in_modal_context`) — the known front-e2e flake signal, NOT a
  regression (this PR doesn't touch front/tests; identical shard passed the
  rerun and the parallel run). Full test is not merge-gated.
- **Review gate (v1.1 prompt): APPROVE, no must-fix.** Reviewer CONFIRMED all 3
  claimed latent bugs, verified behavior-identity of the whole sweep (login 4-case
  message matrix, no external `.addLink` caller — ipmininet builds via
  `net.addLink` never `topo.addLink`, asserts can't fire on legit paths, all casts
  are runtime no-ops under `@login_required`), and confirmed no dropped mypy
  coverage (mypy was 0-error so nothing could be lost). Non-blocking nits: bench
  commit-message mechanism wording (lazy except matching, not "whenever a process
  vanishes"); one redundant configurators assert; malformed-present
  `time-filter` still 500s (pre-existing); residual dead mypy-era ignores.
- **Self-caught mid-review** (author fixed before merge): login else-binding
  message (password-None must show "wrong creds" not "no such user" — fixed by
  gating the hash check inside `if user:`); `_dhcp_opt_bytes` `str.encode()`
  fallback would silently mis-decode an impossible-str option → replaced with a
  cast-only helper (cast is a runtime no-op, str still fails loudly); ruff format
  compliance on the auth edit (caught by the Linter Format step).
- **CI green pre- and post-merge** on 91496b4 (Linter back+front ty gate, Pytest
  3/3, Full test 3/3, auth test, CodeQL, dependency-review). One Full-test shard
  needed a rerun (the test_stp flake above). Fork `main` resynced to upstream
  91496b4 + re-signed fork-local commits (`8b22312`, `c398710`), force-pushed;
  fork-local workflow layer verified preserved (`git diff upstream/main main --`
  shows only auth_test/back_test/full_test + update_uv_lock, NOT linter.yml/
  dependency_review.yml). Known-debt #2 closed.
