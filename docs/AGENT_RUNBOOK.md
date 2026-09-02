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
- `Full test` (front Selenium e2e) + `auth test` are the flake signal; do not
  gate merges on them. Full test runs nightly (`cron '0 2 * * *'`, PR A) and is
  **sharded across 3 matrix runners** (#483): each runner boots its own
  frontend + grid compose and runs a round-robin file slice of
  `front/tests/test_*.py` (`find -maxdepth 1 | sort | awk NR % 3 == shard-1`,
  8/9/8 files), empty-slice guard, `pipefail` + `tee` to
  `.tmp/full-test-shard-<n>.log`, per-shard artifacts
  (`full-test-logs-shard-<n>`). On the FORK this job additionally has a
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
- Use an unquoted `$slice`/`find -maxdepth 1` in new CI code — both are
  silent-coverage holes (#483 review nits, also latent in `back_test.yml`).
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

## Known debt & candidate follow-ups
Actionable leftovers with their unblock conditions, so the next session can
pick up without re-deriving:
1. **Joint CI hardening of `back_test.yml` + `full_test.yml`** (review-gate
   batch-6 nits, APPROVE'd as non-blocking): use `mapfile`/arrays instead of
   unquoted `$slice`, add `set -euo pipefail` at the top of the sudo block, and
   comment/document the `-maxdepth 1` constraint (permanent coverage hole for a
   future `test_*.py` under `front/tests/<subdir>/`). Small, locally verifiable
   (slice math + YAML parse), CI matrix run is the gate.
2. **`ty` strict-type swap** — deferred: 190 diagnostics vs mypy 0 (mypy skips
   untyped function bodies). Unblock: a decision on strictness; then a tooling
   commit separate from the type-fix sweep.
3. **dependabot × uv.lock validity** — open question; can pip@`/` produce valid
   workspace-lock PRs? Resolves only on the next monthly dependabot cycle.
4. **`ci/back-parallel-suite` fork branch** — superseded by matrix sharding
   (#477); preserved for the unshare/OVS negative experiment.
5. **Flake-watch after #483:** confirm the first N nightly Full-test runs post-
   sharding show no flake-profile shift (a shard boundary may now split a
   previously-serial interaction; file independence is proven but watch once).
6. **AGENTS dual-copy sync** — fixed this batch; rule in AGENTS header + §7 of
   this runbook.

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
