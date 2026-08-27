# Emulation benchmark — findings (wip/bench-emulation)

Method: `scripts/bench-emulation.sh` runs `back/bench/bench.py` inside the
boxed emulation container (own netns, `miminet-back:test`), driving each
network through the real emulation path with phase timing, process-tree peak
RSS and ovs-vswitchd RSS deltas.

Environment: native Linux host, rootless podman, container netns. Data in
`.bench/*.json`. Branch `wip/bench-emulation`; nothing upstreamed.

## Results: before vs after (full sweep, 1 repeat)

| metric | baseline | after fixes |
|---|---|---|
| net_start avg | ~2.10 s | **0.18 s** (IPv6 DAD poll removed) |
| link_down | flaky 7 s / 90 s timeout | stable ~5.7 s |
| networks emulated | 20/21 (+90 s flake timeout) | **21/21**, no readiness timeouts |
| full-suite pass | 27/27 (baseline) | **27/27** |
| full-suite wall | 330 s | **296 s** |
| TOTAL sweep wall | ~140 s (+90 s timeout) | **~116 s** |

Representative wall times: tcp 5.2→3.2 s, link_down 7.2→5.7 s, router 5.1→2.9 s,
vxlan_with_nat 5.8→3.5 s, switch_and_hub 4.4→2.9 s. STP networks unchanged
(~8–9 s) — convergence time is inherent, not a bug.

## Example networks benchmark (the /examples page) — settle focus

The 13 web-example networks are NOT in the repo (only in the deployed DB), but
each is served publicly at `/web_network_shared?guid=…` with the full JSON
embedded (`var nodes` / `const edges` / `var jobs`). Reproducibly fetched by
`scripts/fetch-example-networks.py` into `back/bench/examples/` (13
`*_network.json`, all schema-valid).

Baseline (blind 2.0 s settle): total 66.94 s. Settle is 16–91 % of wall —
**~60–70 % on typical simple networks** (switch_and_hub 2.03/2.80 s, router
2.03/2.86 s, tcp 2.00/3.22 s, vlan 2.14/3.47 s, vxlan 2.25/3.40 s).

Adaptive settle (1.2 s floor) + `MIMINET_DISABLE_IPV6=1`: every one of the 13
faster; settle 2.0 → ~1.2 s (zero cap-hits); **total 66.94 → 57.59 s (−14 %)**,
**simple networks (<4 s) −24 %** (27.5 → 21.0 s). Per-network saves 0.5–0.85 s.

The aggressive 0.5 s floor saved −26 % total but is **unsafe**: 3/27 tests
failed (dhcp_one_host, icmp_host_unreachable, icmp_network_unavailable) — their
async replies (DHCP ACK / ICMP error) arrive 0.6–1.1 s after a quiet gap, so
the floor must be ≥ ~1.2 s.

## Hotspot ranking (post-fix)

1. **pre-teardown settle (2.0 s)** — tail-capture window for async replies;
   now adaptive (1.2 s floor + quiet detection), see "Fixes" §3.
2. **readiness_wait** — STP convergence only (~4–6 s); VXLAN cold start ~2.5 s.
3. **jobs** — DHCP ~3–5 s; TCP send ~1 s (wait-bound).
4. pcap parse ~0.01 s (NOT a hotspot).
5. CPU 0.1–1.3 s vs wall 3–15 s → wait-bound, not CPU-bound.

## Memory footprint

- flat 2-host ~67 MiB · STP 8-switch ~245 MiB · VXLAN+NAT 4-router ~172 MiB.
- ovs-vswitchd 14→57 MiB with STP, does not shrink on teardown (retention).
- Concurrency 4 of heaviest ≈ 1 GiB peak → fits a 16 GiB host.

## Fixes applied on this branch

### 1. link_down flake — FIXED (`__restart_captures`)
- Root cause: mimidump starts per-interface during link setup and races
  interface startup; `pcap_activate` → `PCAP_ERROR_IFACE_NOT_UP`, it blocks in
  `wait_interface_up` (up to 100 s) missing the UP netlink event, then exits
  leaving only the INOUT file. The readiness gate then timed out at 90 s.
- Fix: if an outbound capture file is still missing after
  `MIMINET_CAPTURE_RESTART_GRACE` (default 2.0 s), kill the stuck mimidump and
  re-start that capture. Safe: the gate runs before jobs, so no host traffic
  is lost. Result: no more 90 s timeouts; flaky runs self-heal in ~2 s.

### 2. net_start ~2 s — FIXED (IPv6 DAD poll skipped)
- cProfile proved net_start was ~entirely `time.sleep(0.5)` × ~4: ipmininet's
  `IPNode.start()` unconditionally polls `ip -6 addr show tentative` until IPv6
  DAD finishes, even on IPv4-only networks (`use_v6=False`). It is a race —
  measured 0.04 s to 10.6 s depending on kernel DAD timing.
- Fix: `MiminetTopology` now passes `use_v6=False` to hosts. The gate itself
  (skip the DAD poll when `node.use_v6` is False) is **upstream in
  mimi-net/ipmininet** — it was prototyped in `network.py` as a
  `ProcessHelper.call` shim during the experiments, but the shim is NOT in the
  product; it lands with the ipmininet dependency bump. Switches bypass
  IPNode (no DAD).
- Side effect: fast net_start exposed the mimidump race more often; the
  capture-restart (fix 1) absorbs it at ~2 s.

### 3. pre-teardown settle — ADAPTIVE (1.2 s floor, default)
- The blind 2.0 s sleep is tail-capture time for async replies (DHCP ACK,
  ICMP unreachable, VXLAN/NAT propagation). Removing it → 14/27 tests fail;
  1.0 s → 3/27; 1.5 s → 1/27.
- Quiet-detection needs genuinely quiet counters, which the continuous IPv6
  flood (see §4) prevents. With `MIMINET_DISABLE_IPV6=1` the flood is gone and
  `__settle()` polls this emulation's own OVS ports (psutil `net_io_counters`,
  no subprocess), breaking after 3 quiet polls (3 × 0.1 s) once elapsed ≥
  `MIMINET_SETTLE_MIN` (default 1.2 s), capped at 2.0 s.
- Floor 1.2 s is required by the latest async tails (0.6–1.1 s); 27/27 with
  the full suite. Without disable-ipv6 the flood keeps counters busy and the
  settle degrades to the 2.0 s cap (= old behavior, no regression).
- Knobs: `MIMINET_SETTLE_MIN` (floor), `MIMINET_STOP_SLEEP` (old fixed
  override). Max/poll/quiet are hardcoded (2.0 s / 0.1 s / 3). The benchmark
  measures `net.stop()` externally as `stop_time` and reads
  `settle_hit_cap` to tell early breaks from cap-bound ones.

## IPv6 multicast flood — root cause + fix (`MIMINET_DISABLE_IPV6`)
- Every emulated interface carries a *continuous* IPv6 flood: MLDv2 multicast
  listener reports + Duplicate-Address-Detection neighbor solicitations
  (`tcpdump`: `ff02::16` MLDv2, `ff02::1:ffXX` NS). Hubs flood a host's own
  DAD NS back at it, so DAD never completes and probes repeat forever.
- The product already filters it out of captures (`not igmp and not ip6`) — it
  never reaches the animation. But it keeps every OVS port busy, polluting
  psutil counters (defeats quiet-detection) and burning CPU.
- `use_v6=False` does NOT stop it (ipmininet only skips global-address config;
  the kernel IPv6 stack stays up). `net.ipv6.conf.*.disable_ipv6=1` per
  interface removes it, but needs a writable `/proc/sys/net` — **the bench
  container must run `--privileged`** (production celery already does:
  `back/docker-compose.yml` `privileged: true`). Implemented in
  `MiminetNetwork.__disable_ipv6()`, gated on `MIMINET_DISABLE_IPV6=1`
  (**default on** since the perf/emulation-time change; opt out with `=0`).
  Cost ~10–50 ms/emulation. Safe: Miminet is IPv4-only.

## Cleanup / shutdown cost research

| phase | cost | needed in ephemeral container? |
|---|---|---|
| settle (pre-teardown) | 1.2–2.0 s | yes (tail-capture arrival) |
| `super().stop()` teardown | 0.08–0.87 s | NO — netns/OVS vanish with container |
| `clean_services` | ~0.01 s | no |
| `mn -c` (harness/bench) | **1.53 s** | NO — resets shared host state only |
| container create | ~0.3 s | amortized if pooled |
| OVS init | ~0.3 s | amortized if pooled |
| Python emulator-stack import | ~1.0 s | amortized if pooled |

Conclusions:
- We currently pay teardown (~0.1–0.9 s) + `mn -c` (1.53 s) that an ephemeral
  per-emulation container would not need → ~1.6–2.4 s/emulation saved by
  skipping teardown before container death (only SIGINT-flush mimidump + read
  pcaps required; mimidump flushes on signal).
- The settle is now the adaptive window above; the async-tail floor (~1.2 s) is
  the remaining packet-arrival cost, only addressable by redesigning
  tail-capture.
- Warmup: cold per-task box ≈ 1.6 s (0.3 create + 0.3 OVS + 1.0 python import).
  A pre-warmed pool (idle boxes, OVS up, stack pre-imported) removes it; the
  current shared celery box already amortizes warmup.

## Residual flakiness
`vlan_with_vxlan` intermittently fails a raw (no-retry) run with a packet
mismatch (observed at settle 1.0/1.5 and grace 1.0). Pre-existing; the product
absorbs it via the 4x retry in `tasks.run_miminet`. Likely a late-start capture
missing early packets — candidate for the upstream capture-start fix.
