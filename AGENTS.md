# AGENTS.md — Rules and Guardrails for AI agents working in this repo

These are standing instructions distilled from prior autonomous work. They apply
to every agent session. Where they conflict with a user instruction in the
current conversation, the user instruction wins for that session — otherwise
follow these.

## 0. Operating boundaries (hard constraints)
- Work only inside the project directory. No reads/writes in `/tmp`, `~/.cache`,
  `/etc`, or other outside paths. If a tool or command would touch them, redo it.
- Worktrees live under `.worktrees/<branch>` and are excluded from git via
  `.git/info/exclude` (repo-local, never committed).
- Treat harness plan mode as read-only: no edits, no mutating commands. Deliver
  a plan and wait for release, even if the user says "go".
- Never call blocking/question tools during a full-auto run. If a question is
  genuinely unavoidable, defer it and include it in the final report.

## 1. Full-auto execution rules
- Update `todowrite` continuously (add/complete items as you go; one
  `in_progress` at a time).
- Ask no questions until the final report. Report every deferred question at the
  end, with: alternatives considered, why no experiment could settle it, and
  what would unblock it.
- Match effort to confidence and verifiability (see §3).

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
- Sign every commit with the SSH signing key
  (`-c commit.gpgsign=true -c gpg.format=ssh
   -c user.signingkey=/home/me/.ssh/id_signing_github.pub`),
  using `--no-verify` to bypass the pre-commit hook (no config file present).
- CI chain: `Linter` runs on push/PR; `Pytest`, `Full test`, `auth test` trigger
  off `workflow_run: Linter completed`. Full test + auth test are the flake
  signal; do not gate merges on them.
- After each upstream merge, rebase fork `main` (re-apply the 2 fork-local
  commits) and force-push it.
- Merge order matters when PRs touch the same files: A → D → C → E.

## 5. Security rules
- Never commit or log secrets/tokens. Never commit `back/Vagrantfile.txt`,
  `opencode.json`, `static/`.
- Never leave the repo in a state that cannot install/build (e.g., deleting the
  only dependency manifest before its replacement lock exists).
- Do not create PRs for work that is deferred or carries unresolved risk.
