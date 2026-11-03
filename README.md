# DEV.ONE Secure Live

Phát triển trực tiếp trên **Mac mini**; **MacBook Air** chạy luồng camera và ghi hình tại điểm đặt. Đọc [bản bàn giao cho chat mới](HANDOFF_MAC_MINI.md) rồi [trạng thái triển khai](docs/implementation-status.md).

## Trạng thái hiện tại

- Website [lao6789.com](https://lao6789.com) đã chạy HTTPS, Admin/MFA, phân quyền người xem, live và xem lại từ Air.
- Camera101 H264 Baseline720p/25fps + AAC16kHz/mono → Air → tunnel → VPS. FFmpeg chuyển riêng AAC→Opus cho WebRTC, video copy. Người dùng xác nhận nghe được live và bản ghi mới.
- **Ghi mới đang tắt** sau bài thử âm thanh30giây; live/playback vẫn chạy. Không tự bật lại. Video chỉ lưu trên Air, retention1ngày, cleaner startup/chu kỳ30phút, reserve15GiB. Air cần bật/cắm nguồn/mở nắp/đăng nhập.
- [Backup metadata mã hóa](docs/metadata-backup.md): VPS02:15 mỗi ngày/giữ14ngày; Mini lấy khi đăng nhập/mỗi giờ/giữ30ngày. Đã restore bản thật vào DB tạm và kiểm MFA.
- Admin có giám sát12mục và lịch sử cảnh báo; bộ kiểm tra chạy mỗi phút, cảnh báo chỉ hiển thị trên Admin theo lựa chọn người dùng. Xem [hướng dẫn vận hành](docs/operations.md). Traffic đo được không là hóa đơn/quota nhà cung cấp.
- Đã kiểm reboot/đăng nhập lại Air và tắt/bật Wi-Fi riêng Air thật: dịch vụ tự phục hồi, ghi vẫn tắt. Người dùng xác nhận live/tiếng/xem lại tốt trên điện thoại theo hướng dẫn4G/5G; chưa nêu model/browser, không suy thành kiểm đủ Safari/iOS/Android. Tải200/8h đã được miễn (`USER-ACCEPTED/WAIVED`), latency chấp nhận trực quan; không có benchmark200 thật hoặc đo p95. Mất điện toàn hệ thống/đổi WAN-IP/TURN và Lào làm sau.
- Đọc [checkpoint v1](docs/v1-implementation.md) và [hướng dẫn triển khai](docs/web-deployment.md). Kiểm web bằng `npm run check`, browser bằng `npm run test:browser`; không suy ra tải200 media từ unit tests. ER605 không tham gia tuyến hiện tại.

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
