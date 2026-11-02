# DEV.ONE Secure Live - kế hoạch triển khai v2

Cập nhật 02/11/2026, giờ Việt Nam (UTC+07). Trạng thái: POC native LAN và ghi SSD trên Air; chưa phải hệ thống production. Bản này thay kế hoạch ngày 30/10/2026 và là nguồn nội dung của PDF v2. Tên tệp cũ được giữ để các liên kết tiếp tục hoạt động.

## 1. Quyết định hiện hành và phạm vi

Mục tiêu sản phẩm tiếp tục là một camera 720p, không âm thanh, website riêng tư cho người xem Lào và Việt Nam, quản lý người dùng/quyền, live, bật/tắt ghi và xem lại. Tối đa 200 phiên WebRTC là mục tiêu cần kiểm thử, chưa là năng lực đã đạt.

- Mac mini là máy phát triển duy nhất: `/Volumes/Developer/Projects/camera`. Codex trực tiếp triển khai, review và kiểm thử theo dev-flow.
- MacBook Air là runtime tại điểm camera: `/Users/macbook/Developer/camera`. Air nhận RTSP, phục vụ WebRTC cục bộ và ghi SSD. Đây là thay đổi đã được chọn so với thiết kế ban đầu không có máy tính onsite.
- Camera vào PoE 1 của switch; UPLINK 5 vào LAN bộ phát Wi-Fi. Mini và Air cùng Wi-Fi. ER605 không tham gia tuyến hiện tại.
- LAN đã được người dùng chấp nhận trực quan theo mục tiêu một giây và miễn đo quang học: `USER-ACCEPTED/VISUAL`. Không có p95 đã đo. Không yêu cầu đo lại LAN trong phạm vi này.
- Giữ phạm vi v1: một camera; không thêm app mobile riêng, multi-camera, chat, thanh toán, AI, DRM hoặc Kubernetes.
- Mục tiêu ghi server trong thiết kế cũ chưa triển khai. Ghi Air hiện tại không tự động thay thế quyết định nơi lưu và cung cấp playback cho website.

Tài liệu vận hành chi tiết: [bàn giao Mini](HANDOFF_MAC_MINI.md), [checkpoint](docs/implementation-status.md), [dịch vụ ghi Air](docs/air-recording-service.md). Bản gốc 30/10 và hướng dẫn tuyến cũ đã bỏ khỏi checkout theo yêu cầu người dùng; lịch sử Git dùng để truy vết.

## 2. Kiến trúc và thiết bị thực tế

Tuyến đang chạy: **Camera RTSP/TCP → MediaMTX v1.21.3 trên Air → WebRTC cục bộ + fMP4 SSD + playback cục bộ có xác thực**. Video không tái mã hóa. Mini chỉ phát triển và quản trị qua SSH LAN đã được duyệt.

| Thành phần | Hiện trạng đã ghi nhận |
|---|---|
| Camera | Hikvision DS-2CD2643G2-LIZS2UHUN; V5.7.23 build 260320; static 192.168.1.64/24, DHCP=false |
| Profile kênh 101 | H.264 Baseline, 1280×720, 25 fps, CBR 2048 Kbps, GOP 25; không audio, H264+/SVC tắt |
| Air | Air 2017 Intel, macOS 14.8.9/Sonoma qua OpenCore; Perl core; MediaMTX v1.21.3 |
| Mini | macOS 26.7/arm64; Python 3.9+ stdlib; không chạy binary FFprobe Intel của Air |
| Switch / AP | Hikvision DS-3E1505P-EI/M; AP/model ISP và vị trí thực địa Lào còn cần xác định |
| ER605 / NVR | Không nằm trong tuyến đang chạy; không tự kết nối lại để khớp kế hoạch cũ |

Listener Air chỉ loopback 127.0.0.1: RTSP 8554/TCP, WebRTC 8889/TCP và 8189/UDP, Control API 9997/TCP, playback 9996/TCP. Chưa mở listener LAN/public. Playback dùng tài khoản riêng, không dùng lại mật khẩu camera.

Hướng tiếp theo đề xuất: **Air → outbound mã hóa/xác thực → MediaMTX trên server được duyệt → WebRTC tới người xem**. Web/API quản lý quyền; không chuyển từng frame live qua backend web. Đây là kiến trúc dự kiến, chưa có VPS, publisher, HTTPS public hoặc VPN bảo trì đang hoạt động.

Nguồn MediaMTX đúng tag v1.21.3 có `forward` native, gồm WHIP/HTTPS và RTSPS. Ưu tiên POC khả năng sẵn có trước khi thêm FFmpeg/agent mới; giao thức cuối cùng phụ thuộc kiểm thử mạng. [Schema v1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/mediamtx.yml). Khả năng trong source không phải bằng chứng WAN đã chạy.

## 3. Bằng chứng và giới hạn tại ngày cập nhật

Snapshot đọc qua SSH strict host trust lúc **17:55:53+07 ngày 02/11/2026**; chỉ lấy các trường trạng thái allowlist, không restart hay đổi cấu hình.

| Quan sát trực tiếp | Kết quả |
|---|---|
| Supervisor | running / ok; status cập nhật 17:55:46+07 |
| Nguồn | ready=true; H264; readyTime 16:32:53.622655+07 |
| Dữ liệu nhận | 1.250.917.160 byte; tăng so với lần đọc 17:51 |
| Ghi hình | record=true; recordingPaused=false; authLatchActive=false |
| SSD trống | 99.196.829.696 byte, khoảng 92,4 GiB; reserve 15 GiB |
| Retention / segment | 1 ngày / 1 phút; chưa đủ 24 giờ dữ liệu của phiên này |

Bằng chứng đã lưu trong checkpoint: mẫu MP4 thật 65,0329 giây / 1.628 frames, 25,033 fps, 0 B-frame, 0 audio; GOP min 2, median/max 25. Safari Air có hình theo xác nhận người dùng. Playback không auth trả 401/có auth trả 200; native hot-pause giữ nguồn và WebRTC. Retention fixture xóa tệp 25h, giữ tệp 1h. Những kết quả này không thay thế endurance hay kiểm mạng thực địa.

Tại HEAD `d09e23e31406a4c5c2fdae7d2ee1eda7f51e4cf3`, lượt khảo sát cùng chat đã đọc 25 tệp văn bản (4.778 dòng) và PDF gốc 14 trang; loại trừ credential, video, binary, ảnh thiết bị, cache và runtime riêng tư. `make check` trên Mini PASS 22 tests (1,860s); Perl syntax và 14 top-level checks (13 subtests, 75 assertions bên trong) trên Air PASS; plist lint PASS. Source không đổi trong lần cập nhật tài liệu này, không chạy lại pipeline camera.

Chưa đạt: endurance 24h, retention dữ liệu thật đủ tuổi, tự khởi động sau reboot/logout, phục hồi nguồn/WAN, publisher/server, mobile WAN, RBAC và tải 200 peers. Có backup camera mã hóa trước chỉnh profile; chưa thử restore.

## 4. Bản đồ code và khoảng trống cần xử lý

| Đường dẫn | Vai trò / giới hạn |
|---|---|
| `scripts/poc.py` | Validate JSON, render YAML POC loopback, cài native ghim hash, probe/analyze, bounded run/smoke; Python stdlib |
| `scripts/air_recording_supervisor.pl` | Private files → hash/lock/disk guards → owned child → log/status/API pause; Perl core |
| `infra/macos/recording-agent.plist.example` | Caffeinate + supervisor, GUI session-only, KeepAlive=false |
| `tests/test_poc.py` | Config, hash, codec, redaction, subprocess fixtures |
| `tests/test_air_recording_supervisor.t` | Fake workspace/child; lock, auth latch, disk pause, cleanup và log guards |
| `infra/mediamtx` | Template POC loopback; khác cấu hình recording private đang chạy |

Chưa có `apps/web`, `apps/api`, `packages/shared`, database/schema, CI ứng dụng hay bộ load WebRTC. Next.js + Fastify + PostgreSQL + Caddy là stack dự kiến kế thừa kế hoạch, chưa phải dependency đã cài hoặc được mặc nhiên duyệt.

Ba việc kỹ thuật cần làm trước khi bật outbound:

1. Tách lỗi camera và đích publisher: dòng giả theo dạng log native `[path live] [WHIPS dest 0 1234abcd] bad status code: 401 (Unauthorized)` đang bị classifier trả `camera_auth_failure`. Đây là bằng chứng synthetic trên hàm hiện tại; chưa có sự cố publisher thật. Cần regression test để lỗi đích không kích hoạt camera latch/dừng ghi cục bộ, trong khi camera 401/403 vẫn fail-stop.
2. Bổ sung che publisher token/credential và kiểm log theo giao thức chọn. Loader hiện thu secrets camera/playback và RTSP URL; chưa có kiểm thử token WHIP. Không đưa token vào URL/log/argv.
3. Tạo cấu hình recording/publisher tái tạo được từ private inputs và kiểm tra an toàn. `poc.py configure` hiện sinh POC tắt recording/playback; không dùng nó ghi đè private recording config đang chạy.

## 5. Thứ tự triển khai mới và cổng nghiệm thu

| Gói | Thực hiện | Điều kiện qua cổng |
|---|---|---|
| P0 - chuẩn bị outbound | Sửa classifier và redaction; renderer recording/publisher; test cô lập trên Mini và Perl Air | Camera auth vẫn latch; lỗi publisher không dừng local record; không lộ secrets; chưa chạm phiên thật |
| P1 - độ bền và phục hồi Air | Theo dõi phiên 24h/retention; chuẩn bị cơ chế auto-start có latch, giới hạn retry và rollback | Evidence đủ thời gian; kiểm recovery có giám sát sau khi cơ chế persistent được duyệt |
| P2 - WAN POC | Chốt VPS/domain/ngân sách; thử native forward có mã hóa/xác thực và player HTTPS hạn chế truy cập | Server nhận video thật ≥2h; local recording tiếp tục; mất WAN 60s rồi hồi phục, 3 lần; ghi thời gian recovery |
| P3 - web private | Chốt contracts/schema/dependencies; auth, MFA admin, RBAC, quota/kick, player, recording/playback, audit | Không bypass quyền; 201 yêu cầu không vượt 200 suất; revoke cắt media thật; ghi/playback đúng chính sách |
| P4 - tải và thực địa | Ramp 1/20/50/100/150/200; soak 8h; mobile, playback, backup/rollback và mạng Lào/VN | Peer thật nhận media, số liệu QoE/tài nguyên/egress; nghiệm thu theo từng mạng/thiết bị; restore thực tế |

Đường găng: **P0 → P2 → P3 → P4**. Quan sát P1 và chuẩn bị quyết định hạ tầng chạy song song về lịch; recovery P1 phải đạt trước bàn giao vận hành. Không cần đợi 24h mới viết tests/config trong workspace. Chỉ mở website production sau khi tuyến server có bằng chứng phù hợp; có thể chuẩn bị UX, DTO dự thảo và test cases trước đó.

Nếu phiên nguồn không gián đoạn, mốc đủ 24h là khoảng 16:33 ngày 03/11; kiểm retention sau khoảng 17:05. Đây là mốc kiểm tra dự kiến, không tự động thành PASS: phải kiểm khoảng trống, tuổi tệp, playback mẫu đầu/giữa/cuối, dung lượng và log đã che bí mật. Cleaner có chu kỳ tối đa khoảng 30 phút; file từ trial cũ không chứng minh thời lượng phiên hiện tại.

Không gián đoạn phiên đang đo để triển khai P0/P2 hoặc thử reboot. Chuẩn bị và review trước, áp dụng vào cửa sổ thay đổi được duyệt. POC Internet có thể lập kế hoạch 1-3 ngày kỹ thuật khi access/hạ tầng sẵn có; lịch v1 phải cập nhật sau P2 và chốt tải/playback/thực địa, không dùng ước lượng làm cam kết hoàn tất.

## 6. Các quyết định còn mở

| Quyết định | Cần chốt trước | Tác động |
|---|---|---|
| VPS, vùng đặt, domain và ngân sách traffic | P2 | Singapore là ứng viên; chọn theo đường mạng Lào/VN và quota egress |
| Giao thức publisher và tài khoản riêng | P2 | Thử WHIP/HTTPS hoặc RTSPS; auth/mã hóa, retry và firewall phải kiểm thực tế |
| Nơi lưu bản ghi cho website | P3 thiết kế playback | Air-only, server hoặc cả hai; không tự áp lại yêu cầu server cũ hay mặc định upload/backfill |
| Số giờ ghi, retention và backup trên server nếu có | Trước bật ghi/xóa server | Air hiện giữ 1 ngày; không suy ra retention server đã chốt |
| Auto-start và hỗ trợ onsite | P1 recovery | Login/FileVault/lid/power; cài persistent service cần quyền riêng |
| ISP/vị trí Lào, thiết bị/người thử | P2/P4 | Kết quả lab Việt Nam không thay nghiệm thu Lào |
| Phiên mỗi tài khoản, thời hạn login/media, số playback | P3/P4 | Schema, quota/revoke, tải và egress |
| Tiêu chí WAN latency/freeze và fallback | P2/P4 | Mục tiêu một giây tiếp tục là mục tiêu; miễn đo LAN không phải bằng chứng WAN |

Mô hình sizing theo profile 2,048 Mbps: một nguồn ghi khoảng 22,12 GB/ngày trước overhead; 200 viewers khoảng 471 Mbps nếu dự phòng 15%. Nếu duy trì 200 viewers 8h/ngày trong 30 ngày: khoảng 50,87 TB egress. Đây là phép tính thiết kế, chưa là usage đo hay báo giá; playback/TURN/retransmission/backup tính riêng. Không chọn VPS chỉ dựa vào vCPU/RAM.

Nơi phát lại phải được quyết định trước khi xây UI/DB recording. Air-only cần đường truy cập có quyền và xử lý offline; server recording tạo khoảng trống khi uplink mất; cả hai cần chính sách bản nào là nguồn chính và có/không đồng bộ lại. Hiện chưa có upload/backfill video.

## 7. Hợp đồng nghiệm thu cho phần còn lại

Các ngưỡng kế thừa dưới đây là mục tiêu lập kế hoạch; phải chốt ma trận môi trường trước nghiệm thu. Không nới ngưỡng âm thầm để đóng cổng.

- Live WAN: mục tiêu p95 ≤1.000 ms, hướng tới p50 ≤500 ms; startup p95 ≤2s, freeze ≤1%. Nếu chưa có phép đo phù hợp thì ghi PENDING/ước lượng, không dùng ping hoặc getStats thay glass-to-glass. Miễn đo LAN hiện hành vẫn giữ nguyên.
- Trình duyệt: Chrome desktop, Safari macOS, Safari iPhone và Chrome Android thật; mạng cố định/di động Lào và Việt Nam. Báo riêng direct UDP và relay/TURN nếu cần.
- Auth: quyền live/playback/download độc lập; cookie an toàn, CSRF/rate limit, Argon2id, MFA admin. Chưa chọn/pin dependency production. Auth unavailable phải từ chối phiên mới.
- Phiên: reservation và media session tính trong quota; chống tái sử dụng token vượt quota; mapping session ID được kiểm trên MediaMTX thật trước chốt schema. Disable/logout/kick cắt media trong mục tiêu ≤5s khi hệ thống khỏe, có retry/reconcile khi lỗi.
- Recording: desired/observed state, idempotency, reconcile sau restart; bật/tắt ghi không làm dừng live. Playback proxy kiểm quyền, seek/range/cancel và backpressure; không buffer toàn bộ video vào RAM. UTC nội bộ, hiển thị Asia/Vientiane.
- Tải: 200 WebRTC peers thật trong 8h cùng ghi và tải playback đã chốt; kiểm bytes/frames tiến triển, không OOM/restart/rò phiên. Không dùng HTTP requests làm bằng chứng tải media.
- Vận hành: recovery nguồn/WAN, cảnh báo disk/offline, kênh bảo trì quyền hẹp, backup/restore và rollback. Media không restart chỉ vì deploy UI; chưa có cam kết HA.

Mỗi báo cáo ghi thời gian/múi giờ, commit/version/config hash, máy chạy, môi trường, command, raw evidence private và kết luận có giới hạn. Các mã CODEC-01/LAT-01/NET-01/NET-02/WEB-01..04/REC-01..03/PLAY-01/LOAD-01/SEC-01/OPS-01 được giữ để truy vết; NET-01/02 nay kiểm tuyến Air outbound, không bắt buộc ER605/WireGuard.

## 8. Quy tắc thực hiện và bàn giao

Giữ Air cắm nguồn, mở nắp, đăng nhập. Service `com.devone.camera.air-recording-supervisor` là GUI session-only, KeepAlive=false; chưa tự phục hồi sau logout/reboot. Không tự cài LaunchDaemon/login item, đổi FileVault/sleep hoặc gỡ auth latch. Low/unknown disk phải pause ghi, pause thất bại dừng owned child; không tự xóa video ngoài native retention.

SSH hiện được duyệt từ Mini tới `macbook@192.168.1.12`, trust/key riêng trong project, giới hạn nguồn Mini 192.168.1.8. IP là snapshot; không nới trust/quyền khi gặp lỗi. Credential/runtime ngoài Git, thư mục 0700 và file 0600; không xuất raw config/API config dump, key, password hay environment.

Giữ thứ tự mạng Mini Ethernet → Thunderbolt Bridge → Wi-Fi; không thêm alias/host route hoặc chạy helper mạng đã vô hiệu hóa. Lỗi restart SOCD/iBoot trước đây chưa xác định nguyên nhân; không dùng khôi phục priority làm bằng chứng đã sửa lỗi hệ thống.

Lệnh kiểm phần mềm đã có (fixtures, không phải nghiệm thu WAN):

- Mini, thư mục repo: `make check`.
- Air, thư mục workspace Air: `/usr/bin/perl -c scripts/air_recording_supervisor.pl`.
- Air, cùng workspace: `/usr/bin/perl tests/test_air_recording_supervisor.t`.
- Mini: `plutil -lint infra/macos/recording-agent.plist.example` và `git diff --check`.

Cập nhật tài liệu không cấp quyền triển khai. Hạ tầng/chi phí, dependency production, schema/public API, credential mới, listener LAN/public, persistent access, push/deploy và thao tác phá hủy cần quyền rõ ràng. Không phục hồi Antigravity/agy/bridge. Không cài Python/CLT trên Air hoặc chạy FFprobe Intel trên Mini.

Bước thực hiện kế tiếp cụ thể là **P0: classifier + redaction publisher + cấu hình tái tạo được**, với regression tests và diff review; quan sát P1 song song. Trước áp dụng runtime cần cửa sổ thay đổi và quyền tương ứng, đồng thời bảo toàn bằng chứng phiên ghi hiện có.

Nguồn đối chiếu: [MediaMTX forward](https://mediamtx.org/docs/features/forward), [schema tag v1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/mediamtx.yml), [forward log context](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/forward/dest_handler.go), [cleaner tag v1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/recordcleaner/cleaner.go). Các nguồn này đã được đối chiếu trong phiên khảo sát; xác minh lại nếu đổi version.
