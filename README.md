# DEV.ONE Secure Live — tiếp tục trên Windows

Đọc **[HANDOFF_WINDOWS.md](HANDOFF_WINDOWS.md)**: trạng thái thiết bị, cách mở Codex Windows, công việc đầu tiên và prompt khởi động.

Ngày 01/11/2026, người dùng dừng toàn bộ kiểm thử trên Mac và chuyển sang Windows. Giữ source POC/tests; runtime, công cụ tải về, mật khẩu và báo cáo thử trên Mac đã xóa. Không có thông tin đăng nhập thật trong repo.

## Bắt đầu

~~~powershell
git clone https://github.com/tuanminh2409bn/camera.git
Set-Location camera
~~~

Mở thư mục trong Codex, đọc AGENTS.md và bản bàn giao. CLI còn giả định macOS/POSIX; **W0 là bổ sung Windows native**, chưa được nghiệm thu Windows.

## Mục tiêu

Camera Hikvision → switch PoE → ER605/WireGuard → MediaMTX Singapore → WebRTC tại Lào/Việt Nam. H.264 1280×720/25fps, không audio; p95 glass-to-glass ≤1.000 ms, hướng tới p50 ≤500 ms. Không có Edge Agent tại điểm đặt camera.

Chỉ M0–M2 trước; website/API/DB production, recording và tải 200 peers vẫn theo các cổng mạng/video/độ trễ thực tế.

## Nội dung

| Đường dẫn | Vai trò |
|---|---|
| scripts/poc.py | Python stdlib: config, installer ghim hash, runtime có giới hạn, redaction, probe/analyze |
| tests/ và Makefile | Tests/lệnh kiểm tra; 22 tests từng đạt trên Mac |
| infra/mediamtx/ | Mẫu JSON/YAML loopback, không có credential thật |
| infra/docker/ | Linux/Docker tham khảo, chưa chạy trên Windows |
| infra/vpn/ | Runbook thủ công ER605/WireGuard/VPS |
| docs/ | Kiểm kê, cổng nghiệm thu, đo độ trễ, checkpoint |
| PDF và kế hoạch gốc | Giữ nguyên tài liệu đã duyệt |

Camera Activated, lần cuối DHCP 192.168.0.101; web Windows đã vào được. HTTP/RTSP digest/MD5. Chưa có video RTSP, codec, WebRTC video, latency, VPN hoặc Windows runtime được xác minh.

Mac trước đây đạt make check và smoke native v1.21.3; smoke chỉ có listener/API/player, không giải mã video. Đọc [checkpoint](docs/implementation-status.md) để biết giới hạn bằng chứng.

## Tài liệu

- [Bàn giao Windows](HANDOFF_WINDOWS.md)
- [Kế hoạch M0–M6](KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md)
- [Đấu nối](docs/hardware-setup.md), [kiểm kê](docs/m0-device-inventory.md), [cổng M0–M2](docs/m0-m2-checklist.md)
- [Đo glass-to-glass](docs/latency-measurement-procedure.md)
- [WireGuard](infra/vpn/README.md), [Docker tham khảo](infra/docker/README.md)

.local/.runtime, media, keys và ảnh tem có định danh không được publish. Không tiếp tục chẩn đoán Mac đã dừng; phiên Windows do người dùng bắt đầu sẽ ghi bằng chứng mới.
