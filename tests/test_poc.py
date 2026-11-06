import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import poc


def _make_valid_source(**overrides):
    data = {
        "scheme": "rtsp",
        "host": "10.20.30.40",
        "port": 554,
        "channel": "102",
        "username": "cam_oper_01",
        "password": "Str0ng!Pass#2026:Live@Cam",
        "transport": "tcp",
    }
    data.update(overrides)
    return data


def _make_ffprobe_payload(
    *,
    frame_count: int = 1500,
    fps_str: str = "25/1",
    step_sec: float = 0.04,
    codec_name: str = "h264",
    width: int = 1280,
    height: int = 720,
    gop: int = 25,
    include_b_frame_at: int = -1,
    has_b_frames_meta: int = 0,
    include_audio: bool = False,
    include_frames: bool = True,
) -> str:
    streams = [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": codec_name,
            "profile": "Baseline",
            "width": width,
            "height": height,
            "avg_frame_rate": fps_str,
            "r_frame_rate": fps_str,
            "has_b_frames": has_b_frames_meta,
            "tags": {"comment": "SECRET_STREAM_TAG_DO_NOT_LEAK"},
        }
    ]
    if include_audio:
        streams.append({"index": 1, "codec_type": "audio", "codec_name": "pcm_alaw"})
    payload = {
        "format": {
            "filename": "rtsp://cam_oper_01:SuperSecretPass999@10.20.30.40:554/Streaming/Channels/102",
            "tags": {"title": "SECRET_FORMAT_TAG"},
        },
        "streams": streams,
    }
    if include_frames:
        frames = []
        for idx in range(frame_count):
            if idx == include_b_frame_at:
                ptype = "B"
            elif gop > 0 and idx % gop == 0:
                ptype = "I"
            else:
                ptype = "P"
            frames.append(
                {
                    "media_type": "video",
                    "stream_index": 0,
                    "pict_type": ptype,
                    "best_effort_timestamp_time": f"{idx * step_sec:.4f}",
                }
            )
        payload["frames"] = frames
    return json.dumps(payload)


class TestSourceValidationAndConfig(unittest.TestCase):
    def test_valid_channels_and_credential_encoding(self):
        cfg102 = poc.validate_source_config(_make_valid_source(channel="102", transport="tcp"))
        self.assertEqual(cfg102["channel"], "102")
        self.assertEqual(cfg102["transport"], "tcp")
        self.assertIn("Str0ng%21Pass%232026%3ALive%40Cam", cfg102["rtsp_url"])
        self.assertNotIn("Str0ng!Pass#2026:Live@Cam", cfg102["redacted_url"])
        self.assertEqual(cfg102["redacted_url"], "rtsp://[REDACTED]@10.20.30.40:554/Streaming/Channels/102")

        cfg101 = poc.validate_source_config(_make_valid_source(channel=101, transport="udp"))
        self.assertEqual(cfg101["channel"], "101")
        self.assertEqual(cfg101["transport"], "udp")

    def test_committed_example_file_is_rejected(self):
        example_path = poc.REPO_ROOT / "infra" / "mediamtx" / "camera-source.example.json"
        self.assertTrue(example_path.is_file())
        with self.assertRaises(poc.PocError):
            poc.load_source_file(example_path)

    def test_rejects_invalid_scheme_host_port_channel_and_credentials(self):
        invalid_cases = [
            {"scheme": "http"},
            {"scheme": "rtsps"},
            {"host": ""},
            {"host": "192.0.2.10"},
            {"host": "0.0.0.0"},
            {"host": "camera.example.com"},
            {"host": "10.0.0.1/evil"},
            {"host": "10.0.0.1:554"},
            {"host": "10.0.0.1\nfoo"},
            {"port": 0},
            {"port": 65536},
            {"port": True},
            {"port": "554"},
            {"channel": "103"},
            {"channel": "1"},
            {"channel": ""},
            {"username": ""},
            {"username": "CHANGE_ME_USER"},
            {"username": "valid_user\nattack"},
            {"password": ""},
            {"password": "password"},
            {"password": "CHANGE_ME_PASSWORD"},
            {"password": "bad\x00pass"},
            {"transport": "http"},
        ]
        for override in invalid_cases:
            with self.subTest(override=override):
                with self.assertRaises(poc.PocError):
                    poc.validate_source_config(_make_valid_source(**override))


class TestRedactionAndPermissions(unittest.TestCase):
    def test_existing_admin_account_is_accepted(self):
        self.assertEqual(poc.validate_source_config(_make_valid_source(username="admin"))["username"], "admin")

    def test_secret_input_requires_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "camera.json"
            path.write_text(json.dumps(_make_valid_source()))
            path.chmod(0o644)
            with self.assertRaises(poc.PocError):
                poc.load_source_file(path)
            path.chmod(0o600)
            self.assertEqual(poc.load_source_file(path)["channel"], "102")

    def test_symlinked_private_roots_and_nested_paths_are_rejected(self):
        for relative in (".local", ".runtime", ".local/nested"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir) / "repo"
                root.mkdir()
                external = Path(tmpdir) / "external"
                external.mkdir()
                link = root / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(external, target_is_directory=True)
                with self.assertRaises(poc.PocError):
                    poc.atomic_write_private(Path(relative) / "secret.yml", "secret", workspace_root=root)
                self.assertEqual(list(external.iterdir()), [])
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".local").mkdir()
            (root / ".local/dangling").symlink_to(root / "missing")
            with self.assertRaises(poc.PocError):
                poc.atomic_write_private(Path(".local/dangling"), "secret", workspace_root=root)

    def test_redact_text_strips_urls_and_secrets(self):
        cfg = poc.validate_source_config(_make_valid_source())
        raw_log = (
            f"Connecting to {cfg['rtsp_url']} with user={cfg['username']} "
            f"and password={cfg['password']} or raw {cfg['password']}"
        )
        cleaned = poc.redact_text(raw_log, cfg["secrets"])
        self.assertNotIn(cfg["password"], cleaned)
        self.assertNotIn(cfg["username"], cleaned)
        self.assertNotIn("Str0ng%21Pass", cleaned)
        self.assertIn("rtsp://[REDACTED]@10.20.30.40:554/Streaming/Channels/102", cleaned)

    def test_atomic_write_enforces_0600_and_rejects_tracked_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cfg = poc.validate_source_config(_make_valid_source())
            yml = poc.render_mediamtx_config(cfg, target="native", synthetic=True)
            out_path = poc.atomic_write_private(Path(".local/mediamtx.poc.yml"), yml, workspace_root=root)
            self.assertTrue(out_path.is_file())
            self.assertEqual(stat.S_IMODE(out_path.stat().st_mode), 0o600)

            for bad_rel in ("mediamtx.yml", "infra/mediamtx.yml", "docs/leak.yml", "../escape.yml"):
                with self.subTest(bad_rel=bad_rel):
                    with self.assertRaises(poc.PocError):
                        poc.atomic_write_private(Path(bad_rel), yml, workspace_root=root)

            symlink_path = root / ".local" / "link.yml"
            symlink_path.symlink_to(out_path)
            with self.assertRaises(poc.PocError):
                poc.atomic_write_private(Path(".local/link.yml"), yml, workspace_root=root)

    def test_render_native_and_docker_configs_disable_moq_and_unused_protocols(self):
        cfg = poc.validate_source_config(_make_valid_source(transport="udp"))
        native_yml = poc.render_mediamtx_config(cfg, target="native", synthetic=False)
        self.assertIn("moq: no", native_yml)
        self.assertIn("srt: no", native_yml)
        self.assertIn("rtmp: no", native_yml)
        self.assertIn("hls: no", native_yml)
        self.assertIn("metrics: no", native_yml)
        self.assertIn("pprof: no", native_yml)
        self.assertIn("playback: no", native_yml)
        self.assertIn("record: no", native_yml)
        self.assertIn("sourceOnDemand: no", native_yml)
        self.assertIn("rtspTransport: udp", native_yml)
        self.assertIn("webrtcAddress: 127.0.0.1:8889", native_yml)
        self.assertNotIn("synthetic:", native_yml)

        docker_yml = poc.render_mediamtx_config(cfg, target="docker", synthetic=True)
        self.assertIn("moq: no", docker_yml)
        self.assertIn("webrtcAddress: 0.0.0.0:8889", docker_yml)
        self.assertIn("rtspAddress: 0.0.0.0:8554", docker_yml)
        self.assertIn("172.16.0.0/12", docker_yml)
        self.assertIn("synthetic:\n    source: publisher", docker_yml)


class TestNativePlatforms(unittest.TestCase):
    def test_nuc_linux_amd64_is_supported_without_changing_macos_targets(self):
        for system, machine, expected in (
            ("Linux", "x86_64", "linux_amd64"),
            ("Linux", "amd64", "linux_amd64"),
            ("Darwin", "arm64", "darwin_arm64"),
            ("Darwin", "x86_64", "darwin_amd64"),
        ):
            with self.subTest(system=system, machine=machine):
                self.assertEqual(poc.detect_platform_key(system, machine), expected)
                self.assertIn(expected, poc.MEDIAMTX_RELEASES)

    def test_unverified_native_platforms_fail_closed(self):
        for system, machine in (("Linux", "aarch64"), ("Windows", "AMD64")):
            with self.subTest(system=system, machine=machine), self.assertRaises(poc.PocError):
                poc.detect_platform_key(system, machine)


class TestInstallMediaMTX(unittest.TestCase):
    def _build_tar_bytes(self, members: dict) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name, content in members.items():
                info = tarfile.TarInfo(name=name)
                if isinstance(content, tuple) and content[0] == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = content[1]
                    tar.addfile(info)
                else:
                    data = content if isinstance(content, bytes) else content.encode("utf-8")
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def test_install_rejects_sha256_mismatch_before_extraction(self):
        archive_bytes = self._build_tar_bytes({"mediamtx": b"#!/bin/sh\necho v1.21.3\n"})
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def fake_opener(url, timeout=30):
                return io.BytesIO(archive_bytes)

            with self.assertRaises(poc.PocError) as ctx:
                poc.install_mediamtx(workspace_root=root, platform_key="darwin_arm64", opener=fake_opener)
            self.assertIn("SHA256 mismatch", str(ctx.exception))
            install_dir = root / ".local" / "tools" / "mediamtx-1.21.3"
            self.assertFalse((install_dir / "mediamtx").exists())

    def test_install_rejects_path_traversal_and_symlinks(self):
        for bad_members in (
            {"../evil": b"bad"},
            {"/tmp/evil": b"bad"},
            {"sub/mediamtx": b"bad"},
            {"mediamtx": ("symlink", "/bin/sh")},
        ):
            archive_bytes = self._build_tar_bytes(bad_members)
            digest = hashlib.sha256(archive_bytes).hexdigest()
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                with mock.patch.dict(
                    poc.MEDIAMTX_RELEASES,
                    {"darwin_arm64": {"url": "https://example.invalid/mtx.tar.gz", "sha256": digest}},
                ):
                    with self.assertRaises(poc.PocError):
                        poc.install_mediamtx(
                            workspace_root=root,
                            platform_key="darwin_arm64",
                            opener=lambda url, timeout=30: io.BytesIO(archive_bytes),
                        )

    def test_install_succeeds_with_matching_sha256(self):
        archive_bytes = self._build_tar_bytes(
            {"mediamtx": b"#!/bin/sh\necho v1.21.3\n", "LICENSE": b"MIT"}
        )
        digest = hashlib.sha256(archive_bytes).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with mock.patch.dict(
                poc.MEDIAMTX_RELEASES,
                {"darwin_arm64": {"url": "https://example.invalid/mtx.tar.gz", "sha256": digest}},
            ):
                res = poc.install_mediamtx(
                    workspace_root=root,
                    platform_key="darwin_arm64",
                    opener=lambda url, timeout=30: io.BytesIO(archive_bytes),
                )
                self.assertEqual(res["status"], "installed")
                bin_path = Path(res["binary_path"])
                self.assertTrue(bin_path.is_file())
                self.assertTrue(os.access(bin_path, os.X_OK))


class TestFFprobeAnalysisAndSubprocess(unittest.TestCase):
    def test_short_or_invalid_duration_cannot_relax_codec_gate(self):
        raw = _make_ffprobe_payload(frame_count=250)
        for value in (1, 10, 0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(poc.PocError):
                poc.analyze_ffprobe_payload(raw, min_duration=value)

    def test_full_60s_valid_sample_passes_and_sanitizes_secrets(self):
        raw = _make_ffprobe_payload(frame_count=1500, step_sec=0.04, gop=25)
        rep = poc.analyze_ffprobe_payload(raw, min_duration=60.0)
        self.assertTrue(rep["gate_passed"])
        self.assertEqual(rep["status"], "passed")
        self.assertFalse(rep["insufficient_sample"])
        self.assertEqual(rep["observed_frame_count"], 1500)
        self.assertGreaterEqual(rep["observed_duration_sec"], 60.0)
        self.assertEqual(rep["gop"]["avg_frames"], 25.0)
        dumped = json.dumps(rep)
        self.assertNotIn("SuperSecretPass999", dumped)
        self.assertNotIn("SECRET_STREAM_TAG_DO_NOT_LEAK", dumped)
        self.assertNotIn("SECRET_FORMAT_TAG", dumped)
        self.assertNotIn("10.20.30.40", dumped)

    def test_metadata_only_and_truncated_samples_fail(self):
        meta_only = _make_ffprobe_payload(include_frames=False)
        rep_meta = poc.analyze_ffprobe_payload(meta_only, min_duration=60.0)
        self.assertFalse(rep_meta["gate_passed"])
        self.assertTrue(rep_meta["insufficient_sample"])
        self.assertIn("missing_frame_evidence", rep_meta["failure_reasons"])

        short_sample = _make_ffprobe_payload(frame_count=250, step_sec=0.04)
        rep_short = poc.analyze_ffprobe_payload(short_sample, min_duration=60.0)
        self.assertFalse(rep_short["gate_passed"])
        self.assertTrue(rep_short["insufficient_sample"])
        self.assertEqual(rep_short["status"], "insufficient_sample")

        sparse_two_frames = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1280,
                        "height": 720,
                        "avg_frame_rate": "25/1",
                    }
                ],
                "frames": [
                    {"media_type": "video", "pict_type": "I", "best_effort_timestamp_time": "0.0"},
                    {"media_type": "video", "pict_type": "I", "best_effort_timestamp_time": "60.0"},
                ],
            }
        )
        rep_sparse = poc.analyze_ffprobe_payload(sparse_two_frames, min_duration=60.0)
        self.assertFalse(rep_sparse["gate_passed"])
        self.assertTrue(rep_sparse["insufficient_sample"])

    def test_b_frames_audio_wrong_codec_and_malformed_json_fail(self):
        with_b = _make_ffprobe_payload(frame_count=1500, include_b_frame_at=12)
        rep_b = poc.analyze_ffprobe_payload(with_b, min_duration=60.0)
        self.assertFalse(rep_b["gate_passed"])
        self.assertFalse(rep_b["checks"]["no_b_frames"])
        self.assertIn("b_frames_detected", rep_b["failure_reasons"])

        with_audio = _make_ffprobe_payload(frame_count=1500, include_audio=True)
        rep_aud = poc.analyze_ffprobe_payload(with_audio, min_duration=60.0)
        self.assertFalse(rep_aud["gate_passed"])
        self.assertFalse(rep_aud["checks"]["no_audio"])

        wrong_res = _make_ffprobe_payload(frame_count=1500, width=1920, height=1080)
        self.assertFalse(poc.analyze_ffprobe_payload(wrong_res, min_duration=60.0)["gate_passed"])

        bad_json = poc.analyze_ffprobe_payload("{not-json", min_duration=60.0)
        self.assertFalse(bad_json["gate_passed"])
        self.assertEqual(bad_json["status"], "error")

    def test_probe_handles_nonzero_exit_and_timeout_without_leaking_secrets(self):
        cfg = poc.validate_source_config(_make_valid_source())

        def failing_runner(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv,
                returncode=1,
                stdout="",
                stderr=f"Failed to open {cfg['rtsp_url']} with pass {cfg['password']}",
            )

        with self.assertRaises(poc.PocError) as ctx_err:
            poc.probe_camera_stream(cfg, ffprobe_bin=sys.executable, runner=failing_runner)
        self.assertNotIn(cfg["password"], str(ctx_err.exception))
        self.assertNotIn(cfg["rtsp_url"], str(ctx_err.exception))

        def timeout_runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=5.0, stderr=cfg["rtsp_url"])

        with self.assertRaises(poc.PocError) as ctx_to:
            poc.probe_camera_stream(cfg, ffprobe_bin=sys.executable, timeout_sec=5.0, runner=timeout_runner)
        self.assertIn("timed out", str(ctx_to.exception))
        self.assertNotIn(cfg["password"], str(ctx_to.exception))
        self.assertNotIn(cfg["rtsp_url"], str(ctx_to.exception))


class TestProcessCleanupAndRepoContracts(unittest.TestCase):
    def test_run_redacts_config_secrets_and_preserves_failure_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cfg = poc.validate_source_config(_make_valid_source())
            config = poc.atomic_write_private(Path(".local/run.yml"), poc.render_mediamtx_config(cfg), workspace_root=root)
            binary = root / "failure.py"
            binary.write_text(
                "#!/usr/bin/env python3\nimport sys\n"
                "if '--version' in sys.argv:\n print('v1.21.3'); sys.exit(0)\n"
                f"print({cfg['rtsp_url']!r}); print({cfg['password']!r}); sys.exit(7)\n"
            )
            binary.chmod(0o700)
            with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                result = poc.run_native_server(config, workspace_root=root, mediamtx_bin=binary, duration_sec=2)
            self.assertEqual(result, 7)
            self.assertNotIn(cfg["password"], output.getvalue())
            self.assertNotIn(cfg["rtsp_url"], output.getvalue())

    def test_bounded_run_stops_a_silent_child(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            binary = root / "silent.py"
            pidfile = root / "pid"
            binary.write_text(
                "#!/usr/bin/env python3\nimport os,sys,time\n"
                "if '--version' in sys.argv:\n print('v1.21.3'); sys.exit(0)\n"
                f"open({str(pidfile)!r},'w').write(str(os.getpid()))\n"
                "time.sleep(3)\n"
            )
            binary.chmod(0o700)
            config = poc.atomic_write_private(Path(".local/run.yml"), "logLevel: error\n", workspace_root=root)
            started = time.monotonic()
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                result = poc.run_native_server(config, workspace_root=root, mediamtx_bin=binary, duration_sec=0.2)
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertEqual(result, 0)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_invalid_runtime_bounds_fail_before_starting_process(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(poc.PocError):
                poc.run_smoke(startup_timeout=value)

    def test_smoke_fails_honestly_when_binary_missing_and_cleans_up_process_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(poc.PocError) as ctx:
                poc.run_smoke(workspace_root=root, mediamtx_bin=root / "nonexistent-mediamtx")
            self.assertIn("not available", str(ctx.exception))

            fake_bin = root / "fake_mediamtx.py"
            fake_bin.write_text(
                "#!/usr/bin/env python3\n"
                "import sys, time\n"
                "if '--version' in sys.argv:\n"
                "    print('v1.21.3')\n"
                "    sys.exit(0)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            os.chmod(fake_bin, 0o755)
            with self.assertRaises(poc.PocError):
                poc.run_smoke(workspace_root=root, mediamtx_bin=fake_bin, startup_timeout=0.3)
            smoke_files = list((root / ".local").glob("mediamtx.smoke.*.poc.yml"))
            self.assertEqual(smoke_files, [])

    def test_gitignore_does_not_ignore_docker_compose_and_template_disables_moq(self):
        gitignore_text = (poc.REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("\n*.poc.yml\n", "\n" + gitignore_text)
        template_text = (poc.REPO_ROOT / "infra" / "mediamtx" / "mediamtx.poc.template.yml").read_text(encoding="utf-8")
        self.assertIn("moq: no", template_text)


if __name__ == "__main__":
    unittest.main()
