# DEV.ONE Secure Live

Phát triển trực tiếp trên **Mac mini**; **MacBook Air** chạy luồng camera và ghi hình tại điểm đặt. Đọc [bản bàn giao cho chat mới](HANDOFF_MAC_MINI.md) rồi [trạng thái triển khai](docs/implementation-status.md).

## Trạng thái hiện tại

- Camera thật → switch PoE → bộ phát Wi-Fi → Air nhận RTSP bằng MediaMTX v1.21.3 → WebRTC loopback trên Air.
- Kênh101 H.264 Baseline720p/25fps, không âm thanh; mẫu ghi65 giây đạt codec gate, không B-frame. Người dùng chấp nhận tốc độ xem bằng mắt theo mục tiêu1 giây, chưa có số đo p95.
- Air đang ghi SSD theo phiên đăng nhập, giữ khoảng24h, tự dọn theo chu kỳ tối đa30 phút và giữ reserve15GiB. Playback cục bộ có xác thực; chưa có website Admin. Phiên ghi chưa được nghiệm thu đủ24h.
- ER605 không tham gia tuyến hiện tại. Publisher WAN/VPS/HTTPS, bảo trì từ xa và tải200 người xem chưa triển khai.

## Mở dự án

Checkout hiện dùng: `/Volumes/Developer/Projects/camera`. Trên máy phát triển mới, clone source rồi chuẩn bị file riêng tư tại máy; repo không có mật khẩu, key hoặc runtime:

```sh
git clone https://github.com/tuanminh2409bn/camera.git
cd camera
```

Trong chat mới, yêu cầu Codex đọc `AGENTS.md`, `HANDOFF_MAC_MINI.md` và checkpoint; kiểm tra trạng thái Air bằng thao tác chỉ đọc trước khi sửa. Không tạo phiên MediaMTX thứ hai, thêm IP/route tạm hoặc chạy lại helper mạng đã vô hiệu hóa.

## Bản đồ dự án

| Đường dẫn | Vai trò |
|---|---|
| [HANDOFF_MAC_MINI.md](HANDOFF_MAC_MINI.md) | Máy phát triển/runtime, SSH, dữ liệu riêng tư, việc tiếp theo và prompt khởi động |
| [scripts/poc.py](scripts/poc.py) | CLI Python stdlib cho config, cài runtime ghim hash, probe/analyze và POC có thời hạn |
| [scripts/air_recording_supervisor.pl](scripts/air_recording_supervisor.pl) | Giám sát native recording: lock, redaction, auth latch, disk reserve và cleanup |
| [tests/](tests/) và [Makefile](Makefile) | Kiểm thử phần mềm; supervisor dùng Perl trên Air |
| [infra/macos/](infra/macos/) | Plist mẫu session-only; không chứa cấu hình private hay credential |
| [docs/air-recording-service.md](docs/air-recording-service.md) | Vận hành và phát lại cục bộ trên Air |
| [infra/mediamtx/](infra/mediamtx/) | JSON/YAML mẫu loopback; khác với private recording config đang chạy |

## Kiểm tra và tài liệu

`make check` trên Mini kiểm tra Python/CLI/unit fixtures. Những lệnh bắt đầu camera/native runtime là thao tác riêng, không cần để đọc bản bàn giao. Xem kết quả và giới hạn tại [checkpoint](docs/implementation-status.md).

- [Đấu nối hiện tại](docs/hardware-setup.md), [kiểm kê](docs/m0-device-inventory.md), [các cổng triển khai](docs/m0-m2-checklist.md).
- [Kế hoạch v2](KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md) và [PDF v2](DEVONE_Secure_Live_Codex_Blueprint_Ban_Moi_20261030.pdf): hiện trạng, quyết định mở và gói P0-P4. Các bản kế hoạch cũ chỉ còn trong lịch sử Git.

Thứ tự mạng gốc của Mini đã khôi phục: Ethernet → Thunderbolt Bridge → Wi-Fi. Ethernet đang inactive nên Internet hiện vẫn qua Wi-Fi. Không có kết luận rằng thay thứ tự mạng đã xử lý nguyên nhân restart trước đây.
