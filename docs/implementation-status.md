# Implementation checkpoint

Updated: 2026-10-30 (Asia/Ho_Chi_Minh).

## Scope and reviewed snapshot

Initial Git baseline: `dcb897011f31231acc2b68d0a563247218d3630f`. Initial workspace contained the reviewed 14-page PDF/307-line plan and no application source. Original PDF and plan remain unchanged. `.DS_Store`, native runtime binaries, caches and generated config/evidence are excluded from source review.

Current slice is the **local software preparation for M0-M2**, not completion of hardware or VPN gates. One Hikvision camera, H.264 720p/25 fps, no audio; viewers in Laos and Vietnam. Future path: camera -> ER605/WireGuard -> Singapore MediaMTX -> browser WebRTC; Fastify/Next.js/PostgreSQL are gated on real POC evidence.

Maintained source/config/docs read: AGENTS.md, plan, README, Makefile, `.gitignore`, all scripts/tests, MediaMTX/Docker/VPN templates and all docs. Six newly added user-owned device photos in `images/` were inspected for model/port/PoE labels, preserved without modification and excluded from the implementation commit. Serial/MAC/device keys are not transcribed.

Final CLI source SHA256: `08c8f4e2fd3991ac1818ecfcb54c03e2340a48adde2794d4c9eee31f30cea635`.

## Current project map

- `scripts/poc.py`: Python 3.9+ stdlib CLI, explicit SHA256-verified MediaMTX installer, prerequisite doctor, private config generation, redacted native process lifecycle, bounded FFprobe invocation and offline codec analysis. CLI help is the entry point.
- `tests/test_poc.py`: unit/regression tests for malformed/incomplete samples, codec/audio/B-frame checks, private paths/permissions/symlinks, archive validation, redaction, subprocess errors/timeouts and silent-child cleanup.
- `infra/mediamtx`: intentionally unusable placeholder source JSON and local reference config. Generated native configs bind loopback and disable unused protocols including MoQ; camera live path has read-only permissions, synthetic publisher path is explicit and separate.
- `infra/docker`: pinned v1.21.3 local Compose template, separate container-listener render target with host ports restricted to loopback. Not executed on this host.
- `infra/vpn`: manual ER605/VPS runbook and placeholder peer config; no router, route, firewall or WAN automation executed.
- `docs`: observed device labels, physical wiring, M0-M2 checklist and latency measurement/report procedure.

No production dependencies, DB schema, public authentication contract, paid services or production endpoint were introduced. MediaMTX native is a local POC tool. Input camera credentials stay in private JSON; generated configs/reports are confined to ignored `.local`/`.runtime`, secret files are mode 0600. The initial POC is not production RBAC/authentication.

## Implementation route and permission evidence

Selected default Sonnet slug was absent from authenticated catalog, not quota exhausted. User then explicitly approved `gemini-4-argon-high`; doctor confirmed account route and AI credit overages disabled. Worker task `camera-m0-m2-20261030` used an isolated worktree based on the baseline above.

Run 1 hit the bounded 600-second timeout with partial configuration/docs. Run 2 wrote source/tests/README but failed bridge acceptance: automatic review denied `python3 -m compileall -q scripts tests` because the headless worker could not request command permission. Worker logs/packet/partial work are preserved outside the repo. No permission settings or bypass flags were changed, and the bridge task is not marked accepted.

The user explicitly authorized Codex to finish the remaining changes and execute local unittest/compileall/CLI/MediaMTX smoke checks. Codex copied only in-scope worker outputs into the requested project, independently reviewed them, reproduced defects with failing regression tests, then fixed bounded runtime, symlink confinement, private input modes, 60-second minimum sample enforcement, legitimate admin username support and failure-exit/redaction behavior.

## Actual verification on macOS arm64

Host: Python 3.9.6, Git 2.55.0. No Docker/ffprobe/ffmpeg/shellcheck available on PATH; no system packages installed.

| Command or scenario | Actual result |
|---|---|
| Initial expanded regression suite | Failed for intended reasons: silent child exceeded deadline, symlink roots escaped confinement, source mode unchecked, short/NaN/Inf durations mishandled, admin username refused |
| `make check` | PASS: compileall, CLI help and **22 unittest tests**, 1.830s on final source |
| `python3 scripts/poc.py install-mediamtx` | PASS: official Darwin arm64 archive hash verified, pinned v1.21.3 installed under ignored `.local` |
| Archive SHA256 | `bc1a0762fd18ffb413bcd81dcb9a072ac159fbd1f27e79ac6f14598aaac5ed3f` |
| `python3 scripts/poc.py smoke` | PASS: actual v1.21.3 binary, generated config parses, built-in player HTTP/Control API/RTSP sockets respond, owned process cleaned up |
| `python3 scripts/poc.py doctor` | Correctly reports `degraded`: MediaMTX ready, ffprobe/ffmpeg/Docker/shellcheck missing, camera source absent |
| `configure --synthetic-only` then native `run --duration 180` | Generated 0600 config starts actual MediaMTX, camera source remains null |
| Real browser UI, IAB on Mac | Opened `http://127.0.0.1:8889/synthetic/`; video element renders and shows `Error: stream not found, retrying in some seconds`, expected with no publisher. No actual media decode or camera claim |
| Actual process sockets via `lsof` | Only 127.0.0.1 TCP 8554/8889/9997 and UDP 8189; no MoQ/RTMP/HLS/SRT/metrics/playback listeners |
| Native process shutdown | Ctrl-C returned exit 0 and stopped owned media process; temporary smoke configs cleaned up |
| `git diff --check` | PASS after whitespace fix |

The generated synthetic config remains available at `.local/mediamtx.poc.yml`, deliberately without a camera source. Runtime was stopped after verification. This is startup/offline-error UI evidence only, not a live viewing acceptance test.

## Milestone gates

| Gate | Status | Remaining evidence |
|---|---|---|
| M0 label inventory | Partial: model/ports visible in photos | Firmware, power/PoE budget, backups and actual LAN access |
| Local software POC | Verified within the scope above | Docker path remains unexecuted |
| M1 camera/codec/latency | Pending | Device connection, real FFprobe sample, browser decode, optical latency |
| M2 VPN | Pending | VPS/access, actual ER605 tunnel, RTSP through VPN, WAN/reboot recovery |
| M3-M6 | Not started | Prerequisite gates and production requirements |

No real RTSP source, optical latency, 200-peer load, mobile browser decode, recording, VPN or deployment has been verified. Next physical action is the wiring sequence in `hardware-setup.md`, followed by identifying actual IP/firmware and preparing private camera credentials locally. FFprobe must be made available before live codec probing. Do not send secrets in chat.
