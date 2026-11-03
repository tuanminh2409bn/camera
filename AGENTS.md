# DEV.ONE Secure Live — hướng dẫn làm việc

## Bắt đầu chat mới

- Đọc `HANDOFF_MAC_MINI.md`, `docs/implementation-status.md` và `docs/air-recording-service.md` trước khi tiếp tục. Kiểm tra HEAD/working tree thực tế; các PID, IP, dung lượng và trạng thái trong tài liệu là snapshot.
- Mac mini là máy phát triển duy nhất, checkout `/Volumes/Developer/Projects/camera`. MacBook Air là máy chạy MediaMTX/ghi hình tại điểm camera, workspace `/Users/macbook/Developer/camera`; không nhầm hai máy khi chạy lệnh.
- Codex tự triển khai, review và kiểm thử trực tiếp theo `dev-flow`. Không dùng Antigravity, `agy` hoặc bridge/worker cũ. Không tự phục hồi những công cụ đã gỡ.
- Các yêu cầu hiện tại thay thế hướng bàn giao và các tuyến đấu nối cũ. Kế hoạch Markdown và PDF tại root đã cập nhật v2 ngày 02/11/2026; bản gốc 30/10 và các runbook tuyến cũ đã bỏ khỏi checkout theo yêu cầu người dùng; truy vết bằng lịch sử Git. Đọc kế hoạch v2 cùng bàn giao/checkpoint; không dùng bản lịch sử để triển khai.

## Tuyến và phạm vi hiện tại

- Camera Hikvision `DS-2CD2643G2-LIZS2UHUN`, firmware `V5.7.23 build 260320`, IP tĩnh `192.168.1.64/24`, DHCP=false.
- Camera → PoE 1 của switch; switch UPLINK 5 → LAN bộ phát Wi-Fi. Mini và Air cùng mạng Wi-Fi. ER605 không tham gia tuyến hiện tại; không nối lại hoặc đổi camera DHCP để khớp tài liệu cũ.
- Kênh101: H.264 Baseline, 1280×720, 25 fps, CBR2048Kbps, GOP25, H264+/SVC tắt. Ngày03/11 đã bật AAC16kHz/mono; video readback giữ nguyên. VPS FFmpeg copy H264/chuyển AAC→Opus cho WebRTC qua RTSP chỉ127.0.0.1:18555. Người dùng đã xác nhận nghe cả live và bản ghi mới. Full backup thiết bị trước chỉnh vẫn chưa kiểm restore.
- Người dùng đã chấp nhận tốc độ WebRTC bằng mắt theo mục tiêu một giây và miễn bài đo quang học: ghi `USER-ACCEPTED/VISUAL`, không ghi p95 đã đo hoặc yêu cầu quay slow-motion lại trong phạm vi này.
- Ngày 03/11 người dùng đã duyệt triển khai bản đầu lên DigitalOcean SGP1 và `lao6789.com`, gồm HTTPS, Admin/RBAC và đường hầm bảo mật Air → VPS. Đọc checkpoint v1 để phân biệt dịch vụ đã chạy với những bước nghiệm thu còn thiếu. Người dùng đã chấp nhận miễn bài tải200peers/8giờ (`USER-ACCEPTED/WAIVED`); không yêu cầu thử lại hoặc ghi thành benchmark đã đo. VPN bảo trì và TURN chưa được xác nhận. Hạ tầng/cost mới, dependency mới ngoài phạm vi duyệt, thay schema/public API hoặc mở thêm listener cần quyền riêng.

## Giữ phiên ghi trên Air

- Ngày 03/11/2026 lúc10:27+07, người dùng yêu cầu kết thúc bài thử và đã tắt **ghi mới**: `recording_intent.desired=false`, native `record=false`. Supervisor/MediaMTX, live và playback vẫn chạy. Không tự bật lại ghi. Người dùng chấp nhận kết thúc sớm bài dự kiến24h; dữ liệu thực liên tục17h54m08,786s, ghi `USER-ACCEPTED`, không ghi đã đo đủ24h và không yêu cầu chạy lại phần thời gian được miễn trong phạm vi này.
- Ngày03/11 lúc12:39+07 đã cài3LaunchAgent tại `/Users/macbook/Library/LaunchAgents/` theo quyền người dùng. Supervisor label `com.devone.camera.air-recording-supervisor` chạy `.local/air-autostart-runtime/air_login_supervisor.pl`; `KeepAlive.SuccessfulExit=false`, throttle60s. Native và tunnel đã kiểm tự phục hồi trong GUI session, chưa thử logout/reboot thật. Đọc `docs/air-autostart.md` và checkpoint; các mô tả session-only/KeepAlive=false cũ là snapshot trước triển khai này.
- Managed entry point phải bắt đầu record=false trước native exec; chỉ bật theo intent/safety hợp lệ. Sau bài ghi thử âm thanh30giây được duyệt lúc14:33 ngày03/11: desired=false/revision3, native=false và mọi record flag trên đĩa=false. Người dùng đã miễn phần thời gian bài24h còn thiếu và bài tải200; không tự bật ghi hoặc yêu cầu chạy lại. Auto-start cần Air bật/mở nắp/cắm nguồn và đăng nhập macOS; không tự đổi FileVault/auto-login hay reboot/logout Air.
- SSH operator VPS đã khôi phục bằng khóa mới `.local/ssh/server-operator/id_ed25519_recovery_20261103`; host trust/known_hosts cũ giữ nguyên, khóa cũ còn nguyên. User tự reset root/đổi password và tự thêm public key qua Recovery Console. `/usr/bin/ssh -o UseKeychain=yes -o IdentityAgent=none` với key mới và strict known_hosts đã PASS, không cần đọc/hiện passphrase. Không dùng khóa cũ đang quên passphrase hoặc tự mở password SSH; password/kbd-interactive vẫn tắt.
- Giữ Air cắm nguồn, mở nắp và đăng nhập. Đọc `status.json`/API trước khi thao tác; không dùng PID chép từ tài liệu để signal và không khởi động native instance thứ hai.
- Ghi `.local/recordings/live/`, fMP4, part1s/segment1m, retention1d. Native cleaner có thể dọn trễ khoảng30 phút sau mốc24h; wrapper không tự xóa video. Reserve15GiB; lỗi/thiếu dung lượng sẽ pause ghi, pause thất bại thì dừng child.
- Camera auth401/403 phải dừng và giữ `auth-stop.latch`, không thử lặp. Playback HTTP401 là challenge cục bộ, không phải lỗi mật khẩu camera. Không tự gỡ latch khi chưa review nguyên nhân.
- Listener Air chỉ127.0.0.1: RTSP8554, WebRTC8889/UDP8189, API9997, playback9996 và gateway web9900. Playback có tài khoản riêng; Admin website là tài khoản độc lập trên VPS.
- SSH đã được duyệt qua LAN tới `macbook@192.168.1.12`, key/trust riêng tại `.local/ssh/air-poc` trên Mini. Key bị giới hạn nguồn Mini `192.168.1.8`; không mở rộng quyền hoặc đổi trust/host key khi gặp lỗi.
- Gateway và tunnel dùng hai LaunchAgent `com.devone.camera.web-gateway` và `com.devone.camera.server-tunnel`; Perl gateway hiện chạy từ `.local/air-autostart-runtime`, SSH config/key vẫn `.local/ssh/server-tunnel`. Runtime `.local/web-gateway-runtime` và plist project cũ chỉ giữ để rollback, không bootstrap duplicate. Khi thay job cùng label: đọc PID hiện tại, bootout rồi đợi job và tiến trình cũ thoát hết trước bootstrap; không chỉ chờ lệnh bootout trả về. Firewall VPS vẫn chỉ cho SSH từ IP công cộng nơi làm việc; đổi IP có thể ngắt tunnel. Chưa kiểm logout/reboot hoặc mất WAN thật.

## Sao lưu metadata định kỳ

- Đã được duyệt/cài FFmpeg từ Ubuntu trên VPS và GnuPG từ Homebrew trên Mini; không nâng gói hoặc mở thêm public listener. Release hiện hành `/opt/devone/releases/20261103T082215Z` có audio và giám sát Admin; xem checkpoint cho hash/gate. Không tự bật ghi sau thử.
- VPS `devone-backup.timer` mã hóa DB+3cấu hình hằng ngày02:15 Asia/Ho_Chi_Minh, giữ14ngày. Chỉ public key GPG trên VPS; private key có passphrase do user tự đặt giữ trên Mini. Đã restore chính bản lưu vào DB tạm riêng, kiểm MFA; không restore đè DB thật.
- Mini LaunchAgent `com.camera.metadata-backup` lấy ciphertext lúc đăng nhập/mỗi3600giây, giữ30ngày trong `~/Library/Application Support/CameraBackup/archives`. Runtime/SSH key riêng cũng ở đây, tránh TCC chặn ổ Developer. Key chỉ list/stream ciphertext, restrict/no shell/no forward/from IP nơi làm việc; user đã duyệt rõ credential này. Không đổi trust hoặc mở rộng quyền khi lỗi IP/SSH.
- Backup cũ `.local/production-backups/camera-*.tar.gz.gpg` và các khóa cũ giữ nguyên. Chỉ prune tên metadata mới; không video trong backup. Đọc [runbook](docs/metadata-backup.md) trước phục hồi/xoay khóa.

## Giám sát và vận hành

- User chọn chỉ hiển thị cảnh báo trên Admin trước, không Telegram/email; xác nhận tiếp tục **giữ tắt ghi** khi vận hành. Không tạo credential/kênh gửi thông báo hoặc bật ghi từ yêu cầu đưa vào hoạt động chung.
- `devone-monitor.timer` đọc API/Air/media/HTTPS/disk/backup mỗi60s, xác nhận lỗi3mẫu/phục hồi2mẫu. Snapshot allowlist `/var/lib/devone-monitor/status.json`0600 ownerdevone; state/lock root0600, parent root:devone0710 chỉ cho API đi xuyên để đọc snapshot. Không mở listener hoặc sửa schema DB; `/api/admin/service-status` giữ fields cũ và thêm operations chỉ Admin. Stale180s/future60s/mode/symlink/schema sai đều không báo xanh; UI timeout8s.
- Traffic là counter từ lúc monitor bắt đầu, không là billing/quota của DigitalOcean. Không hứa phí từ số này. Monitor nằm cùng VPS; khi VPS hỏng toàn bộ, không có cảnh báo ra ngoài và Admin không mở được. Đọc [runbook vận hành](docs/operations.md).
- User đã đồng ý tự thao tác reboot/đăng nhập Air và Wi-Fi riêng Air theo từng bước. Đây là quyền handoff cho người dùng thực hiện trong cửa sổ hiện tại, không là quyền cho agent tự reboot/logout/đổi mạng máy khác. Lưu boot time/status/hash trước và sau; chỉ ghi PASS khi có bằng chứng thật. Không chạy lại tải200/endurance/optical đã miễn.
- Cửa sổ03/11 đã kiểm xong: Air reboot thật/đăng nhập và Wi-Fi riêng Air tắt/bật đều PASS; boot time mới15:23:38,3jobs chạy/1native, hash không đổi, VPS H264+Opus, playback H264+AAC, intent=false/revision3. User xác nhận điện thoại “đều tốt” theo hướng dẫn4G/5G, chưa nêu model/browser. Không yêu cầu lặp lại các phần đã nghiệm thu; các dòng “chưa reboot” ở snapshot cũ là lịch sử. Quyền cửa sổ này không tự áp dụng cho reboot/mất mạng tương lai.

## Mạng và sự cố Mini

- Theo yêu cầu mới, thứ tự gốc đã được người dùng lưu và Codex xác minh: **Ethernet → Thunderbolt Bridge → Wi-Fi**. Ethernet hiện inactive/DHCP, default route vẫn qua Wi-Fi en1. Không tự chuyển lại Wi-Fi-first.
- Không thêm IP phụ/host route hoặc chạy lại helper mạng cũ. `.local/check-mac-camera.py` phải tiếp tục không tồn tại; bản `.disabled.txt` chỉ lưu để tra cứu.
- Người dùng từng gặp restart khi chạy helper. Log có `SOCD report detected: (iBoot async abort)`; chưa xác định nguyên nhân. Khôi phục thứ tự mạng không chứng minh đã sửa được lỗi hệ thống. Không tự reboot/update macOS, chẩn đoán stress, đổi WAN/router/firmware hoặc flush route.

## Source, công cụ và bí mật

- `scripts/poc.py`: Python3.9+ stdlib, config/probe/analyze/installer/runtime có giới hạn. MediaMTX ghim v1.21.3; supervisor dùng Perl core của Air. Không tự cài Python/CLT trên Air.
- FFprobe9.0.2 Intel chỉ được duyệt trong project Air. Không chạy binary Intel này trên Mini hoặc cài công cụ hệ thống ngầm.
- `.local`/runtime0700, cấu hình và credential0600. Không in password, RTSP URL có credential, private key, raw config/API config dump hoặc environment. Chỉ xuất các field allowlist đã redaction.
- Không commit runtime, video, backup cấu hình thiết bị, ảnh tem, mật khẩu hoặc log riêng tư. Các bản clone mới không có credential/SSH key; người dùng nhập trực tiếp trên máy khi cần.
- Giữ thay đổi ngoài phạm vi. Push/merge/deploy cần quyền; phiên 03/11 đã cho phép triển khai bản đầu được nêu trong checkpoint, không tự coi đó là quyền cho thay đổi hạ tầng hoặc phát hành khác.

## Kiểm chứng

- Software checks trên Mini: `make check` (compileall, CLI help, Python unittest); các bài dùng fixture và child giả. Không chạy lại pipeline camera/native trên Mini chỉ để bàn giao.
- Supervisor trên Air: `/usr/bin/perl -c scripts/air_recording_supervisor.pl` và `/usr/bin/perl tests/test_air_recording_supervisor.t`; dùng fake workspace/child, không đổi phiên ghi thật.
- Không coi unit/synthetic là bằng chứng codec, latency, WAN hay endurance. Chỉ ghi PASS cho cổng có dữ liệu phù hợp; ghi rõ máy thực thi và thời điểm.
- Trước công bố: kiểm tra diff, Markdown links, plist, hash source, file bị ignore và secret scan; ghi lệnh/kết quả trong checkpoint. Không làm yếu gate/tests để lấy kết quả xanh.
