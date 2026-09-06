# ipmininet 1.3.0 — miminet upgrade-impact valuation (2026-09-06)

Analysis of the mimi-net/ipmininet **fork** v1.3.0 release (2026-09-06,
merged PRs #32–#50) against miminet's actual consumption. miminet pins the
fork at **v1.2.7** in `back/pyproject.toml` (`ipmininet @
git+https://github.com/mimi-net/ipmininet.git@v1.2.7`; `uv.lock` resolves rev
`058d4ea`). Read-only analysis; **no code changed** (per user: defer all,
prepare for improvements only).

## 1. What v1.3.0 changed (from release notes + code diff v1.2.7..v1.3.0)

- **FRRouting 7.5 → 10.7.1 with mgmtd-based per-node config** (#36). Installer
  now builds FRR 10.7.1 from source and generates configs through the mgmtd
  backend (FRR ≥ 9). **Requires re-provision** (`python -m ipmininet.install
  -af`) after upgrade or daemon startup checks fail.
- **ExaBGP 4.2.25 → 5.0.13 via pip** (#37, replaces apt).
- **OpenR daemon support removed** (EOL) (#35); installer modernized (PEP 668).
- **Ubuntu 26.04 container support** (#32, PCRE1 built from source).
- **Bugfix:** zebra `PrefixListEntry("any")` no longer crashes when route-map
  code reads its `.ge` field (#48).
- **Coverage gate 84 → 90** (blended TOTAL 92.24%, 278 passed) with scenario
  tests for previously ~0% modules (dnsmasq, DHCPRelay, IPOVSSwitch, ExaBGP
  attributes, link descriptions) (#47, #43).
- **Zero-tolerance duplicate-code gate** (`duplication_max` 51 → 0,
  `scripts/check-duplicates.sh`, pre-commit hook) (#49).
- **Test-suite re-architecture:** shared `run_ipnet`/`run_topology_scenario`/
  `assert_config_file`/`assert_all_paths` helpers replace hand-rolled
  scaffolding (test SLOC 5565 → 5348) (#49).
- **Ruff/lint modernization**, py3.12 idioms, PLR/PLC/TRY003 cleanups, named
  magic constants (#42, #44, #45, #46).
- `wait_until_capturing(intf_name, timeout, strict)` API **unchanged**
  (verified against both tags) — the strict/READY semantics miminet consumes
  (network.py `__captures_not_live`) still exist identically.
- **`ip -color=never` hardening** in the code paths ipmininet itself parses
  (`link.py` `ip address show`, `srv6.py`, `cli.py`) — upstream no longer
  relies on the env-level `NO_COLOR` for its own reads.
- `IPTopo` unknown-attribute now raises typed `UnknownTopologyAttributeError`
  (subclass of `AttributeError`) — backward compatible.
- `IPOVSSwitch`: "OVS kernel switch does not work in a namespace" raised
  earlier/cleaner — no behavioral change for miminet's host-netns usage.

## 2. What miminet actually consumes (verified on fork `main` d30a3f1)

`back/src` imports (see lens-B Appendix for the wider map):
- `ipmininet.ipnet.IPNet` — emulator.py, network.py, network_topology.py,
  net_utils/vlan.py, net_utils/vxlan.py, tests.
- `ipmininet.iptopo.IPTopo` — network_topology.py (subclass
  `MiminetTopology`).
- `ipmininet.ipswitch.IPSwitch`, `ipmininet.ipovs_switch.IPOVSSwitch` —
  network_topology.py (L2 switch + hub modes).
- `ipmininet.router.config.RouterConfig` — network_topology.py
  (`config=RouterConfig` on every `addRouter`).
- `ipmininet.host.config.dnsmasq.Dnsmasq` — jobs.py (dhcp_server job 203;
  generates config + `_wait_for_daemon_bind`).
- `NetworkCapture.wait_until_capturing(..., strict=True)` — network.py
  readiness polling (mimidump READY).
- `mininet` core + `dpkt` alongside.

**Critically: miminet NEVER registers a routing daemon.** Zero `addDaemon`/
`STATIC`/`StaticRoute`/`zebra`/`OSPF`/`BGP` call sites in `back/src`, and the
`back` Docker image installs no FRR. Router nodes are plain L3 kernel routers:
`RouterConfig` sets `net.ipv4.ip_forward` sysctls; static/host default routes
are applied via `ip route`/`route add default` shell commands (jobs.py,
network_topology.py:271/281/289). Therefore **the FRR 10.7.1 + mgmtd overhaul,
the ExaBGP pip move, and the OpenR removal do NOT affect miminet's emulation.**

## 3. Findings

- **F1 — v1.2.7 → v1.3.0 is a LOW-RISK, pure-pin bump for miminet.** The only
  consumed APIs that changed are backward-compatible (typed AttributeError,
  earlier OVS-namespace error), and the daemon ecosystem churn is irrelevant
  because miminet runs no daemons. The diff in `ipnet.py`/`link.py`/
  `ipswitch.py`/`ipovs_switch.py` touching capture start/stop was refactored
  into shared `start_captures`/`stop_captures` helpers (no behavior change for
  the miminet usage).
- **F2 — miminet's `NO_COLOR=1` workaround (emulator.py:27-30) STAYS.** The
  fork now hardens only the `ip` commands *ipmininet itself* parses
  (`-color=never`). miminet still shells its own `ip route get` reads
  (network.py:249) and job `ip` commands on PTYs, so env-level color
  suppression remains the cheap, correct guard. Optional later: narrow it to
  miminet-owned commands only; not worth a change now.
- **F3 — capture-restart/readiness and settle hacks are NOT superseded.**
  `wait_until_capturing(strict=True)` semantics are identical in 1.3.0; the
  mimidump ifup race miminet works around (network.py `__restart_captures`)
  lives in the **mimidump** repo (separate, pinned commit `854a3b0`), not in
  ipmininet. Bumping ipmininet does not change that.
- **F4 — no miminet code is *forced* for deletion by the upgrade.** Candidates
  that could be cleaned on a later feature batch (NOT this upgrade): the
  duplicated `web_network`/`web_network_shared` handlers and CWD-relative blob
  paths flagged in the Batch 12 architecture review (lens-B F4/F5) are
  independent of ipmininet.

## 4. Deferred task (unblock chain + aim)

**DT-ipmininet-1.3.0 — pin bump to v1.3.0 and re-green the back suite.**
- Aim: keep the emulation fork current so future back/emulation features and
  bug fixes land on the supported release (its CI now gates at 90% coverage).
- Unblock chain:
  1. `back/pyproject.toml` pin `v1.2.7` → `v1.3.0`, `uv lock` (single-lock
     workspace; expect only the ipmininet source rev to change).
  2. **Rootless full back-suite run** (`scripts/back-test.sh` or the batch-11
     recipe: `pytest` from `back/tests`, `PYTHONPATH=../src`, rootless) — this
     is the deciding gate; emulation tests exercise IPNet/IPSwitch/OVS/dnsmasq
     paths.
  3. Confirm no test `test_json/*.json` depends on a routing daemon (verified
     none register one today — re-check nothing new was added).
  4. If green: small upstream PR (pin + lock only), merge, re-sync fork `main`.
  5. If a flake/regression appears: capture logs, decide bump-vs-hold; do NOT
     silently revert.
- Not settled by this analysis: exact runtime behavior of v1.3.0
  `link.py`/`ipnet.py` startup under miminet's IPv4-only, host-netns, OVS
  usage — only an actual rootless run proves it (per §3 deferral policy).

## 5. Reuse ideas from the fork's PR history (feed the Batch 12 front-85% plan)

- **Coverage-gate-at-baseline−1** (#31/#41/#47): fork enforces
  `fail_under` set just under the measured whole-suite baseline; scenario
  tests added for ~0% modules before the gate was raised. Mirrors the back
  precedent (76.15 → gate 75) — the front API/grading-engine coverage job
  (lens-C F3) should do exactly this.
- **Zero-duplicate-code gate** (#49) — `scripts/check-duplicates.sh` +
  pre-commit; cheap to mirror on miminet if duplication (e.g.
  `web_network`/`web_network_shared`) matters.
- **Shared test-scaffold re-architecture** (#49): central `run_*`/`assert_*`
  helpers; matches the back_test 3-shard slice cleanup philosophy.
- **Polling discipline** (#24/#26/#40/#38): poll server-visible state, never
  fixed sleeps — miminet's `__wait_until_ready` already embodies this; keep
  extending the pattern.
- **`ip -color=never` on parsed commands** as the robust way to defeat
  iproute2 colorization on PTYs (alternative to env `NO_COLOR`).

## 6. Files/reference

- fork: https://github.com/mimi-net/ipmininet (default `master`); release
  notes for v1.2.5…v1.3.0; PRs #1–#50.
- mimidump (capture engine): https://github.com/mimi-net/mimidump (no
  releases; miminet pins commit `854a3b0` in `back/Dockerfile`).
- This valuation is Tier-2 fodder; the actual bump is a Tier-3 upstream PR
  once unblocked.
