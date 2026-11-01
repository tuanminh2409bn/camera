# Hướng dẫn Docker Compose Local POC (`infra/docker/compose.poc.yml`)

Tài liệu này mô tả tuyến chạy thử bằng Docker cho giai đoạn chuẩn bị **M0–M2** và lý do ưu tiên bản thực thi **MediaMTX native** trên macOS.

**Bàn giao 01/11/2026:** Mac đã dừng kiểm thử và dọn runtime. Tuyến hiện tại là Windows native sau công việc W0 trong [HANDOFF_WINDOWS.md](../../HANDOFF_WINDOWS.md). Docker/Linux/WSL chưa được xác minh trên Windows; các lệnh dưới đây là tham khảo tuyến riêng, không phải bước khởi động Windows mặc định.

## 1. Khi nào dùng tuyến Native vs Docker

- **Trên macOS (khuyến nghị dùng Native):**
  - Máy trạm hiện tại là macOS `darwin_arm64` và không cài sẵn Docker.
  - Ngay cả khi có Docker Desktop trên macOS, container chạy bên trong máy ảo Linux qua lớp mạng NAT. Điều này làm sai lệch hành vi **RTP/UDP ingress** khi kéo RTSP ở chế độ UDP và gây phức tạp cho **WebRTC ICE UDP candidate** (`127.0.0.1:8189/udp`).
  - Do đó, mọi bài đo baseline LAN (M1) và so sánh A/B giữa `rtspTransport: tcp` và `rtspTransport: udp` trên macOS **phải ưu tiên dùng binary native** `mediamtx v1.21.3`.
- **Trên Linux hoặc khi cần kiểm tra RTSP/TCP trong container:**
  - Dùng [`compose.poc.yml`](compose.poc.yml) làm baseline cục bộ với `rtspTransport: tcp`.
  - Đây **không phải** bản triển khai production (chưa có Caddy HTTPS, Fastify auth callback, PostgreSQL hay cấu hình ICE public IP).

## 2. Nguyên tắc bảo mật và cấu hình trong `compose.poc.yml`

1. **Ghim phiên bản cố định:** Sử dụng `bluenviron/mediamtx:1.21.3` (không dùng tag `latest`).
2. **Chỉ mở cổng phía Host trên Loopback (`127.0.0.1`) với target render riêng `--target docker`:**
   - Khi chạy trong Docker, port-forwarding từ host đi vào network namespace của container, nên nếu MediaMTX bên trong container chỉ bind `127.0.0.1` thì host không kết nối tới được.
   - Do đó, `scripts/poc.py configure --target docker` sinh file riêng `.local/mediamtx.docker.poc.yml` (mode `0600`) với listener trong container ở `0.0.0.0` (`8554`, `8889`, `8189`, `9997`), tắt `moq: no`, `srt: no`, `rtmp: no`, `hls: no`, giữ `webrtcAdditionalHosts: [127.0.0.1]` và cho phép IP loopback + dải bridge nội bộ Docker trong `authInternalUsers`.
   - Phía máy host, `compose.poc.yml` khóa chặt các cổng publish vào `127.0.0.1`:
     - `127.0.0.1:8554:8554/tcp`: RTSP local listener
     - `127.0.0.1:8889:8889/tcp`: WebRTC WHEP / trình phát tích hợp (`http://127.0.0.1:8889/live`)
     - `127.0.0.1:8189:8189/udp`: WebRTC ICE UDP local listener
     - `127.0.0.1:9997:9997/tcp`: MediaMTX Control API (chỉ nội bộ loopback)
3. **Không đưa thông tin mật vào `environment:`:**
   - Mật khẩu camera và RTSP URL tuyệt đối không truyền qua biến môi trường của Docker Compose để tránh lộ thông tin khi chạy `docker inspect` hoặc `ps`.
   - File `.local/mediamtx.docker.poc.yml` (mode `0600`, nằm trong `.gitignore`) được mount chỉ đọc (`read_only: true`) vào `/mediamtx.yml`.
4. **Không dùng `healthcheck` gọi `sh`/`curl`:**
   - Image chính thức `bluenviron/mediamtx:1.21.3` là image tối giản (minimal binary image), không có `/bin/sh`, `curl` hay `wget`.
   - Kiểm tra trạng thái từ máy host qua `http://127.0.0.1:8889/live` hoặc `http://127.0.0.1:9997/v3/paths/list`.

## 3. Các bước chạy (khi máy có Docker)

```bash
# 1. Sinh file cấu hình Docker riêng tư (.local/mediamtx.docker.poc.yml, mode 0600)
python3 scripts/poc.py configure --target docker --source-file .local/camera-source.json --transport tcp

# 2. Khởi chạy container trên loopback
docker compose -f infra/docker/compose.poc.yml up

# 3. Dừng và dọn container
docker compose -f infra/docker/compose.poc.yml down
```
