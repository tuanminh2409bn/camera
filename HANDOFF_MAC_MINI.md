# Bàn giao để tiếp tục trên Mac mini

Cập nhật 02/11/2026, giờ Việt Nam. Đây là điểm bắt đầu cho chat mới. Phát triển trên Mac mini; Air là runtime onsite, không chuyển quy trình phát triển sang máy khác.

## 1. Máy và trạng thái cần giữ

| Thành phần | Hiện trạng |
|---|---|
| Mac mini | macOS26.7/arm64; checkout `/Volumes/Developer/Projects/camera`; Codex triển khai trực tiếp |
| MacBook Air | Air2017 Intel, macOS14.8.9/Sonoma qua OpenCore; workspace `/Users/macbook/Developer/camera` |
| Camera | Hikvision DS-2CD2643G2-LIZS2UHUN, firmware V5.7.23 build260320; Activated, static192.168.1.64/24 |
| Tuyến LAN | Camera PoE1 → switch UPLINK5 → LAN bộ phát Wi-Fi; Mini/Air dùng cùng Wi-Fi; ER605 không nằm trong tuyến |
| Phiên ghi | Service `com.devone.camera.air-recording-supervisor`, bắt đầu16:32:53+07 ngày 02/11; kiểm tra lại trạng thái trước thao tác |

Đã kiểm tra lại lúc 17:27:39+07: source ready/record=true, supervisor running, không auth latch/pause;61 tệp ghi,914.709.916byte, SSD trống99.648.942.080byte (~92,8GiB). Chỉ một native PID sở hữu cổng loopback; đây là snapshot, không phải số liệu24h. Không signal theo PID trong tài liệu.

Air cần cắm sạc, mở nắp và còn đăng nhập. Service hiện bootstrap từ project, KeepAlive=false, chưa tự chạy lại sau logout/reboot. Không cài daemon, login item hoặc sửa FileVault/sleep nếu chưa có quyền mới.

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
