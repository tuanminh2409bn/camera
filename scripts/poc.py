#!/usr/bin/env python3
"""DEV.ONE Secure Live - M0-M2 local POC CLI."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import math
import os
import platform
import re
import selectors
import shutil
import socket
import stat
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

MEDIAMTX_VERSION = "v1.21.3"
MEDIAMTX_RELEASES: Dict[str, Dict[str, str]] = {
    "darwin_arm64": {
        "url": "https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/mediamtx_v1.21.3_darwin_arm64.tar.gz",
        "sha256": "bc1a0762fd18ffb413bcd81dcb9a072ac159fbd1f27e79ac6f14598aaac5ed3f",
    },
    "darwin_amd64": {
        "url": "https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/mediamtx_v1.21.3_darwin_amd64.tar.gz",
        "sha256": "8a8416ee2ff5d17d9366498b6d88b76ab6d3afcda50b6d7321ccddb349bdbaf2",
    },
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_REL = Path(".local/camera-source.json")
DEFAULT_NATIVE_CONFIG_REL = Path(".local/mediamtx.poc.yml")
DEFAULT_DOCKER_CONFIG_REL = Path(".local/mediamtx.docker.poc.yml")
DEFAULT_MEDIAMTX_BIN_REL = Path(".local/tools/mediamtx-1.21.3/mediamtx")

PLACEHOLDER_TOKENS = (
    "change_me",
    "changeme",
    "placeholder",
    "your_",
    "example",
    "todo",
    "replace_with",
    "<",
    ">",
)
DOC_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
URL_CRED_RE = re.compile(r"((?:rtsp|rtsps|http|https)://)([^/\s@]+)@")
KV_SECRET_RE = re.compile(r"(?i)\b(password|passwd|pass|secret|token)=([^\s&\"']+)")


class PocError(Exception):
    """Actionable, redacted POC error."""


def redact_text(text: str, secrets: Sequence[str] = ()) -> str:
    if not text:
        return ""
    out = URL_CRED_RE.sub(r"\1[REDACTED]@", text)
    out = KV_SECRET_RE.sub(r"\1=[REDACTED]", out)
    for item in secrets:
        if not item:
            continue
        for variant in (item, urllib.parse.quote(item, safe="")):
            if variant:
                out = out.replace(variant, "[REDACTED]")
    return out


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _is_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    return any(tok in lower for tok in PLACEHOLDER_TOKENS)


def validate_host(host: Any) -> str:
    if not isinstance(host, str) or not host or host.strip() != host or _has_control_chars(host):
        raise PocError("Invalid host: must be a non-empty string without whitespace or control characters.")
    if any(ch in host for ch in ("/", "@", "?", "#", "'", '"', "\\", " ")):
        raise PocError("Invalid host: contains forbidden URL or shell delimiter characters.")
    if _is_placeholder(host):
        raise PocError("Invalid host: placeholder or example hostname is not allowed.")
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        if not HOSTNAME_RE.match(host) or host.lower().endswith((".example", ".invalid", ".test")):
            raise PocError("Invalid host: must be a valid IPv4/IPv6 address or RFC-compliant hostname.")
        return host
    if ip_obj.is_unspecified or ip_obj.is_multicast:
        raise PocError("Invalid host: unspecified or multicast IP address is not allowed.")
    if isinstance(ip_obj, ipaddress.IPv4Address) and any(ip_obj in net for net in DOC_NETWORKS):
        raise PocError("Invalid host: RFC 5737 documentation/example IP address is not allowed.")
    return host


def validate_source_config(raw: Any, transport_override: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise PocError("Camera source configuration must be a JSON object.")
    scheme = raw.get("scheme")
    if scheme != "rtsp":
        raise PocError("Invalid scheme: only 'rtsp' is supported.")
    host = validate_host(raw.get("host"))
    port = raw.get("port", 554)
    if isinstance(port, bool) or not isinstance(port, int) or not (1 <= port <= 65535):
        raise PocError("Invalid port: must be an integer between 1 and 65535.")
    channel_raw = raw.get("channel")
    if isinstance(channel_raw, bool) or channel_raw is None:
        raise PocError("Invalid channel: must be '101' or '102'.")
    channel = str(channel_raw) if isinstance(channel_raw, (int, str)) else ""
    if channel not in ("101", "102"):
        raise PocError("Invalid channel: only Hikvision channels '101' and '102' are allowed.")
    username = raw.get("username")
    password = raw.get("password")
    if not isinstance(username, str) or not username or _has_control_chars(username) or _is_placeholder(username):
        raise PocError("Invalid username: must be a non-empty, non-placeholder string without control characters.")
    if not isinstance(password, str) or not password or _has_control_chars(password) or _is_placeholder(password) or password.lower() == "password":
        raise PocError("Invalid password: must be a non-empty, non-placeholder string without control characters.")
    transport = transport_override if transport_override is not None else raw.get("transport", "tcp")
    if transport not in ("tcp", "udp"):
        raise PocError("Invalid transport: must be 'tcp' or 'udp'.")
    enc_user = urllib.parse.quote(username, safe="")
    enc_pass = urllib.parse.quote(password, safe="")
    host_fmt = f"[{host}]" if ":" in host else host
    rtsp_url = f"rtsp://{enc_user}:{enc_pass}@{host_fmt}:{port}/Streaming/Channels/{channel}"
    redacted_url = f"rtsp://[REDACTED]@{host_fmt}:{port}/Streaming/Channels/{channel}"
    return {
        "scheme": "rtsp",
        "host": host,
        "port": port,
        "channel": channel,
        "username": username,
        "password": password,
        "transport": transport,
        "rtsp_url": rtsp_url,
        "redacted_url": redacted_url,
        "secrets": [username, password, enc_user, enc_pass, rtsp_url],
    }


def load_source_file(path: Path, transport_override: Optional[str] = None) -> Dict[str, Any]:
    if not path.exists():
        raise PocError(f"Camera source file not found: {path}. Copy infra/mediamtx/camera-source.example.json to .local/camera-source.json.")
    if path.is_symlink() or not path.is_file():
        raise PocError(f"Camera source path must be a regular non-symlink file: {path}")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise PocError("Camera source file must have mode 0600. Use chmod 600 on the private source file.")
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PocError(f"Failed to parse camera source JSON at {path}: {type(exc).__name__}") from exc
    return validate_source_config(data, transport_override=transport_override)


def validate_private_output_path(path: Path, workspace_root: Path = REPO_ROOT) -> Path:
    root_resolved = workspace_root.resolve()
    relative = path
    if path.is_absolute():
        try:
            relative = path.relative_to(workspace_root.absolute())
        except ValueError:
            try:
                relative = path.relative_to(root_resolved)
            except ValueError:
                raise PocError("Output path must reside inside this workspace's .local/ or .runtime/.") from None
    if len(relative.parts) < 2 or relative.parts[0] not in (".local", ".runtime") or ".." in relative.parts:
        raise PocError("Output path must reside inside ignored .local/ or .runtime/ directory.")
    candidate = root_resolved
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():  # Also catches dangling links before resolution.
            raise PocError("Refusing a symlink in private output path.")
    return candidate


def atomic_write_private(path: Path, content: str, workspace_root: Path = REPO_ROOT) -> Path:
    target = validate_private_output_path(path, workspace_root=workspace_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, target)
        os.chmod(target, 0o600)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    mode = stat.S_IMODE(target.stat().st_mode)
    if mode != 0o600:
        raise PocError(f"Failed to enforce 0600 permissions on {target} (got {oct(mode)}).")
    return target


def _yaml_double_quote(val: str) -> str:
    escaped = val.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_mediamtx_config(
    source_cfg: Optional[Dict[str, Any]],
    *,
    target: str = "native",
    synthetic: bool = False,
    ports: Optional[Dict[str, int]] = None,
) -> str:
    if target not in ("native", "docker"):
        raise PocError("Invalid config target: must be 'native' or 'docker'.")
    if source_cfg is None and not synthetic:
        raise PocError("Either camera source configuration or synthetic mode is required.")
    p = {
        "api": 9997,
        "rtsp": 8554,
        "rtp": 8000,
        "rtcp": 8001,
        "webrtc": 8889,
        "webrtc_udp": 8189,
    }
    if ports:
        p.update(ports)
    bind_host = "127.0.0.1" if target == "native" else "0.0.0.0"
    if target == "native":
        allowed_ips = "['127.0.0.1', '::1']"
    else:
        allowed_ips = "['127.0.0.1', '::1', '172.16.0.0/12', '192.168.65.0/24', '10.0.0.0/8']"
    perms: List[str] = []
    if source_cfg is not None:
        perms.extend(["      - action: read\n        path: live"])
    if synthetic:
        perms.extend(
            [
                "      - action: read\n        path: synthetic",
                "      - action: publish\n        path: synthetic",
            ]
        )
    perms.append("      - action: api")
    paths_lines: List[str] = ["paths:"]
    if source_cfg is not None:
        paths_lines.extend(
            [
                "  live:",
                f"    source: {_yaml_double_quote(source_cfg['rtsp_url'])}",
                "    sourceOnDemand: no",
                f"    rtspTransport: {source_cfg['transport']}",
                "    record: no",
                "    maxReaders: 0",
            ]
        )
    if synthetic:
        paths_lines.extend(
            [
                "  synthetic:",
                "    source: publisher",
                "    overridePublisher: no",
                "    record: no",
            ]
        )
    lines = [
        "# Generated by scripts/poc.py - DO NOT COMMIT (mode 0600)",
        f"# Target: {target} | MediaMTX {MEDIAMTX_VERSION} | Loopback POC only (not production auth)",
        "logLevel: info",
        "logDestinations: [stdout]",
        "",
        "api: yes",
        f"apiAddress: {bind_host}:{p['api']}",
        "",
        "metrics: no",
        "pprof: no",
        "playback: no",
        "",
        "rtsp: yes",
        "rtspTransports: [tcp]",
        'rtspEncryption: "no"',
        f"rtspAddress: {bind_host}:{p['rtsp']}",
        f"rtpAddress: {bind_host}:{p['rtp']}",
        f"rtcpAddress: {bind_host}:{p['rtcp']}",
        "",
        "rtmp: no",
        "hls: no",
        "",
        "webrtc: yes",
        f"webrtcAddress: {bind_host}:{p['webrtc']}",
        "webrtcEncryption: no",
        f"webrtcLocalUDPAddress: {bind_host}:{p['webrtc_udp']}",
        'webrtcLocalTCPAddress: ""',
        "webrtcIPsFromInterfaces: no",
        "webrtcAdditionalHosts: [127.0.0.1]",
        "webrtcICEServers2: []",
        "",
        "srt: no",
        "moq: no",
        "",
        "authMethod: internal",
        "authInternalUsers:",
        "  - user: any",
        '    pass: ""',
        f"    ips: {allowed_ips}",
        "    permissions:",
        *perms,
        "",
        "pathDefaults:",
        "  record: no",
        "",
        *paths_lines,
        "",
    ]
    return "\n".join(lines)


def detect_platform_key(system_name: Optional[str] = None, machine_name: Optional[str] = None) -> str:
    sys_norm = (system_name or platform.system()).lower()
    mach_norm = (machine_name or platform.machine()).lower()
    if sys_norm == "darwin" and mach_norm in ("arm64", "aarch64"):
        return "darwin_arm64"
    if sys_norm == "darwin" and mach_norm in ("x86_64", "amd64"):
        return "darwin_amd64"
    raise PocError(f"Unsupported native MediaMTX platform: {sys_norm}/{mach_norm}")


def _validate_tar_members(tar: tarfile.TarFile, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    for member in tar.getmembers():
        if not member.name or member.name.startswith("/") or "\\" in member.name:
            raise PocError(f"Unsafe archive member path rejected: {member.name!r}")
        parts = Path(member.name).parts
        if ".." in parts or len(parts) != 1:
            raise PocError(f"Archive path traversal or nested directory rejected: {member.name!r}")
        if member.issym() or member.islnk() or member.isfifo() or member.isdev() or not member.isfile():
            raise PocError(f"Non-regular archive member rejected: {member.name!r}")
        target = (dest_resolved / member.name).resolve()
        if target.parent != dest_resolved:
            raise PocError(f"Archive member escapes destination: {member.name!r}")


def install_mediamtx(
    workspace_root: Path = REPO_ROOT,
    platform_key: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    plat = platform_key or detect_platform_key()
    if plat not in MEDIAMTX_RELEASES:
        raise PocError(f"Unsupported platform key for MediaMTX {MEDIAMTX_VERSION}: {plat}")
    rel_info = MEDIAMTX_RELEASES[plat]
    url = rel_info["url"]
    expected_sha = rel_info["sha256"].lower()
    install_dir = validate_private_output_path(
        Path(f".local/tools/mediamtx-{MEDIAMTX_VERSION.lstrip('v')}"),
        workspace_root=workspace_root,
    )
    install_dir.mkdir(parents=True, exist_ok=True)
    fetch = opener or urllib.request.urlopen
    fd, tmp_archive_str = tempfile.mkstemp(prefix=".mediamtx-download-", suffix=".tar.gz", dir=str(install_dir))
    tmp_archive = Path(tmp_archive_str)
    extract_stage = Path(tempfile.mkdtemp(prefix=".mediamtx-extract-", dir=str(install_dir)))
    try:
        hasher = hashlib.sha256()
        with os.fdopen(fd, "wb") as out_file:
            with fetch(url, timeout=30) as resp:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    out_file.write(chunk)
        actual_sha = hasher.hexdigest().lower()
        if not hmac.compare_digest(actual_sha, expected_sha):
            raise PocError(
                f"SHA256 mismatch for MediaMTX archive (expected {expected_sha}, got {actual_sha}). Refusing extraction."
            )
        with tarfile.open(tmp_archive, "r:gz") as tar:
            _validate_tar_members(tar, extract_stage)
            for member in tar.getmembers():
                extracted_src = tar.extractfile(member)
                if extracted_src is None:
                    raise PocError(f"Unable to read archive member {member.name!r}")
                out_member_path = extract_stage / member.name
                with open(out_member_path, "wb") as member_file:
                    shutil.copyfileobj(extracted_src, member_file)
                os.chmod(out_member_path, 0o755 if member.name == "mediamtx" else 0o644)
        staged_bin = extract_stage / "mediamtx"
        if not staged_bin.is_file():
            raise PocError("Verified archive did not contain 'mediamtx' binary.")
        for item in extract_stage.iterdir():
            dest_item = install_dir / item.name
            os.replace(item, dest_item)
        bin_path = install_dir / "mediamtx"
        os.chmod(bin_path, 0o755)
        return {
            "status": "installed",
            "version": MEDIAMTX_VERSION,
            "platform": plat,
            "sha256": actual_sha,
            "binary_path": str(bin_path),
        }
    finally:
        if tmp_archive.exists():
            try:
                tmp_archive.unlink()
            except OSError:
                pass
        if extract_stage.exists():
            shutil.rmtree(extract_stage, ignore_errors=True)


def check_mediamtx_binary(bin_path: Path) -> Tuple[bool, str]:
    if not bin_path.exists() or not bin_path.is_file() or not os.access(bin_path, os.X_OK):
        return False, "missing"
    try:
        proc = subprocess.run([str(bin_path), "--version"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"error:{type(exc).__name__}"
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    ver = out[0].strip() if out else ""
    return (proc.returncode == 0 and ver == MEDIAMTX_VERSION), (ver or f"exit:{proc.returncode}")


def run_doctor(workspace_root: Path = REPO_ROOT, mediamtx_bin: Optional[Path] = None) -> Dict[str, Any]:
    mtx_path = mediamtx_bin or (workspace_root / DEFAULT_MEDIAMTX_BIN_REL)
    mtx_ok, mtx_ver = check_mediamtx_binary(mtx_path)
    external_tools = {name: shutil.which(name) for name in ("ffprobe", "ffmpeg", "docker", "shellcheck")}
    missing_tools = [name for name, found in external_tools.items() if not found]
    if not mtx_ok:
        missing_tools.insert(0, "mediamtx")
    src_path = workspace_root / DEFAULT_SOURCE_REL
    src_valid = False
    if src_path.is_file() and not src_path.is_symlink():
        try:
            load_source_file(src_path)
            src_valid = True
        except PocError:
            src_valid = False
    cfg_path = workspace_root / DEFAULT_NATIVE_CONFIG_REL
    cfg_ok = cfg_path.is_file() and not cfg_path.is_symlink() and stat.S_IMODE(cfg_path.stat().st_mode) == 0o600
    return {
        "status": "ok" if (mtx_ok and external_tools["ffprobe"]) else "degraded",
        "python_version": platform.python_version(),
        "python_supported": sys.version_info >= (3, 9),
        "platform": f"{platform.system().lower()}_{platform.machine().lower()}",
        "mediamtx": {
            "expected_version": MEDIAMTX_VERSION,
            "binary_path": str(mtx_path),
            "ready": mtx_ok,
            "detected_version": mtx_ver,
        },
        "tools": {k: {"installed": bool(v), "path": v} for k, v in external_tools.items()},
        "missing_tools": missing_tools,
        "local_files": {
            "source_config_present": src_path.exists(),
            "source_config_valid": src_valid,
            "native_mediamtx_config_ready": cfg_ok,
        },
        "ready_for": {
            "unit_tests": sys.version_info >= (3, 9),
            "native_mediamtx_smoke": mtx_ok,
            "real_camera_probe": bool(external_tools["ffprobe"]) and src_valid,
            "docker_compose_baseline": bool(external_tools["docker"]),
        },
    }


def _parse_fps(rate_str: Any) -> float:
    if not isinstance(rate_str, str) or not rate_str.strip():
        return 0.0
    if "/" in rate_str:
        parts = rate_str.split("/", 1)
        try:
            num, den = float(parts[0]), float(parts[1])
            return num / den if den > 0 else 0.0
        except ValueError:
            return 0.0
    try:
        return float(rate_str)
    except ValueError:
        return 0.0


def _extract_frame_ts(frame: Dict[str, Any]) -> Optional[float]:
    for key in ("best_effort_timestamp_time", "pkt_pts_time", "pts_time", "pkt_dts_time", "dts_time"):
        val = frame.get(key)
        if val is not None:
            try:
                num = float(val)
                if math.isfinite(num):
                    return num
            except (ValueError, TypeError):
                continue
    return None


def validate_seconds(value: float, name: str, minimum: float = 0.0) -> float:
    if not math.isfinite(value) or value <= 0 or value < minimum:
        raise PocError(f"{name} must be finite and positive" + (f", at least {minimum:g} seconds." if minimum else "."))
    return value


def analyze_ffprobe_payload(raw_json: str, min_duration: float = 60.0) -> Dict[str, Any]:
    validate_seconds(min_duration, "Codec sample duration", minimum=60.0)
    min_frames = max(1, int(math.ceil(min_duration * 24.0)))
    base_report: Dict[str, Any] = {
        "status": "error",
        "gate_passed": False,
        "insufficient_sample": True,
        "observed_duration_sec": 0.0,
        "observed_frame_count": 0,
        "required_min_duration_sec": float(min_duration),
        "required_min_frames": min_frames,
        "sample_coverage_ratio": 0.0,
        "codec": {
            "name": None,
            "profile": None,
            "width": None,
            "height": None,
            "nominal_fps": 0.0,
            "observed_fps": 0.0,
            "audio_streams": 0,
        },
        "frames": {"total": 0, "i_frames": 0, "p_frames": 0, "b_frames": 0, "other_frames": 0},
        "gop": {"count": 0, "min_frames": None, "max_frames": None, "avg_frames": None, "median_frames": None},
        "checks": {
            "codec_h264": False,
            "resolution_1280x720": False,
            "fps_25": False,
            "no_audio": False,
            "no_b_frames": False,
            "sample_coverage_ok": False,
            "gop_measured": False,
        },
        "failure_reasons": [],
    }
    try:
        data = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        base_report["failure_reasons"].append("malformed_json")
        return base_report
    if not isinstance(data, dict):
        base_report["failure_reasons"].append("malformed_json")
        return base_report
    streams = data.get("streams")
    frames = data.get("frames")
    if not isinstance(streams, list) or not streams:
        base_report["failure_reasons"].append("missing_streams")
        return base_report

    reasons: List[str] = []
    video_streams = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"]
    audio_frames = 0
    video_frames: List[Dict[str, Any]] = []
    malformed_frames = False
    if not isinstance(frames, list) or len(frames) == 0:
        reasons.append("missing_frame_evidence")
    else:
        for item in frames:
            if not isinstance(item, dict):
                malformed_frames = True
                continue
            mtype = item.get("media_type", "video")
            if mtype == "audio":
                audio_frames += 1
            elif mtype == "video":
                video_frames.append(item)

    no_audio = len(audio_streams) == 0 and audio_frames == 0
    if not no_audio:
        reasons.append("audio_present")
    if len(video_streams) != 1:
        reasons.append("invalid_video_stream_count")
    vstream = video_streams[0] if video_streams else {}
    codec_name = vstream.get("codec_name") if isinstance(vstream.get("codec_name"), str) else None
    profile = vstream.get("profile") if isinstance(vstream.get("profile"), str) else None
    width = vstream.get("width") if isinstance(vstream.get("width"), int) and not isinstance(vstream.get("width"), bool) else None
    height = vstream.get("height") if isinstance(vstream.get("height"), int) and not isinstance(vstream.get("height"), bool) else None
    nominal_fps = _parse_fps(vstream.get("avg_frame_rate")) or _parse_fps(vstream.get("r_frame_rate"))
    meta_b_frames = vstream.get("has_b_frames", 0)
    meta_has_b = isinstance(meta_b_frames, int) and meta_b_frames > 0

    codec_h264 = codec_name == "h264"
    if not codec_h264:
        reasons.append("codec_not_h264")
    res_720p = width == 1280 and height == 720
    if not res_720p:
        reasons.append("resolution_not_1280x720")

    i_count = p_count = b_count = other_count = 0
    i_indices: List[int] = []
    timestamps: List[float] = []
    for idx, vf in enumerate(video_frames):
        ptype = vf.get("pict_type")
        if not isinstance(ptype, str) or ptype not in ("I", "P", "B", "S", "SI", "SP", "BI"):
            malformed_frames = True
            continue
        if ptype == "I":
            i_count += 1
            i_indices.append(idx)
        elif ptype == "P":
            p_count += 1
        elif ptype == "B":
            b_count += 1
        else:
            other_count += 1
        ts = _extract_frame_ts(vf)
        if ts is not None:
            timestamps.append(ts)
        else:
            malformed_frames = True

    if malformed_frames:
        reasons.append("malformed_frame_entry")

    frame_count = len(video_frames)
    observed_duration = 0.0
    if len(timestamps) >= 2:
        span = max(timestamps) - min(timestamps)
        step = (1.0 / nominal_fps) if nominal_fps > 0 else 0.04
        if span > 0 and frame_count >= 2 and abs(((frame_count - 1) * step) - span) <= 1.0:
            observed_duration = round(span + step, 4)
        else:
            observed_duration = round(max(0.0, span), 4)

    observed_fps = round(frame_count / observed_duration, 3) if observed_duration > 0 else 0.0
    fps_25 = (24.5 <= nominal_fps <= 25.5) and (observed_duration > 0 and 23.5 <= observed_fps <= 26.5)
    if not fps_25:
        reasons.append("fps_not_25")

    no_b_frames = (b_count == 0) and (not meta_has_b) and (frame_count > 0)
    if b_count > 0 or meta_has_b:
        reasons.append("b_frames_detected")

    sample_ok = (
        not malformed_frames
        and frame_count >= min_frames
        and observed_duration >= float(min_duration)
        and len(timestamps) == frame_count
    )
    if not sample_ok:
        if "insufficient_sample" not in reasons:
            reasons.append("insufficient_sample")

    gop_intervals = [i_indices[k + 1] - i_indices[k] for k in range(len(i_indices) - 1)]
    gop_measured = len(gop_intervals) > 0
    if not gop_measured:
        reasons.append("gop_not_measurable")

    gop_info: Dict[str, Any] = {
        "count": len(gop_intervals),
        "min_frames": min(gop_intervals) if gop_measured else None,
        "max_frames": max(gop_intervals) if gop_measured else None,
        "avg_frames": round(sum(gop_intervals) / len(gop_intervals), 2) if gop_measured else None,
        "median_frames": float(statistics.median(gop_intervals)) if gop_measured else None,
    }
    coverage_ratio = 0.0
    if min_duration > 0 and min_frames > 0:
        coverage_ratio = round(min(observed_duration / float(min_duration), frame_count / float(min_frames)), 4)

    checks = {
        "codec_h264": codec_h264,
        "resolution_1280x720": res_720p,
        "fps_25": fps_25,
        "no_audio": no_audio,
        "no_b_frames": no_b_frames,
        "sample_coverage_ok": sample_ok,
        "gop_measured": gop_measured,
    }
    gate_passed = all(checks.values()) and not reasons
    status = "passed" if gate_passed else ("insufficient_sample" if not sample_ok else "failed")
    return {
        "status": status,
        "gate_passed": gate_passed,
        "insufficient_sample": not sample_ok,
        "observed_duration_sec": observed_duration,
        "observed_frame_count": frame_count,
        "required_min_duration_sec": float(min_duration),
        "required_min_frames": min_frames,
        "sample_coverage_ratio": coverage_ratio,
        "codec": {
            "name": codec_name,
            "profile": profile,
            "width": width,
            "height": height,
            "nominal_fps": round(nominal_fps, 3),
            "observed_fps": observed_fps,
            "audio_streams": len(audio_streams) + (1 if audio_frames > 0 and not audio_streams else 0),
        },
        "frames": {
            "total": frame_count,
            "i_frames": i_count,
            "p_frames": p_count,
            "b_frames": b_count,
            "other_frames": other_count,
        },
        "gop": gop_info,
        "checks": checks,
        "failure_reasons": reasons,
    }


def probe_camera_stream(
    source_cfg: Dict[str, Any],
    *,
    ffprobe_bin: str = "ffprobe",
    duration_sec: float = 60.0,
    timeout_sec: Optional[float] = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Dict[str, Any]:
    validate_seconds(duration_sec, "Probe duration", minimum=60.0)
    effective_timeout = validate_seconds(timeout_sec, "Probe timeout") if timeout_sec is not None else max(duration_sec + 15.0, 75.0)
    resolved_bin = shutil.which(ffprobe_bin) if "/" not in ffprobe_bin else ffprobe_bin
    if not resolved_bin or not Path(resolved_bin).exists():
        raise PocError(f"ffprobe binary not found ({ffprobe_bin!r}). Install ffprobe externally or use 'analyze' offline.")
    argv = [
        str(resolved_bin),
        "-v",
        "error",
        "-rtsp_transport",
        source_cfg["transport"],
        "-read_intervals",
        f"%+{duration_sec}",
        "-show_streams",
        "-show_frames",
        "-of",
        "json",
        source_cfg["rtsp_url"],
    ]
    secrets = source_cfg.get("secrets", [])
    try:
        proc = runner(argv, capture_output=True, text=True, timeout=effective_timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise PocError(f"ffprobe timed out after {effective_timeout}s while probing {source_cfg['redacted_url']}.") from None
    except OSError as exc:
        raise PocError(f"Failed to execute ffprobe: {redact_text(str(exc), secrets)}") from None
    if proc.returncode != 0:
        raise PocError(
            f"ffprobe exited with code {proc.returncode} on {source_cfg['redacted_url']} (stderr redacted for secret safety)."
        )
    return analyze_ffprobe_payload(proc.stdout or "", min_duration=duration_sec)


def _terminate_process(proc: subprocess.Popen, timeout: float = 3.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)
    except OSError:
        pass


def _find_free_loopback_ports() -> Dict[str, int]:
    ports: Dict[str, int] = {}
    socks: List[socket.socket] = []
    try:
        for key in ("api", "rtsp", "webrtc"):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            ports[key] = s.getsockname()[1]
            socks.append(s)
        s_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_udp.bind(("127.0.0.1", 0))
        ports["webrtc_udp"] = s_udp.getsockname()[1]
        socks.append(s_udp)
        ports["rtp"] = 18000
        ports["rtcp"] = 18001
        return ports
    finally:
        for s in socks:
            s.close()


def run_smoke(
    workspace_root: Path = REPO_ROOT,
    mediamtx_bin: Optional[Path] = None,
    startup_timeout: float = 5.0,
) -> Dict[str, Any]:
    validate_seconds(startup_timeout, "Smoke startup timeout")
    mtx_path = mediamtx_bin or (workspace_root / DEFAULT_MEDIAMTX_BIN_REL)
    ok, ver_info = check_mediamtx_binary(mtx_path)
    if not ok:
        raise PocError(
            f"MediaMTX {MEDIAMTX_VERSION} binary is not available at {mtx_path} ({ver_info}). "
            "Run 'python3 scripts/poc.py install-mediamtx' or pass --mediamtx-bin."
        )
    ports = _find_free_loopback_ports()
    cfg_text = render_mediamtx_config(None, target="native", synthetic=True, ports=ports)
    smoke_cfg_path = atomic_write_private(
        Path(f".local/mediamtx.smoke.{os.getpid()}.poc.yml"),
        cfg_text,
        workspace_root=workspace_root,
    )
    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            [str(mtx_path), str(smoke_cfg_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + startup_timeout
        player_ok = False
        api_ok = False
        rtsp_ok = False
        player_url = f"http://127.0.0.1:{ports['webrtc']}/synthetic"
        api_url = f"http://127.0.0.1:{ports['api']}/v3/paths/list"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise PocError(f"MediaMTX exited prematurely with code {proc.returncode} during smoke check.")
            try:
                with urllib.request.urlopen(player_url, timeout=0.5) as resp:
                    body = resp.read(4096).decode("utf-8", errors="ignore")
                    player_ok = resp.status == 200 and "<html" in body.lower()
                with urllib.request.urlopen(api_url, timeout=0.5) as resp:
                    api_ok = resp.status == 200
                with socket.create_connection(("127.0.0.1", ports["rtsp"]), timeout=0.5):
                    rtsp_ok = True
                if player_ok and api_ok and rtsp_ok:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        if not (player_ok and api_ok and rtsp_ok):
            raise PocError(
                f"Smoke check timed out waiting for loopback listeners (player={player_ok}, api={api_ok}, rtsp={rtsp_ok})."
            )
        return {
            "status": "passed",
            "version": ver_info,
            "loopback_only": True,
            "synthetic_player_url": player_url,
            "listeners_verified": {"webrtc_http": player_ok, "control_api": api_ok, "rtsp_tcp": rtsp_ok},
            "media_decoded": False,
            "camera_connected": False,
            "note": (
                "Verified native MediaMTX binary version, config parsing, loopback listeners, and built-in player page "
                "on synthetic path. Does NOT prove real camera RTSP, browser WebRTC media decode, or glass-to-glass latency."
            ),
        }
    finally:
        if proc is not None:
            _terminate_process(proc)
            if proc.stdout is not None:
                proc.stdout.close()
        if smoke_cfg_path.exists():
            try:
                smoke_cfg_path.unlink()
            except OSError:
                pass


def run_native_server(
    config_path: Path,
    *,
    workspace_root: Path = REPO_ROOT,
    mediamtx_bin: Optional[Path] = None,
    secrets: Sequence[str] = (),
    duration_sec: Optional[float] = None,
) -> int:
    if duration_sec is not None:
        validate_seconds(duration_sec, "Runtime duration")
    resolved_cfg = validate_private_output_path(config_path, workspace_root=workspace_root)
    if not resolved_cfg.is_file():
        raise PocError(f"MediaMTX config not found at {resolved_cfg}. Run 'python3 scripts/poc.py configure' first.")
    mode = stat.S_IMODE(resolved_cfg.stat().st_mode)
    if mode != 0o600:
        raise PocError(f"Refusing to run config with insecure permissions {oct(mode)} (expected 0o600): {resolved_cfg}")
    # Generated configs carry the source even when the original JSON was moved.
    # Derive redaction values without emitting any raw configuration content.
    secrets = list(secrets)
    for url in re.findall(r"rtsps?://[^\s\"']+", resolved_cfg.read_text(encoding="utf-8")):
        parsed = urllib.parse.urlsplit(url)
        secrets.append(url)
        for credential in (parsed.username, parsed.password):
            if credential:
                secrets.extend((credential, urllib.parse.unquote(credential)))
    mtx_path = mediamtx_bin or (workspace_root / DEFAULT_MEDIAMTX_BIN_REL)
    ok, ver_info = check_mediamtx_binary(mtx_path)
    if not ok:
        raise PocError(f"MediaMTX {MEDIAMTX_VERSION} binary not ready at {mtx_path} ({ver_info}).")
    proc = subprocess.Popen(
        [str(mtx_path), str(resolved_cfg)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + duration_sec if duration_sec is not None else None
    pending = b""
    discard_line = False
    selector = selectors.DefaultSelector()
    try:
        assert proc.stdout is not None
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic() if deadline is not None else 0.2
            if remaining <= 0:
                return 0  # finally stops and waits for this owned child.
            if not selector.select(timeout=min(0.2, remaining)):
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                if pending and not discard_line:
                    sys.stdout.write(redact_text(pending.decode("utf-8", errors="replace"), secrets))
                    sys.stdout.flush()
                break
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if not discard_line:
                    sys.stdout.write(redact_text(line.decode("utf-8", errors="replace"), secrets) + "\n")
                    sys.stdout.flush()
                discard_line = False
            if len(pending) > 65536:
                pending = b""
                discard_line = True  # Never emit a partial oversized line containing secrets.
        try:
            return proc.wait(timeout=max(0.001, deadline - time.monotonic()) if deadline is not None else None)
        except subprocess.TimeoutExpired:
            return 0
    except KeyboardInterrupt:
        _terminate_process(proc)
        return 0
    finally:
        _terminate_process(proc)
        selector.close()
        if proc.stdout is not None:
            proc.stdout.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poc.py",
        description="DEV.ONE Secure Live - M0-M2 Local POC & Camera Stream Verification CLI",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_doc = sub.add_parser("doctor", help="Check local host prerequisites and missing tools (JSON, no auto-install)")
    p_doc.add_argument("--mediamtx-bin", type=Path, default=None, help="Path to MediaMTX binary")
    p_doc.add_argument("--json", action="store_true", help="Emit JSON output (default)")

    p_inst = sub.add_parser(
        "install-mediamtx",
        help="Explicit opt-in download of official MediaMTX v1.21.3 to .local/ with hardcoded SHA256 verification",
    )
    p_inst.add_argument("--platform", choices=sorted(MEDIAMTX_RELEASES.keys()), default=None, help="Target platform key")

    p_cfg = sub.add_parser("configure", help="Validate private camera JSON and write 0600 MediaMTX config under .local/")
    p_cfg.add_argument("--source-file", type=Path, default=DEFAULT_SOURCE_REL, help="Private camera source JSON path")
    p_cfg.add_argument("--output", type=Path, default=None, help="Output MediaMTX config path inside .local/")
    p_cfg.add_argument("--transport", choices=("tcp", "udp"), default=None, help="Override RTSP ingest transport")
    p_cfg.add_argument("--target", choices=("native", "docker"), default="native", help="Render target (native or docker)")
    p_cfg.add_argument("--synthetic", action="store_true", help="Enable loopback-only synthetic publisher path")
    p_cfg.add_argument("--synthetic-only", action="store_true", help="Render synthetic-only config without camera source")

    p_run = sub.add_parser("run", help="Run native MediaMTX with log secret redaction and clean Ctrl-C handling")
    p_run.add_argument("--config", type=Path, default=DEFAULT_NATIVE_CONFIG_REL, help="Private MediaMTX config path")
    p_run.add_argument("--source-file", type=Path, default=DEFAULT_SOURCE_REL, help="Optional source file for redaction")
    p_run.add_argument("--mediamtx-bin", type=Path, default=None, help="Path to MediaMTX binary")
    p_run.add_argument("--duration", type=float, default=None, help="Optional bounded runtime in seconds")

    p_smoke = sub.add_parser("smoke", help="Run bounded native loopback smoke check without real camera")
    p_smoke.add_argument("--mediamtx-bin", type=Path, default=None, help="Path to MediaMTX binary")
    p_smoke.add_argument("--timeout", type=float, default=5.0, help="Startup verification timeout in seconds")

    p_probe = sub.add_parser("probe", help="Probe real camera RTSP stream with bounded ffprobe and verify codec gate")
    p_probe.add_argument("--source-file", type=Path, default=DEFAULT_SOURCE_REL, help="Private camera source JSON path")
    p_probe.add_argument("--ffprobe-bin", type=str, default="ffprobe", help="Path or name of ffprobe binary")
    p_probe.add_argument("--transport", choices=("tcp", "udp"), default=None, help="Override RTSP transport")
    p_probe.add_argument("--duration", type=float, default=60.0, help="Sample duration in seconds (default: 60)")
    p_probe.add_argument("--timeout", type=float, default=None, help="Subprocess timeout in seconds")
    p_probe.add_argument("--output", type=Path, default=None, help="Optional path under .local/ to save sanitized JSON")

    p_an = sub.add_parser("analyze", help="Offline analysis of captured ffprobe JSON stream+frame evidence")
    p_an.add_argument("--input", type=Path, required=True, help="Path to captured ffprobe JSON file")
    p_an.add_argument("--min-duration", type=float, default=60.0, help="Minimum required sample duration in seconds")
    p_an.add_argument("--output", type=Path, default=None, help="Optional path under .local/ to save sanitized JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None, workspace_root: Path = REPO_ROOT) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.subcommand == "doctor":
            rep = run_doctor(workspace_root=workspace_root, mediamtx_bin=args.mediamtx_bin)
            print(json.dumps(rep, indent=2))
            return 0
        if args.subcommand == "install-mediamtx":
            res = install_mediamtx(workspace_root=workspace_root, platform_key=args.platform)
            print(json.dumps(res, indent=2))
            return 0
        if args.subcommand == "configure":
            src_cfg = None
            if not args.synthetic_only:
                src_path = args.source_file if args.source_file.is_absolute() else (workspace_root / args.source_file)
                src_cfg = load_source_file(src_path, transport_override=args.transport)
            default_out = DEFAULT_NATIVE_CONFIG_REL if args.target == "native" else DEFAULT_DOCKER_CONFIG_REL
            out_path = args.output or default_out
            rendered = render_mediamtx_config(
                src_cfg,
                target=args.target,
                synthetic=bool(args.synthetic or args.synthetic_only),
            )
            written = atomic_write_private(out_path, rendered, workspace_root=workspace_root)
            summary = {
                "status": "configured",
                "target": args.target,
                "output_path": str(written),
                "mode": "0600",
                "camera_source": src_cfg["redacted_url"] if src_cfg else None,
                "transport": src_cfg["transport"] if src_cfg else None,
                "synthetic_enabled": bool(args.synthetic or args.synthetic_only),
                "player_url": "http://127.0.0.1:8889/live" if src_cfg else "http://127.0.0.1:8889/synthetic",
            }
            print(json.dumps(summary, indent=2))
            return 0
        if args.subcommand == "run":
            secrets: List[str] = []
            src_path = args.source_file if args.source_file.is_absolute() else (workspace_root / args.source_file)
            if src_path.is_file():
                try:
                    secrets = load_source_file(src_path)["secrets"]
                except PocError:
                    secrets = []
            return run_native_server(
                args.config,
                workspace_root=workspace_root,
                mediamtx_bin=args.mediamtx_bin,
                secrets=secrets,
                duration_sec=args.duration,
            )
        if args.subcommand == "smoke":
            res = run_smoke(workspace_root=workspace_root, mediamtx_bin=args.mediamtx_bin, startup_timeout=args.timeout)
            print(json.dumps(res, indent=2))
            return 0
        if args.subcommand == "probe":
            src_path = args.source_file if args.source_file.is_absolute() else (workspace_root / args.source_file)
            src_cfg = load_source_file(src_path, transport_override=args.transport)
            rep = probe_camera_stream(
                src_cfg,
                ffprobe_bin=args.ffprobe_bin,
                duration_sec=args.duration,
                timeout_sec=args.timeout,
            )
            serialized = json.dumps(rep, indent=2)
            if args.output:
                atomic_write_private(args.output, serialized + "\n", workspace_root=workspace_root)
            print(serialized)
            return 0 if rep["gate_passed"] else 2
        if args.subcommand == "analyze":
            raw_text = args.input.read_text(encoding="utf-8")
            rep = analyze_ffprobe_payload(raw_text, min_duration=args.min_duration)
            serialized = json.dumps(rep, indent=2)
            if args.output:
                atomic_write_private(args.output, serialized + "\n", workspace_root=workspace_root)
            print(serialized)
            return 0 if rep["gate_passed"] else 2
    except PocError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    except (OSError, UnicodeDecodeError, urllib.error.URLError, tarfile.TarError) as exc:
        sys.stderr.write(f"ERROR: Local POC operation failed ({type(exc).__name__}); check paths, permissions and connectivity.\n")
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
