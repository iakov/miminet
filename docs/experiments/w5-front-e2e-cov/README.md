# W5 — front/src e2e branch-coverage measurement (2026-09-04)

Fork-temporary, **NEVER-merged** experiment that measured what the Selenium e2e
suite exercises of `front/src`. Executed once, torn down, then recovered from
the dangling commit `62fd169` and archived here (Batch 10 close-out lesson).

## Measured result (run `33845892656`, Full test, fork, all green)
- **Branch-aware weighted cover: 27%** (statements 33.2% = 1596/4811; branches
  7.7% = 119/1548; 36 of 39 `front/src` files executed).
- Low by design: e2e drives only the editor/emulation paths. Worst-executed big
  file: `front/src/quiz/service/check_host_service.py` (439 stmts @ 2%);
  `quiz/` modules are barely hit.
- `coverage.json` from the run: download artifact `front-cov-report` from run
  33845892656 while it is still retained (90 days).

## Mechanism (what was in commit `62fd169`)
- `coverage==7.16.0` pip-installed into the app venv at image build. coverage
  7.16 ships `a1_coverage.pth`, which auto-starts a tracer in every interpreter
  using `/app/.venv` when `COVERAGE_PROCESS_START` points at a config file.
- `coverage.rc` (baked to `/app/.coveragerc`):
  `source=/app`, `branch=true`, `parallel=true`, `sigterm=true`,
  `data_file=/app/.covout/.coverage`.
- uwsgi workers (5) flush on SIGTERM **only** with `sigterm=true` (proven both
  ways against real uwsgi 2.0.31).
- celery prefork children exit via `os._exit` → never flush; `cov_flush.py`
  (imported via `w5_cov.pth`, gated on `W5_COV_FLUSH=1`) registers an at-fork
  child hook that starts a daemon thread calling `coverage.save()` every 10s.
- `.covout` bind-mounted to `front/.tmp/covout`; per-shard upload with
  `include-hidden-files: true`; a combine job remaps container `/app` →
  `${GITHUB_WORKSPACE}/front/src` via `[paths]`.
- `full_test.yml` on the temp branch was trimmed to `workflow_dispatch` so the
  ONE run was manual; collateral fork runs from the branch push (back Pytest,
  auth) were cancelled.

## Files in this folder
- `cov_flush.py` — verbatim from `62fd169:front/w5/cov_flush.py` (byte-identical).
- `coverage.rc` — verbatim from `62fd169:front/w5/coverage.rc`.
- `w5_cov.pth` — verbatim from `62fd169:front/w5/w5_cov.pth`.
- `full_test.yml.w5-branch` — the full edited workflow as committed.
- `w5-full-diff.patch` — `git diff 62fd169^ 62fd169 -- full_test.yml front/Dockerfile front/docker-compose.yml`.
- See Batch 10 runbook entry for the prose recipe + validation evidence.

## Residual risks (if ever re-run)
1. `.pth` activation in the real image was the largest risk (validated on an
   equivalent py3.12 venv, not the exact image); the flush-step `find` guard
   fails red if it does not fire.
2. upload-artifact glob of hidden files under hidden `front/.tmp` (pattern
   proven in W4a #489).
3. Tracing overhead (saver threads) could flake the timing-sensitive suite.

## One-shot re-run steps
```
git -C /home/me/projects/miminet push origin \
    /home/me/projects/miminet/.worktrees/<wt>:refs/heads/w5-front-e2e-cov
gh workflow run full_test.yml --repo iakov/miminet --ref w5-front-e2e-cov
```
then cancel collateral fork runs; extract `%` from the `Front coverage report`
job log or the `front-cov-report` artifact. Cross-check refs: branch
`experiments/w5-front-e2e-cov` and tag `w5/front-e2e-cov-2026-09-04` point at
`62fd169`.
