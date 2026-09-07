# Test cost & duplication survey

Batch 16 follow-up: where CI test time really goes, and whether any smaller
test cases duplicate big tests' coverage to the point of being removable.

Read `00-survey.md` for the data tables and analysis.

TL;DR:
- Coverage subsumption is the wrong deletion criterion: small tests are cheap
  (~0.1-3s), the expensive ones are a handful of big flow/emulation tests
  (test_job_limit 49s, test_job_edit 29s, test_ipip_gre 21s; back shard 2's 21
  emulation scenarios = the whole back time). Removing small tests saves
  seconds and loses the failure-localizing regression layer.
- Real levers: e2e infra boot (~107s/shard) > big flow tests > everything else.
- Found one safe maintenance dedup: 3 copy-pasted blacklist matrices in
  test_user_options_input.py.

Status: survey only. No test changes made. Deferred: per-test coverage
attribution spike as the gate for any future coverage-subsumption deletion.

Update (2026-09-08, merged-coverage validation): the cross-lane merge ran
against real CI artifacts and confirms the survey's premise — the browser-free
front slice understates modules that only the (uninstrumented) e2e suite
exercises (configurators.py 26%, miminet_admin.py 28%, app.py 60%) while
back/src is 93.1% merged with the gap at emulator.py (84%), exactly where the
900s-timeout flakes live. Numbers and branch state in AGENT_RUNBOOK Batch 16.
