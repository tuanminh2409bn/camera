# Bàn giao để tiếp tục trên Mac mini

**Bàn giao vận hành03/11:** release `/opt/devone/releases/20261103T082215Z`, Admin có12kiểm tra và cảnh báo chỉ tại Admin theo lựa chọn user. Đã kiểm reboot/đăng nhập Air và tắt/bật Wi-Fi riêng Air thật; dịch vụ tự phục hồi, không bật thủ công. User xác nhận điện thoại live/tiếng/xem lại tốt; chưa rõ model/browser. Ghi mới tiếp tục tắt, desired=false/revision3. Code đã chốt local trên nhánh `tuanminh/secure-live-v1` tới `a113fc9` cùng các commit trước; tài liệu bàn giao được commit kế tiếp, chưa push. Đọc [vận hành](docs/operations.md) và phần cuối [checkpoint](docs/v1-implementation.md). Các mốc “chưa reboot/chưa mobile/chưa commit” phía dưới là lịch sử. Không tự lặp bài hoặc bật ghi.

**Hiện hành03/11,14:40+07:** đã phát hành web/audio H264+Opus, bản ghi AAC; người dùng xác nhận nghe được live và bản ghi mới. Sau thử30giây: ghi mới=false/revision3. VPS release `/opt/devone/releases/20261103T074500Z`. Backup mã hóa VPS02:15/14ngày và Mini lúc đăng nhập/mỗi giờ/30ngày đã chạy; bản lưu thật restore DB tạm/MFA PASS, Mini agent exit0 bằng key chỉ tải ciphertext. Đọc [checkpoint](docs/v1-implementation.md) và [backup](docs/metadata-backup.md). Các trạng thái mốc cũ phía dưới là lịch sử. Không bật ghi lại hoặc yêu cầu chạy lại các bài đã miễn.

**Vận hành03/11,12:45+07:** SSH VPS đã khôi phục bằng key mới `id_ed25519_recovery_20261103` (cùng thư mục operator, known_hosts cũ; dùng `/usr/bin/ssh -o UseKeychain=yes` được). Đã cài3LaunchAgent tự chạy sau đăng nhập Air và kiểm phục hồi native/tunnel thật; ghi mới vẫn=false,1065file/16.148.184.903byte không tăng. Đọc [runbook Air](docs/air-autostart.md) và checkpoint trước thao tác. User miễn bài tải200/8h (`USER-ACCEPTED/WAIVED`), không có benchmark; chưa đo logout/reboot/mất WAN thật, không tự thực hiện các bài đó.

**Kết thúc bài ghi 03/11 lúc10:27+07 theo yêu cầu:** ghi mới đã tắt, desired/observed đều false; source/supervisor/live/playback vẫn phục vụ. Phiên ghi chính từ16:32:53,740858 ngày02/11 đến10:27:02,527107 ngày03/11, dài17h54m08,786s. Người dùng chấp nhận kết thúc sớm bài dự kiến24h (`USER-ACCEPTED`); không mô tả thành đo đủ24h hoặc tự bật lại ghi. Xem [checkpoint](docs/v1-implementation.md) cho bằng chứng dừng và việc tiếp theo.

**Cập nhật 03/11/2026:** bản đầu đã được triển khai lên VPS DigitalOcean Singapore và `https://lao6789.com` theo quyền người dùng; Air nối ra VPS bằng tunnel riêng, phiên ghi hiện hữu không được khởi động lại. Các đoạn “chưa mua/chưa deploy” bên dưới là snapshot 02/11. Đọc [checkpoint v1](docs/v1-implementation.md) và [runbook](docs/web-deployment.md) để biết cấu hình, kiểm thử và các cổng nghiệm thu còn thiếu; không coi 200 người, endurance hoặc phục hồi sau reboot là đã đạt.

Cập nhật 02/11/2026, giờ Việt Nam. Đây là điểm bắt đầu cho chat mới. Phát triển trên Mac mini; Air là runtime onsite, không chuyển quy trình phát triển sang máy khác.

**Cập nhật web v1 trong phiên tối02/11:** xem [checkpoint](docs/v1-implementation.md) và [runbook web](docs/web-deployment.md) trước khi tiếp tục. Người dùng đã cho phép Next.js/Fastify/PostgreSQL/Caddy, dependency/schema/API. Các thay đổi đang local trên nhánh `tuanminh/secure-live-v1`, xuất phát từ HEAD `2619fd607718fc93170a76cd364d593863380d29`; chưa push/deploy. Không áp dụng kết luận “chưa có backend” của bản đồ POC bên dưới cho source mới. Không restart Air để đồng bộ source trong khi bài ghi24h chưa được kiểm xong.

## 1. Máy và trạng thái cần giữ

| Thành phần | Hiện trạng |
|---|---|
| Mac mini | macOS26.7/arm64; checkout `/Volumes/Developer/Projects/camera`; Codex triển khai trực tiếp |
| MacBook Air | Air2017 Intel, macOS14.8.9/Sonoma qua OpenCore; workspace `/Users/macbook/Developer/camera` |
| Camera | Hikvision DS-2CD2643G2-LIZS2UHUN, firmware V5.7.23 build260320; Activated, static192.168.1.64/24 |
| Tuyến LAN | Camera PoE1 → switch UPLINK5 → LAN bộ phát Wi-Fi; Mini/Air dùng cùng Wi-Fi; ER605 không nằm trong tuyến |
| Phiên ghi | Service `com.devone.camera.air-recording-supervisor`, bắt đầu16:32:53+07 ngày 02/11; kiểm tra lại trạng thái trước thao tác |

Đã kiểm tra lại lúc 17:27:39+07: source ready/record=true, supervisor running, không auth latch/pause;61 tệp ghi,914.709.916byte, SSD trống99.648.942.080byte (~92,8GiB). Chỉ một native PID sở hữu cổng loopback; đây là snapshot, không phải số liệu24h. Không signal theo PID trong tài liệu.

Air cần cắm sạc, mở nắp và đăng nhập. Snapshot02/11 dùng service session-only; hiện đã thay bằng3LaunchAgent trong `~/Library/LaunchAgents` theo quyền mới03/11, xem runbook ở đầu tài liệu. Không tự cài daemon trước đăng nhập hoặc sửa FileVault/sleep/auto-login.

Source đã review/kiểm thử tại commit `31da5701060406b02f4f3b45b4cdb781238c572b`; chat mới so sánh HEAD/working tree với mốc này và đọc diff mới trước khi sửa.

## 2. Bản đồ source và luồng dữ liệu

- `scripts/poc.py`: validate source JSON, tạo private YAML, cài MediaMTX ghim hash, chạy POC có thời hạn, probe/analyze codec và smoke. Python3.9+ stdlib, không có DB/backend web.
- `scripts/air_recording_supervisor.pl`: entry point session recording. Đọc private JSON/YAML → kiểm hash native binary/lock/SSD → spawn child trong workspace riêng → nhận log đã redaction → ghi status/log và theo dõi API pause. CLI chỉ nhận workspace/duration, không nhận password trong argv.
- `infra/macos/recording-agent.plist.example`: gọi caffeinate + Perl supervisor trong GUI session; template được render vào `.local/recording-service` trên Air.
- `tests/test_poc.py`: config/hash/codec/redaction/subprocess fixtures. `tests/test_air_recording_supervisor.t`: fake workspace/child cho lock, auth latch, disk pause, timeout/cleanup và log guards.
- Runtime thật: camera RTSP101/TCP → MediaMTX v1.21.3 → WebRTC loopback và fMP4 SSD → native playback có tài khoản riêng. Không encode lại video.
- Interface: RTSP8554, WebRTC8889/UDP8189, API9997, playback9996, tất cả127.0.0.1 trên Air. Không mở LAN/public hoặc đưa thông tin camera vào browser URL.
- `.local/mediamtx.poc.yml` do CLI POC sinh ra khác `.local/mediamtx.recording.poc.yml` đang chạy; không render đè recording config.

## 3. SSH và dữ liệu riêng tư

Mini hiện192.168.1.8, Air192.168.1.12. Key project chỉ cho phép từ192.168.1.8; nếu DHCP/IP thay đổi thì dừng và báo lỗi, không tự nới `authorized_keys`. Host ED25519 đã được người dùng đối chiếu: `SHA256:ampG5qxzLsnzmpgFoPeDVIqDbxxjtseaffRzjiWmMoQ`.

Kiểm tra trạng thái chỉ đọc từ Mini:

```sh
cd /Volumes/Developer/Projects/camera
ssh -T -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o GlobalKnownHostsFile=/dev/null \
  -o UserKnownHostsFile="$PWD/.local/ssh/air-poc/known_hosts" \
  -o ConnectTimeout=5 -i "$PWD/.local/ssh/air-poc/id_ed25519" \
  macbook@192.168.1.12 \
  'cat /Users/macbook/Developer/camera/.local/recording-service/status.json'
```

Các đường dẫn sau **không ở Git**; không cat/in ra chat hoặc đưa vào diff:

| Trên máy | File/dir | Vai trò |
|---|---|---|
| Mini | `.local/ssh/air-poc/` | Private SSH key và known_hosts riêng |
| Mini/Air | `.local/camera-source.json` | Credential camera thật,0600 |
| Air | `.local/mediamtx.recording.poc.yml` | Recording config có source URL,0600 |
| Air | `.local/recording-admin.json`, `.local/recording-admin.curl` | Tài khoản playback riêng,0600 |
| Air | `.local/recording-service/` | Plist private, status/log/lock,0700 |
| Air | `.local/recordings/live/` | Video rolling retention, file0600/dir0700 |
| Mini/Air | `.local/backups/camera-full-before-720p.bin` | Full backup mã hóa; người dùng giữ mật khẩu, chưa restore thử |
| Air | `.local/tools/` | MediaMTX v1.21.3 Intel và FFprobe9.0.2 project-only |

Bản clone mới chỉ có source/templates. Không giả định đã có credential/key/tool; yêu cầu người dùng nhập/lưu trực tiếp tại máy khi cần, không gửi password vào chat.

## 4. Những gì đã đạt

- HTTP web camera và RTSP chuẩn xem được qua Wi-Fi; Safari trên Air có hình WebRTC chuyển động theo xác nhận người dùng.
- Camera đã cấu hình H.264 Baseline 1280×720/25fps, CBR2048Kbps, GOP25, không âm thanh. Mẫu thật65,0329giây/1.628frames:25,033fps,0B/0audio,GOPmedian/max25,min2 → CODEC-01 PASS.
- Người dùng chấp nhận tốc độ bằng mắt theo mục tiêu1giây và miễn đo quang học: `USER-ACCEPTED/VISUAL`, không có p95 đã đo.
- Ghi/phát lại MP4 thật, playback401/200, hot-pause giữ nguồn/WebRTC; retention fixture xóa file25h và giữ1h. Dữ liệu thật không bị xóa trong bài fixture.
- Supervisor có hash pin, duplicate lock, redaction/rotation, auth fail-stop/latch, reserve15GiB, record-pause quaAPI và owned-process cleanup. Xem lệnh/kết quả kiểm thử trong checkpoint.
- Bản `dev-flow` trên Mini khớp 16/16 tệp commit caefff8 của dev-flow-macos; chính sách global vẫn yêu cầu Codex làm trực tiếp. Antigravity CLI/bridge và worker runtime đã gỡ.

## 5. Mạng Mini và lỗi cũ

Thứ tự gốc **Ethernet → Thunderbolt Bridge → Wi-Fi** đã được người dùng lưu trong System Settings và Codex đọc lại bằng `networksetup -listnetworkserviceorder`. Ethernet DHCP/inactive, default route en1, HTTPS GitHub200 sau thay đổi.

Không thêm alias/route, flush bảng route hoặc chạy lại `.local/check-mac-camera.py`; file này đã bị vô hiệu hóa. Hai panic report trước đó có `SOCD report detected: (iBoot async abort)`; chưa xác định nguyên nhân. Khôi phục priority không phải bằng chứng đã sửa được lỗi restart. Nếu sau này nối Ethernet vào router không có Internet, phải kiểm tra đường đi thực tế; không tự sắp xếp lại ưu tiên để che vấn đề tuyến đó.

## 6. Kiểm tra phần mềm và việc tiếp theo

Kế hoạch hiện hành là [v2 ngày 02/11](KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md); PDF root cũng đã cập nhật v2. Ưu tiên P0 (classifier lỗi publisher, che token, cấu hình recording/publisher tái tạo được), quan sát P1 song song, rồi P2 WAN → P3 web → P4 tải/thực địa. Bản gốc và các runbook tuyến cũ đã bỏ khỏi checkout; dùng lịch sử Git khi cần truy vết. Snapshot 17:27 bên trên là lịch sử; lần đọc mới 17:55 nằm trong checkpoint.

Trên Mini, `make check` = compileall + CLI help + Python unittest, không phải khởi động MediaMTX thật. Test supervisor cần Perl native Air:

```sh
/usr/bin/perl -c scripts/air_recording_supervisor.pl
/usr/bin/perl tests/test_air_recording_supervisor.t
```

Hai lệnh Perl chạy trên Air, trong workspace Air; các fixture không thay runtime đang ghi. Không tự cài Python/CLT trên Air hoặc chạy FFprobe Intel trên Mini. Không chạy `poc.py smoke/run/probe` lên camera chỉ để đọc handoff.

Ưu tiên cho phiên tiếp:

1. Đọc git/status và kiểm tra service Air bằng thao tác chỉ đọc; giữ phiên ghi đang hoạt động.
2. Theo dõi và ghi bằng chứng đủ24h, SSD và retention; không suy diễn từ phiên hiện tại thành endurance PASS.
3. Chuẩn bị phương án tự khởi động/phục hồi sau reboot để người dùng review trước khi cài thêm cơ chế persistent.
4. Chốt đường publisher outbound có xác thực/mã hóa từ Air tới server được duyệt, ngân sách/VPS và mạng thực Lào/VN. Không thuê hoặc deploy tự động.
5. Chỉ mở giai đoạn website Admin/RBAC/HTTPS sau khi có cổng mạng thật phù hợp; playback hiện tại chỉ cục bộ.

Prompt khởi động chat mới:

> Dùng dev-flow. Đọc AGENTS.md, HANDOFF_MAC_MINI.md, docs/implementation-status.md và docs/air-recording-service.md. Mac mini là máy phát triển, Air là runtime onsite đang ghi SSD24h. Kiểm tra HEAD/working tree và trạng thái Air chỉ đọc trước, giữ phiên ghi. Codex làm trực tiếp; không khôi phục Antigravity hoặc helper mạng cũ. Báo cổng nào đã có bằng chứng, rồi tiếp tục đúng phạm vi đã duyệt và công việc kế tiếp trong handoff.
