# DEV.ONE Secure Live

## Scope and gates

- Follow `KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md`. Current slice: M0-M2 preparation and local MediaMTX POC only. Do not build production website/auth/DB until the camera-to-server network gate passes.
- One Hikvision camera, H.264 720p/25 fps, no audio, viewers in Laos and Vietnam. Latency target: p95 <= 1,000 ms, aiming for p50 <= 500 ms, measured glass-to-glass. Synthetic media does not prove camera latency.
- No Mini PC/NUC/Edge Agent at the camera site. Preserve PDF and original plan.
- Router firmware, WAN changes, resets, external deployment and new infrastructure costs require explicit authority. Do not run router or firewall mutation commands automatically.

## Code and secrets

- Prefer Python 3.9+ standard library for the POC tooling. Do not add third-party runtime packages without reviewing the need.
- Native macOS MediaMTX is the local POC route; provide a separately documented Linux/Docker route. Pin versions and verify downloaded archive hashes. Never auto-install system tools.
- Keep camera credentials, RTSP URLs, VPN keys and media tokens out of tracked files, command output and shared evidence. Store runtime configuration in ignored, private files. Do not dump process environments or raw ffprobe stderr.
- POC listeners bind loopback by default; disable unused protocols. The POC is not production authentication. LAN/public exposure must be an explicit, separately reviewed configuration.
- Use bounded subprocess calls, validated inputs, explicit exit codes and actionable redacted errors. Do not interpolate untrusted values into shell commands.

## Verification and reporting

- Add meaningful tests for config validation, credential redaction, probe interpretation, subprocess failures and timeouts. Never soften failures to claim a pass.
- Record exact commands, runtime versions and actual results in `docs/implementation-status.md`. Mark missing hardware/network measurements as pending, not successful.
- Required local checks: `make check` (compileall, CLI help, unittest) and `python3 scripts/poc.py smoke` with the pinned native binary. `doctor` reports prerequisites without installing them. See README and the checkpoint for verified results and missing tools.
- Real camera RTSP, router/WireGuard recovery, glass-to-glass latency, mobile browsers and 200-peer load each need independent evidence.

