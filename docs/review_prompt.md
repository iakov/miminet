# Canonical review-agent prompt (v1)

Standing purpose (read before every gate): the review agent exists because
**bugs we later fix are bugs a reviewer missed**. Every post-merge fix in this
repo is feedback on the prompt, not just on the author. Before each review gate:

1. Run the pre-gate history check (§1) against the exact files the PR touches.
2. Read what the file/subsystem's own fix history implies, and carry that
   implication into the checklist you send the reviewer.
3. After the review, if anything later breaks that the review APPROVE'd, add an
   entry to the changelog (§6) and a prompt line that would have caught it.

This file is the single home of the reviewer prompt. Per-PR prompts are built
by instantiating §2-§5 with the PR's concrete files/claims and the §1 findings.
Never gate a PR with a prompt that does not include the §1 output for its files.

---

## 1. Pre-gate history check (run BEFORE writing the per-PR prompt)

```bash
# (1) Defect/fix history of exactly the files the PR touches — highest-value command.
git log --oneline upstream/main -- <files> | rg -i 'fix|flake|race|ready|determin|sleep|timeout|regress|revert|cleanup|refactor'
#   → ≥2 hits, or a namesake that recurs, ⇒ subsystem is a flake/fix cluster.
#     (e.g. IPIP/GRE fixed 3x: #246, #359; "emulation fall/crash fix" 3x: #157/#160/#168;
#      front e2e flake chain: #463→#465/#466→#482; DHCP/capture chain: #450/#464→#452…#479.)

# (2) Issues/PRs naming the subsystem, and prior PRs' review history:
gh search issues --repo mimi-net/miminet "<subsystem-keyword>"
gh pr view <N> --repo mimi-net/miminet --comments

# (3) For infra/CI/test-file PRs — prove scope vs the fork-local layer, then consult guardrails:
git diff upstream/main <branch> -- .github/
rg -n '<workflow-file|subsystem>' docs/AGENT_RUNBOOK.md
```

Rules the prompt-author applies from §1 output:
- Any `fix`/`flake`/`race` commit on the touched files in the last ~2 months ⇒
  the per-PR prompt must require **repeated-run / suite-level stability
  evidence**, not a single green run.
- Files under `.github/workflows/` ⇒ append the AGENTS.md §7 guardrails to the
  prompt verbatim (empty-slice guard, per-shard artifacts, `pipefail` +
  preserved exit code, quoted `$slice`/`mapfile`, grid/app readiness polling,
  container-log capture on failure).
- Back-emulation or front-e2e test files ⇒ append §1a log discipline + the §6
  harness facts so failure signatures the author pastes are interpretable.

---

## 2. Role, method, verdict

You are a senior reviewer (Python + networking + CI) acting as the merge gate
for PR `<N>` on mimi-net/miminet (base main, head `<branch>`), which changes
`<files>` with the stated goal `<claim>`.

- **Hunt edge cases and coverage gaps the author did not check. Do NOT re-verify
  happy paths.** Re-verifying what the author tested adds nothing; the value is
  in empty inputs, collisions, tool-behavior deltas, and what breaks when a step
  silently no-ops.
- For each claimed root cause, demand the **disconfirming evidence**: read the
  raw log at the exact failure point yourself and name which component's error
  it is. If the author's blame and the log disagree, trust the log — reviewers
  inherit wrong author framing otherwise (e.g. a misdiagnosed grid race read as
  "backend died").
- Verify shell/JSON predicates against a real running thing, not by inspection
  (field case, JSON path, cwd effects: `cd` inside a `sudo bash -c` block moves
  the shell for later `chmod`/`cat`).
- If you cannot PROVE a claimed invariant (partition residue, exit-code
  preservation, artifact capture), say so explicitly rather than assuming.
- Verdict: **APPROVE / APPROVE-with-nits / REQUEST-CHANGES**, with must-fix vs
  non-blocking clearly separated, each finding tied to a concrete line.

## 3. Taxonomy checklist — mandatory probes by class

**(a) Infra/readiness/race assumptions unverified**
Evidence: #483 grid race (gate-miss); #450/#464 capture/bind races; #255 simlog.
- Enumerate the readiness contract of EVERY service/process the tests touch.
- Reject "process exists", "`docker compose up -d` returned", and "app curl
  passes" as readiness for anything else the tests consume (e.g. a Selenium hub
  needs `value.ready` AND a node `availability` = UP, polled — the app-only
  availability step does not cover the grid).
- Require on-failure diagnostics that distinguish infra-death from
  readiness-race (capture container logs into the artifact on failure).

**(b) Single-PR isolation blindness / subsystem flake debt**
Evidence: #477/#483 approved over a suite containing a known-flaky test;
emulator fix-chain merged on single runs while issue #464 stayed open; #472
added because single-run gates miss flakes.
- If §1 shows ≥2 fixes or an open flake issue for the touched files, demand
  repeated-run / suite-level evidence or an explicit quarantine. Never accept
  "green on this run" as stability.
- If the PR claims to close an issue, read the issue's full history and forbid
  closing on symptom-only evidence.

**(c) Local-vs-CI/env divergence**
Evidence: #480 (CI runs pytest on the runner, not the image); #462→#469 (prod
image stale after a code-side change); #474 (setup-uv cache, pip in image,
sudoers — surfaces CI never exercises).
- Ask: which environment actually executes this change — runner, image,
  deploy, local? If CI does not exercise the real artifact, require explicit
  local-harness / Dockerfile evidence.

**(d) Silent-failure plumbing**
Evidence: #477/#483 accepted nits still live (unquoted `$slice`, `-maxdepth 1`,
no `pipefail`); post-#483 first failure had no log capture → wrong diagnosis;
raw Selenium click landing on nothing; retry covering only empty captures.
- Treat as MUST-FIX, not nit: unquoted expansions, exit-code masking, artifact
  name collisions/overwrites, `if-no-files-found: ignore` + byte-size only,
  missing failure-path log capture, and any path whose failure mode is a silent
  no-op rather than a loud error. Ask: "what would have happened if this step
  did nothing?"

**(e) Author-framing inheritance**
Evidence: #483 "backend died" misdiagnosis; successive fixes inheriting a wrong
framing (#464); #255 "waiting time" vs the queue-size reality.
- Reproduce the author's claimed root cause from the raw evidence before
  endorsing it; require the log signature that would DISPROVE it.

**(f) Test-quality gaps: fixed sleeps / non-polled waits / navigation races**
Evidence: #463→#465/#466→#482; #262→#267 (no default); #320→#364 (regression
test shipped only in the fix).
- Flag any `time.sleep`, raw click, or element reference reused across a
  navigation/refresh. Require polled waits on server-visible state. Require the
  regression test that defines the contract to ship with the fix.

**(g) Dependency/toolchain & lint-coverage gaps**
Evidence: #476→#478 (W605 tool-behavior delta); #461 (stale manifest);
dependency-review CVE gating.
- On toolchain/migration PRs: parity-check against the replaced tool (run the
  OLD checker), verify referenced manifests exist/valid, lock/arch closure for
  the real install target, and keep the tooling commit separable from mass
  autofix.

## 4. Positive controls — checks that must NEVER regress out of the prompt

These caught real latent bugs; every future prompt keeps them:
- Empty inputs (empty slice ⇒ whole suite silently re-runs — #477).
- Name/id collisions (artifact-name overwrite across shards — #477;
  modal-inner DOM ids not globally unique — #482 round 1).
- Tool-behavior deltas across a linter/formatter migration (#476) and
  AST-identity of mass autofix.
- Id→semantics mapping against the source of truth (job 202 =
  synchronous iptables, not a listener — #479).
- Where the change actually executes in CI vs the image (#480).
- Helper assumptions verified against the served template, not the intent
  (#482 round 2).
- Fork-local leakage: `git diff upstream/main <branch> -- <file>` before push.

## 5. Per-PR prompt body (instantiate with §1 findings)

> Review-gate for PR `<N>` on mimi-net/miminet (base main, head `<branch>`),
> files `<files>`, claimed goal: `<claim>`.
>
> Pre-gate history for these files: <paste §1 output — fix commits found, issue
> refs, cluster status>. Implication I am asking you to enforce: <derived rule>.
>
> Verify/critique (do not re-verify happy paths):
> 1. <probe derived from history>
> 2. <probe from taxonomy classes a-g that apply>
> 3. <positive-control checks relevant to this PR>
> 4. <specific "author did not check" targets — empty inputs, collisions,
>    exit-code/artifact behavior, predicate correctness against a real service>
>
> Deliver APPROVE / APPROVE-with-nits / REQUEST-CHANGES with must-fix vs
> non-blocking separated, each finding tied to a line. If you cannot PROVE an
> invariant the PR relies on, say so explicitly.

## 6. Changelog (why each prompt line exists)

- **v1 (2026-09-02)** — first canonical version, distilled from full-repo
  history mining. Evidence episodes behind the classes: grid-readiness race +
  misdiagnosis (#483 amend e7fa2f8→742d79a) → (a)/(e); accepted silent-CI
  nits still live (#477/#483) → (d); front e2e flake chain (#463→#482) →
  (f)/(b); DHCP/capture chain (#450/#464→#479) → (a)/(b); env divergence
  (#480, #462→#469, #474) → (c); linter/dependabot gaps (#476/#478, #461) →
  (g). Positive controls kept from the #47x-#48x gate records (empty-slice,
  artifact collision, W605, AST-identity, id→semantics, CI-vs-image, DOM-id
  uniqueness, fork-local diff).
