# Emulation benchmark — session journal

Branches: `wip/bench-emulation` (all work local, nothing upstreamed yet).
Findings live in `.bench/BENCH_FINDINGS.md`; raw data in `.bench/*.json`.

## Session log

### 2026-08-27 — session 1: baseline measurement
- Built `back/bench/bench.py` + `scripts/bench-emulation.sh` (boxed container,
  own netns, `miminet-back:test`), added inert `timing`/`phase_times` hook to
  `MiminetNetwork`, added `BACK_ENGINE` override to `scripts/lib-back-env.sh`.
- E1 full sweep (21 networks, 1 rep): 20 passed, `link_down` flaked.
- E2/E3: 3 reps of tcp (~67 MiB, 5.2 s), rstp_four (~245 MiB, 9.4 s),
  vxlan_with_nat (~171 MiB, 5.8 s).
- Key hotspots: fixed `sleep(2)` in stop() (~30% wall), net_start (~2.0 s),
  pcap parse ~0.01 s (NOT a hotspot). CPU-bound: no (wait-bound).

### 2026-08-27 — session 2: fixes + re-bench + net_start research
- **link_down flake FIXED** (`MiminetNetwork.__restart_captures`): mimidump
  races interface startup (`wait_interface_up` up to 100 s), leaving no
  outbound capture → 90 s readiness timeout. Restart stuck captures after
  `MIMINET_CAPTURE_RESTART_GRACE` (default 2.0 s). Stress: all pass, self-heal
  ~2 s. Full suite 27/27.
- **Pre-teardown settle researched**: NOT removable in shared-box model
  (0 → 14/27 fail; 1.0 → 3/27; 1.5 → 1/27; 2.0 → reliable). Kept default 2.0 s
  behind `MIMINET_STOP_SLEEP` env knob.
- **net_start FIXED**: cProfile → it was ipmininet IPv6 DAD poll
  (`ip -6 addr show tentative`, sleep 0.5 × ~4, race 0.04–10.6 s). Prototyped
  a local `ProcessHelper.call` shim (short-circuit when use_v6=False);
  MiminetTopology passes use_v6=False to hosts. net_start 2.1 → 0.18 s avg.
  Proper fix moved upstream (mimi-net/ipmininet, alongside PR #11 → 1.2.6) —
  the shim is NOT in the product; it lands with the ipmininet bump.
- Side effect: fast net_start exposed mimidump race more; capture-restart
  absorbs it (~2 s). Grace tuned 8→2 s (27/27 at 2 s; 1 s flaked once).
- **Cleanup/warmup research done**: teardown (~0.1–0.9 s) + mn -c (1.53 s) are
  unnecessary in an ephemeral per-emulation container (save ~1.6–2.4 s/emu);
  2.0 s settle is the floor; warm pool (OVS + pre-imported stack) removes
  ~1.6 s/task cold start. See BENCH_FINDINGS.md.
- Final: full suite 27/27 (296 s, was 330 s), sweep 21/21 (avg net_start
  0.18 s). Residual flake: vlan_with_vxlan intermittent (pre-existing, masked
  by product retry).

### 2026-08-27 — session 3: examples benchmark + adaptive settle + IPv6 flood
- **Example networks fetched**: the 13 `/examples` networks are only in the
  deployed DB, but each is served publicly at `/web_network_shared?guid=…`
  with the full JSON embedded. Added `scripts/fetch-example-networks.py`
  → `back/bench/examples/*_network.json` (13, all schema-valid).
- **Baseline on examples** (`.bench/examples_blind.json`): 66.94 s total;
  blind 2.0 s settle is 16–91 % of wall, ~60–70 % on typical simple networks.
- **Discovery: continuous IPv6 flood.** psutil counters NEVER go quiet — every
  interface carries a continuous MLDv2 + DAD neighbor-solicitation flood
  (hubs reflect a host's own DAD NS back at it → DAD loops). Filtered from
  captures (`not ip6`), but pollutes counters + CPU. `use_v6=False` doesn't
  stop it; per-interface `disable_ipv6=1` does, but `/proc/sys/net` is
  read-only in a non-privileged container. Made the podman harness path
  `--privileged` (matches production's `privileged: true`).
- **Adaptive settle implemented** (`MiminetNetwork.__settle`, psutil-only, no
  subprocess in the poll loop): poll own OVS ports, break after N quiet polls
  once ≥ floor. Modes fixed|adaptive|debug; knobs MIN/MAX/POLL/QUIET_POLLS/
  DEBUG_DIR; `settle_wait` + `settle_hit_cap` phases.
- **0.5 s floor unsafe**: 3/27 failed (dhcp_one_host, icmp_host_unreachable,
  icmp_network_unavailable) — async replies (DHCP ACK / ICMP error) arrive
  0.6–1.1 s after a quiet gap. **1.2 s floor + disable-ipv6 → 27/27**, and
  27/27 with pure defaults too.
- **A/B on examples** (`.bench/examples_adaptive_safe.json`): settle 2.0 →
  ~1.2 s (zero cap-hits), total 66.94 → 57.59 s (**−14 %**), simple networks
  (<4 s) **−24 %** (27.5 → 21.0 s). Every example faster (+0.5–0.85 s).
- Defaults: adaptive settle with 1.2 s floor (safe; degrades to 2.0 s cap if
  IPv6 stays on); `MIMINET_DISABLE_IPV6` stays default-off (needs privileged).

### NEXT (session 4, candidates)
- Ship decision: `MIMINET_DISABLE_IPV6` default-on in production? (IPv4-only
  product; kills noise/CPU.) Needs a wider network regression first.
- Floor tuning on more diverse networks (1.2 s margin over the 1.11 s observed
  tail is thin) — validate before productizing as default.
- Upstream ipmininet: gate DAD on use_v6 + start captures only when the
  interface is up.
- Concurrency sweep (Batch 2) now that net_start is cheap.
