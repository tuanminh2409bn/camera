# DEV.ONE Secure Live — hướng dẫn làm việc

## Bắt đầu chat mới

- Đọc `HANDOFF_MAC_MINI.md`, `docs/implementation-status.md` và `docs/air-recording-service.md` trước khi tiếp tục. Kiểm tra HEAD/working tree thực tế; các PID, IP, dung lượng và trạng thái trong tài liệu là snapshot.
- Mac mini là máy phát triển duy nhất, checkout `/Volumes/Developer/Projects/camera`. MacBook Air là máy chạy MediaMTX/ghi hình tại điểm camera, workspace `/Users/macbook/Developer/camera`; không nhầm hai máy khi chạy lệnh.
- Codex tự triển khai, review và kiểm thử trực tiếp theo `dev-flow`. Không dùng Antigravity, `agy` hoặc bridge/worker cũ. Không tự phục hồi những công cụ đã gỡ.
- Các yêu cầu hiện tại thay thế hướng bàn giao và các tuyến đấu nối cũ. Kế hoạch Markdown và PDF tại root đã cập nhật v2 ngày 02/11/2026; bản gốc 30/10 và các runbook tuyến cũ đã bỏ khỏi checkout theo yêu cầu người dùng; truy vết bằng lịch sử Git. Đọc kế hoạch v2 cùng bàn giao/checkpoint; không dùng bản lịch sử để triển khai.

## Tuyến và phạm vi hiện tại

- Camera Hikvision `DS-2CD2643G2-LIZS2UHUN`, firmware `V5.7.23 build 260320`, IP tĩnh `192.168.1.64/24`, DHCP=false.
- Camera → PoE 1 của switch; switch UPLINK 5 → LAN bộ phát Wi-Fi. Mini và Air cùng mạng Wi-Fi. ER605 không tham gia tuyến hiện tại; không nối lại hoặc đổi camera DHCP để khớp tài liệu cũ.
- Kênh101: H.264 Baseline, 1280×720, 25 fps, CBR2048Kbps, GOP25, không âm thanh, H264+/SVC tắt. Có full backup mã hóa riêng tư trước khi chỉnh, chưa kiểm tra restore.
- Người dùng đã chấp nhận tốc độ WebRTC bằng mắt theo mục tiêu một giây và miễn bài đo quang học: ghi `USER-ACCEPTED/VISUAL`, không ghi p95 đã đo hoặc yêu cầu quay slow-motion lại trong phạm vi này.
- Hiện là POC native LAN/ghi SSD. Website Admin/RBAC, VPN bảo trì, publisher WAN, VPS, HTTPS public và tải200 peers chưa triển khai. Mọi hạ tầng/cost, dependency mới, thay schema/public API hoặc mở listener LAN/public cần quyền riêng.

## Giữ phiên ghi trên Air

- Service label `com.devone.camera.air-recording-supervisor`, bootstrap từ `.local/recording-service/recording-agent.plist` trong user GUI session. `KeepAlive=false`, chưa cài `Library/LaunchAgents` hay daemon; không tự chạy lại sau logout/reboot.
- Giữ Air cắm nguồn, mở nắp và đăng nhập. Đọc `status.json`/API trước khi thao tác; không dùng PID chép từ tài liệu để signal và không khởi động native instance thứ hai.
- Ghi `.local/recordings/live/`, fMP4, part1s/segment1m, retention1d. Native cleaner có thể dọn trễ khoảng30 phút sau mốc24h; wrapper không tự xóa video. Reserve15GiB; lỗi/thiếu dung lượng sẽ pause ghi, pause thất bại thì dừng child.
- Camera auth401/403 phải dừng và giữ `auth-stop.latch`, không thử lặp. Playback HTTP401 là challenge cục bộ, không phải lỗi mật khẩu camera. Không tự gỡ latch khi chưa review nguyên nhân.
- Listener chỉ127.0.0.1: RTSP8554, WebRTC8889/UDP8189, API9997, playback9996. Playback có tài khoản riêng; chưa có Admin website.
- SSH đã được duyệt qua LAN tới `macbook@192.168.1.12`, key/trust riêng tại `.local/ssh/air-poc` trên Mini. Key bị giới hạn nguồn Mini `192.168.1.8`; không mở rộng quyền hoặc đổi trust/host key khi gặp lỗi.

## Mạng và sự cố Mini

- Theo yêu cầu mới, thứ tự gốc đã được người dùng lưu và Codex xác minh: **Ethernet → Thunderbolt Bridge → Wi-Fi**. Ethernet hiện inactive/DHCP, default route vẫn qua Wi-Fi en1. Không tự chuyển lại Wi-Fi-first.
- Không thêm IP phụ/host route hoặc chạy lại helper mạng cũ. `.local/check-mac-camera.py` phải tiếp tục không tồn tại; bản `.disabled.txt` chỉ lưu để tra cứu.
- Người dùng từng gặp restart khi chạy helper. Log có `SOCD report detected: (iBoot async abort)`; chưa xác định nguyên nhân. Khôi phục thứ tự mạng không chứng minh đã sửa được lỗi hệ thống. Không tự reboot/update macOS, chẩn đoán stress, đổi WAN/router/firmware hoặc flush route.

## Source, công cụ và bí mật

- `scripts/poc.py`: Python3.9+ stdlib, config/probe/analyze/installer/runtime có giới hạn. MediaMTX ghim v1.21.3; supervisor dùng Perl core của Air. Không tự cài Python/CLT trên Air.
- FFprobe9.0.2 Intel chỉ được duyệt trong project Air. Không chạy binary Intel này trên Mini hoặc cài công cụ hệ thống ngầm.
- `.local`/runtime0700, cấu hình và credential0600. Không in password, RTSP URL có credential, private key, raw config/API config dump hoặc environment. Chỉ xuất các field allowlist đã redaction.
- Không commit runtime, video, backup cấu hình thiết bị, ảnh tem, mật khẩu hoặc log riêng tư. Các bản clone mới không có credential/SSH key; người dùng nhập trực tiếp trên máy khi cần.
- Giữ thay đổi ngoài phạm vi. Push/merge/deploy cần quyền; yêu cầu cập nhật GitHub trong phiên bàn giao này đã cho phép commit và push phần công việc được tổng hợp, không cho phép phát hành hạ tầng.

## Kiểm chứng

- Software checks trên Mini: `make check` (compileall, CLI help, Python unittest); các bài dùng fixture và child giả. Không chạy lại pipeline camera/native trên Mini chỉ để bàn giao.
- Supervisor trên Air: `/usr/bin/perl -c scripts/air_recording_supervisor.pl` và `/usr/bin/perl tests/test_air_recording_supervisor.t`; dùng fake workspace/child, không đổi phiên ghi thật.
- Không coi unit/synthetic là bằng chứng codec, latency, WAN hay endurance. Chỉ ghi PASS cho cổng có dữ liệu phù hợp; ghi rõ máy thực thi và thời điểm.
- Trước công bố: kiểm tra diff, Markdown links, plist, hash source, file bị ignore và secret scan; ghi lệnh/kết quả trong checkpoint. Không làm yếu gate/tests để lấy kết quả xanh.
