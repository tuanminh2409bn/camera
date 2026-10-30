# DEV.ONE Secure Live — Chuẩn bị M0–M2 & Local MediaMTX POC

Bộ công cụ và tài liệu chuẩn bị cho giai đoạn **M0–M2** theo [`KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md`](KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md):
- **Luồng mục tiêu:** Một camera Hikvision (H.264, `1280x720`, `25 fps`, không âm thanh, không B-frame) → Switch PoE → Router TP-Link ER605 (WireGuard) → MediaMTX tại Singapore → Trình duyệt WebRTC tại Lào và Việt Nam.
- **Mục tiêu độ trễ glass-to-glass:** `p95 ≤ 1.000 ms`, hướng tới `p50 ≤ 500 ms` (sàn LAN M1 hướng tới `p95 ≤ 400 ms`).
- **Phạm vi hiện tại:** Chỉ bao gồm công cụ POC cục bộ (`scripts/poc.py`), kiểm tra cấu hình/codec, cấu hình MediaMTX `v1.21.3` trên loopback và tài liệu chuẩn bị thiết bị/VPN cho M0–M2. **Chưa xây dựng** website/API/DB production khi chưa vượt qua cổng mạng từ camera tới server.
- **Hiện trạng thiết bị:** Camera và router ER605 **chưa kết nối**. Không có bất kỳ kết quả đo độ trễ phần cứng hay VPS giả lập nào được ghi nhận là đạt.

## 1. Yêu cầu hệ thống & Công cụ

- **Python:** `3.9+` (chỉ sử dụng thư viện chuẩn Python và `unittest`, không dùng gói phụ thuộc bên thứ ba).
- **MediaMTX (ghim cố định `v1.21.3`):**
  - Ưu tiên chạy **native trên macOS `darwin_arm64`** vì máy trạm hiện không có Docker và mạng máy ảo Docker trên macOS làm sai lệch đường RTP/UDP ingress cũng như WebRTC UDP candidate.
  - Bản phát hành chính thức: `mediamtx_v1.21.3_darwin_arm64.tar.gz` (`SHA256: bc1a0762fd18ffb413bcd81dcb9a072ac159fbd1f27e79ac6f14598aaac5ed3f`).
- **Công cụ cài ngoài (không tự động cài đặt):**
  - `ffprobe`: cần thiết khi probe luồng RTSP thật từ camera (`CODEC-01`). Khi chưa có `ffprobe` hoặc chưa nối camera, có thể dùng lệnh `analyze` để kiểm tra offline file JSON đã thu.
  - `docker`: tuỳ chọn cho tuyến mẫu [`infra/docker/compose.poc.yml`](infra/docker/compose.poc.yml).

## 2. Các lệnh sử dụng chính xác

### 2.1. Kiểm tra môi trường máy trạm (`doctor`)

```bash
python3 scripts/poc.py --help
python3 scripts/poc.py doctor
```

Lệnh `doctor` xuất JSON liệt kê trạng thái Python, binary MediaMTX `v1.21.3`, các công cụ thiếu trên `PATH` (`ffprobe`, `ffmpeg`, `docker`, `shellcheck`) và không bao giờ tự động cài đặt gói hệ thống.

### 2.2. Tải MediaMTX `v1.21.3` chính thức (chỉ khi người dùng chủ động gọi)

```bash
python3 scripts/poc.py install-mediamtx
```

Tải gói chính thức về `.local/tools/mediamtx-1.21.3/`, kiểm tra khớp mã băm `SHA256` cứng và kiểm tra an toàn đường dẫn tar trước khi giải nén.

### 2.3. Khởi tạo và sinh cấu hình riêng tư (`0600`)

1. Sao chép file mẫu chứa placeholder sang `.local/camera-source.json` và điền thông tin thật của camera (file trong `.local/` đã được `.gitignore`):
   ```bash
   mkdir -p .local
   cp infra/mediamtx/camera-source.example.json .local/camera-source.json
   chmod 600 .local/camera-source.json
   ```
   > File mẫu [`infra/mediamtx/camera-source.example.json`](infra/mediamtx/camera-source.example.json) chứa giá trị placeholder (`192.0.2.10`, `CHANGE_ME_...`) và sẽ bị `poc.py` từ chối cho tới khi được thay bằng thông tin hợp lệ.

2. Sinh cấu hình MediaMTX native (`.local/mediamtx.poc.yml`, mode `0600`, khóa toàn bộ listener ở `127.0.0.1` và tắt `moq`, `srt`, `rtmp`, `hls`, `metrics`, `pprof`, `playback`, `record`):
   ```bash
   # Chế độ TCP baseline (mặc định) hoặc UDP cho thử nghiệm A/B
   python3 scripts/poc.py configure --source-file .local/camera-source.json --transport tcp
   python3 scripts/poc.py configure --source-file .local/camera-source.json --transport udp
   ```

3. Sinh cấu hình khi cần bật thêm đường `synthetic` (chỉ cho phép publish/read nội bộ trên loopback, tách biệt hoàn toàn với đường `live` chỉ đọc từ camera) hoặc sinh cấu hình cho Docker (`--target docker`):
   ```bash
   python3 scripts/poc.py configure --synthetic-only
   python3 scripts/poc.py configure --target docker --source-file .local/camera-source.json --transport tcp
   ```

### 2.4. Kiểm thử khói runtime native (`smoke`) và chạy MediaMTX (`run`)

```bash
# Kiểm thử khói: khởi chạy tạm thời binary v1.21.3 trên cổng loopback trống,
# xác minh version, parse config, kiểm tra trang WebRTC player tích hợp rồi tự dừng sạch sẽ
python3 scripts/poc.py smoke

# Chạy MediaMTX native với bộ lọc ẩn mật khẩu/RTSP URL trên log; mở player tại http://127.0.0.1:8889/live
python3 scripts/poc.py run --config .local/mediamtx.poc.yml
```

### 2.5. Kiểm tra Codec Gate (`probe` trực tiếp và `analyze` offline)

```bash
# Probe trực tiếp camera thật trong 60 giây bằng ffprobe (không qua shell, có timeout giới hạn)
python3 scripts/poc.py probe --source-file .local/camera-source.json --duration 60 --output .local/probe-report.json

# Phân tích offline từ file JSON xuất bởi ffprobe
python3 scripts/poc.py analyze --input /path/to/ffprobe-capture.json --min-duration 60 --output .local/probe-report.json
```

Báo cáo chỉ giữ lại các trường đã whitelist (`H.264`, `1280x720`, `25 fps`, không audio, `0` B-frame quan sát được, độ phủ mẫu và GOP thực đo); mọi mẫu chỉ có metadata, thiếu frame, thời lượng ngắn hơn ngưỡng hoặc lỗi JSON đều bị đánh `FAIL` (`gate_passed: false`).

### 2.6. Chạy kiểm thử tự động

```bash
python3 -m unittest discover -s tests -v
python3 scripts/poc.py --help
python3 -m compileall -q scripts tests
```

Hoặc qua `Makefile`: `make check`, `make test`, `make doctor`, `make smoke`.

## 3. Tài liệu và Cổng kiểm soát (M0–M2)

- [`docs/m0-device-inventory.md`](docs/m0-device-inventory.md): Bảng kiểm kê thiết bị M0 (firmware camera, ER605, PoE đang ở trạng thái `PENDING`).
- [`docs/hardware-setup.md`](docs/hardware-setup.md): Cắm dây theo đúng cổng thiết bị trong ảnh, chuẩn bị lần thử camera thật.
- [`docs/m0-m2-checklist.md`](docs/m0-m2-checklist.md): Danh mục điều kiện qua cổng M0–M2 (`HW-01`, `CODEC-01`, `NET-01`, `NET-02`, `LAT-01`).
- [`docs/latency-measurement-procedure.md`](docs/latency-measurement-procedure.md): Quy trình đo độ trễ quang học glass-to-glass và mẫu báo cáo đã làm sạch.
- [`infra/vpn/README.md`](infra/vpn/README.md) & [`infra/vpn/wg0.vps.example.conf`](infra/vpn/wg0.vps.example.conf): Runbook cấu hình thủ công WireGuard giữa ER605 (standalone) và VPS Singapore với dải route hẹp.
- [`infra/docker/README.md`](infra/docker/README.md) & [`infra/docker/compose.poc.yml`](infra/docker/compose.poc.yml): Cấu hình Docker Compose cục bộ dùng `--target docker`.
- [`docs/implementation-status.md`](docs/implementation-status.md): Trạng thái triển khai, kết quả chạy lệnh thực tế và các điểm nghẽn phần cứng đang chờ.
