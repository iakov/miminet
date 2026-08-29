# Miminet — infra & perf roadmap (research log)

Durable home for findings and deferred directions. Not product material;
kept on `wip/bench-emulation` (gitignored `.bench/`).

## 1. Flaky-test root cause — capture readiness (ACTIONED)

Known residual flake: `vlan_with_vxlan` intermittently fails a raw (no-retry)
run with a packet mismatch. Product's 4x retry in `tasks.run_miminet` only
covers empty / control-frame-only animations (`_has_meaningful_packets`), not
packet mismatches.

Root cause chain:
- Captures are spawned per interface once the interface is UP (ipmininet PR
  #12). `mimidump.c` `pcap_dump_open` creates the pcap file *after* the handle
  is activated, so "file exists" is a proxy that is still too early to prove
  the capture loop is live for both captors.
- miminet's `__wait_until_ready` polls `capture_out_path(...)` existence; a
  job's first packet can race the attach.

Actioned upstream (2026-08-29):
- `mimi-net/mimidump#11` — emit a readiness sentinel once both captors are live.
- `mimi-net/ipmininet#14` — expose `NetworkCapture.wait_until_capturing(intf, timeout)`.
- Then: miminet `__wait_until_ready` polls it (SSOT), `__restart_captures`
  becomes a safety net; NO retry-on-mismatch code was added to miminet.

## 2. ipmininet 1.2.5 -> master analysis (transferability)

| change | what it does | useful for us? | effort/risk |
|---|---|---|---|
| PR #12 DAD gate (`__router.py`) | skip IPv6 DAD poll when `use_v6=False` | YES — `net_start` 2s->0.2s; we already ship `use_v6=False` (hosts+routers) | gated on 1.2.6 |
| PR #12 capture-start on interface-up (`link.py`) | only start captures when iface is UP | YES — fixes our `link_down`/`vlan_with_vxlan` flake family; `__restart_captures` -> safety net | gated on 1.2.6 |
| PR #11 uv + pyproject + .python-version + Containerfile | modern toolchain, rootless container | reference for a future miminet uv migration; validates our `.python-version` SSOT (#455) | defer |
| `run-tests-parallel.sh` + `py-unshare.sh` | pytest-xdist, each worker in `unshare --mount --pid --net --uts --fork --mount-proc` + tmpfs /tmp | YES — parallel isolated back suite; our 27-test emulation suite is the CI long pole | medium; pilot first |
| `test.yaml` vs `heavy-test.yaml` | fast/PR vs full (master + workflow_dispatch) | YES — move `full_test` (6m47s selenium e2e) off every PR | low |
| `ci-save-deps.sh` / `ci-restore-deps.sh` + actions/cache | cache compiled deps keyed on OS+lockfile | YES — shave ~1-2 min/run from `back_test` apt+pip install | low |
| `run-tests-local.sh` + `require_root` marker | rootless local test split | maybe — our harness is container-based already (#451) | low |
| PEP 668 (`PIP_BREAK_SYSTEM_PACKAGES=1`) | ubuntu 24.04 system pip | already in the planned back/Dockerfile (pr/infra) | - |

## 3. Reuse plan (ipmininet -> miminet, SSOT-first)

| artifact | reuse in miminet | improvement needed in ipmininet |
|---|---|---|
| `NetworkCapture.wait_until_capturing` (#14) | `__wait_until_ready` polls it; drop file-proxy | deliberate API (per-intf, timeout, bool) |
| `scripts/py-unshare.sh` + `run-tests-parallel.sh` | parallel isolated back suite (CI + local) | make `py-unshare.sh` configurable (env: PYTHON, workdir, extra setup); document reuse contract in header |
| `scripts/ci-save-deps.sh` / `ci-restore-deps.sh` | deps caching in `back_test` | short usage + key-derivation note |
| `run-tests-local.sh` + `require_root` | rootless local back harness (optional) | document the marker + split |
| `test.yaml`/`heavy-test.yaml` split + concurrency | `full_test` -> master/manual/nightly | keep as reference implementation |

Principle: less code, more reuse — fix/API lives upstream (ipmininet/mimidump
as SSOT), miminet consumes it.

## 4. Deferred directions (status)

- [ ] ubuntu:24.04 + Python 3.12 + ipmininet `1.2.6` (draft tag; blocked) — seed
      `pr/infra`; delivers `net_start` 2s->0.2s + capture-start reliability.
- [ ] Parallel isolated back suite (xdist + unshare) — pilot: stp/vxlan/link_down
      in parallel; worker count by memory ceiling (bench: 4x heaviest ~1 GiB).
- [ ] CI split: `full_test` off every PR (master + workflow_dispatch + nightly).
- [ ] Compiled-deps caching in `back_test`.
- [ ] Nightly full-emulation run (flake signal).
- [ ] GitHub Actions major bumps (checkout v7, setup-python v7, buildx v4,
      upload-artifact v7, dependency-review v5) — drafted in `pr/infra`.
- [ ] uv + ruff adoption (mirror ipmininet).
- [ ] Bench-harness upstreaming (`back/bench`, `scripts/bench-emulation.sh`,
      examples fetcher) — candidate maintainer tool PR.
- [ ] Frontend quick wins: #404 JS TypeError, #357 VxLAN Save button, #431
      animation speed.
- [ ] wip/bench-emulation -> rebase onto main periodically; keep `BACK_ENGINE`
      override (dropped by rebase; re-added in `819ddd9`).

## 5. Notes

- Local podman harness needs `BACK_ENGINE=podman` (docker daemon reachable but
  image-less). Trimmed product `lib-back-env.sh` drops the override; the wip
  bench branch keeps it.
- `.bench/` is gitignored (`.*`); force-add on the wip branch.
- Suite baseline (pure defaults, post #452/#453): 27/27, ~242s; bench settle
  ~1.2s (hit_cap=False), disable_ipv6 0.04s, net_start ~0.2s (only with the
  ipmininet DAD gate baked in locally).
