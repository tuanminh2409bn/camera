# DEV.ONE Secure Live

## Active handoff: Windows, 2026-11-01

- The user ended all testing on Mac mini and authorized cleanup plus publication to `https://github.com/tuanminh2409bn/camera`. Keep POC source/tests, the original PDF/plan and user photos; delete local runtime, downloads, private credentials and reports. Keep Wi-Fi first on Mac as explicitly selected by the user.
- Start with `HANDOFF_WINDOWS.md` and `docs/implementation-status.md`. Do not resume camera tests, aliases, smoke or unit tests on this Mac checkout. The Windows workflow begins only when the user starts work there.
- The CLI has macOS/POSIX assumptions. Do not call it Windows-ready: first handle the Windows ZIP/.exe installer, NTFS private-file permissions, pipe I/O and child-process cleanup. Preserve existing security and codec gates; never bypass 0600 checks as a substitute for a real Windows ACL implementation.
- Never copy real credentials or device-label photos into this public repository. Runtime folders and original photos stay ignored.

## Scope and gates

- Follow `KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md`. Current slice: M0-M2 preparation and local MediaMTX POC only. Do not build production website/auth/DB until the camera-to-server network gate passes.
- One Hikvision camera, H.264 720p/25 fps, no audio, viewers in Laos and Vietnam. Latency target: p95 <= 1,000 ms, aiming for p50 <= 500 ms, measured glass-to-glass. Synthetic media does not prove camera latency.
- No Mini PC/NUC/Edge Agent at the camera site. Preserve PDF and original plan.
- Router firmware, WAN changes, resets, external deployment and new infrastructure costs require explicit authority. Do not run router or firewall mutation commands automatically.

## Code and secrets

- Prefer Python 3.9+ standard library for the POC tooling. Do not add third-party runtime packages without reviewing the need.
- Native macOS was the verified historical local route; the active target is now Windows native after the portability work in the handoff. Linux/Docker remains a separately documented, unverified route. Pin versions and verify downloaded archive hashes. Never auto-install system tools.
- Keep camera credentials, RTSP URLs, VPN keys and media tokens out of tracked files, command output and shared evidence. Store runtime configuration in ignored, private files. Do not dump process environments or raw ffprobe stderr.
- POC listeners bind loopback by default; disable unused protocols. The POC is not production authentication. LAN/public exposure must be an explicit, separately reviewed configuration.
- Use bounded subprocess calls, validated inputs, explicit exit codes and actionable redacted errors. Do not interpolate untrusted values into shell commands.

## Verification and reporting

- Add meaningful tests for config validation, credential redaction, probe interpretation, subprocess failures and timeouts. Never soften failures to claim a pass.
- Record exact commands, runtime versions and actual results in `docs/implementation-status.md`. Mark missing hardware/network measurements as pending, not successful.
- For resumed implementation on Windows, required checks are the equivalents of `make check` (compileall, CLI help, unittest) plus `poc.py smoke` with the pinned Windows native binary after W0. The handoff lists PowerShell commands; no GNU Make requirement. `doctor` reports prerequisites without installing them. Mac testing remains stopped by explicit user instruction; do not execute these gates on Mac during cleanup/handoff.
- Real camera RTSP, router/WireGuard recovery, glass-to-glass latency, mobile browsers and 200-peer load each need independent evidence.

