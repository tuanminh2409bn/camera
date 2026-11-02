# Trạng thái triển khai DEV.ONE Secure Live

Cập nhật 02/11/2026. Tài liệu này mô tả snapshot hiện tại, thay cho các hướng đấu nối/bàn giao trước đó. Mac mini là máy phát triển; Air tiếp tục chạy recording tại điểm camera. Đọc [bản bàn giao](../HANDOFF_MAC_MINI.md) khi mở chat mới.

## 1. Quyết định và tuyến hiện tại

- Phát triển tại `/Volumes/Developer/Projects/camera` trên Mac mini macOS26.7/arm64; Codex trực tiếp implement/review/verify. Đã gỡ Antigravity CLI/bridge, quy tắc delegation/model/quota và các worker runtime; source thay đổi chưa nhập về đã lưu private ngoài active workflow.
- Skill dev-flow đã đồng bộ đủ16/16file với commit `caefff8d7b82ec0f9facda875ef25c87bf55675e` từ `tuanminh2409bn/dev-flow-macos`; global rules riêng vẫn giữ. Không có cơ chế tự gọi lại worker.
- Camera → switch PoE → LAN bộ phát Wi-Fi; Mini/Air dùng cùng Wi-Fi. Camera192.168.1.64/24 static, Mini192.168.1.8, Air192.168.1.12 tại snapshot. ER605 không tham gia tuyến. Không cấu hình lại DHCP/IP để khớp các địa chỉ lịch sử.
- Mục tiêu người xem Lào/VN. LAN WebRTC được người dùng chấp nhận trực quan theo mục tiêu1giây và miễn bài đo optical. Ghi `USER-ACCEPTED/VISUAL`, không chuyển thành p95 đã đo. WAN/VPS/website Admin chưa triển khai.
- PDF và kế hoạch gốc giữ nguyên để truy vết; tuyến Air onsite hiện tại là thay đổi đã được người dùng chọn so với thiết kế gốc không Edge.

## 2. Snapshot Air mới nhất — 17:27:39+07 ngày 02/11

Đọc qua SSH strict host trust, không restart/update runtime và không xác thực camera thêm:

| Mục | Kết quả |
|---|---|
| Service | `com.devone.camera.air-recording-supervisor`, GUI session loaded/running |
| Source | Ready từ 16:32:53.622655+07; trackH264, bytesReceived824.990.680 |
| Recording | true, không pause, không auth latch |
| Video trên SSD |61tệp,914.709.916byte; mọi tệp0600 |
| SSD trống |99.648.942.080byte (~92,8GiB), reserve15GiB |
| Listener |Một native PID, chỉ127.0.0.1:8554/8889/9996/9997 vàUDP8189 |
| Launchd stdout/stderr |0byte tại snapshot |

Source readyTime giữ nguyên từ commissioning, đã khoảng55phút; chưa phải endurance24h. PID quan sát14372/14376 chỉ là dữ liệu lịch sử, không dùng để signal trong chat sau.

Service bootstrap từ `/Users/macbook/Developer/camera/.local/recording-service/recording-agent.plist`, không cài Library/LaunchAgents/daemon. KeepAlive=false; cần AC/lid-open/logged-in, chưa tự chạy lại sau logout/reboot. Caffeinate chỉ dành cho service, không đổi sleep/FileVault hệ thống.

## 3. Camera, backup và codec đã kiểm chứng

- Hikvision DS-2CD2643G2-LIZS2UHUN, firmwareV5.7.23 build260320. HTTP Digest và web đã thành công qua Wi-Fi; VLC và MediaMTX chuẩn trên Air nhận được RTSP. Những lỗi client/đường ER605 cũ không phải chẩn đoán mật khẩu hiện tại; không lặp lại thử sai để điều tra.
- Full backup mã hóa trước chỉnh720p:3.507.904byte, lưu riêng `.local/backups/camera-full-before-720p.bin` trên Mini/Air; SHA256 `15b59c9cdc7efb28e311578985305545eca73c2ff23152fcc59354ff0dd894c3`. Người dùng giữ mật khẩu mã hóa; chưa thử restore. Safari Air đã tải thành công; export từ IAB không trả được file.
- Kênh101 đã lưu và HTTP readback200: H.264 Baseline 1280×720, CBR2048Kbps, maxFrameRate raw2500, GOP25, audio=false, H264+/SVCoff; smoothness50. Bitrate preset2048 đã commit, không phải giá trị1536 nhập thử.
- Air FFprobe9.0.2 phân tích MP4 thật65,0329giây/1.628frames, exit0/stderr0. Existing analyzer offline PASS:25,033fps,0audio/0B,67I/1.561P,GOP66intervals,min2/median25/max25. Không khẳng định mọi khoảng GOP đều đúng25.
- FFprobe Intel project-only được người dùng duyệt; nguồn HTTPS Evermeet được FFmpeg giới thiệu. ZIP SHA256 `24a9c968cd4da72d99c7245e914b921815835eb6dff01d99868031aebaf1d439`; binary `a29f8c2e03553223a8b480b1a1f04c42f680c138fa952c20086718a075db38cb`. Kiểm CRC/architecture/hash trên Air; GPG signature publisher chưa verify. Không chạy Intel tool trên Mini hay cài system tool.

## 4. Ghi, phát lại và cơ chế giám sát

- Native MediaMTX v1.21.3 Intel binary SHA256 `2d21dd021fa7d0e667b24f8850555f29d718424c19d5ce9e18163a8b893034fd`; archiveSHA256 `8a8416ee2ff5d17d9366498b6d88b76ab6d3afcda50b6d7321ccddb349bdbaf2`.
- Ghi `.local/recordings/live`, fMP4 part1s/maxpart10M/segment1m/recordDeleteAfter1d. Dự kiến22,12GB/ngày ở2048Kbps trước overhead. Native cleaner chạy lúc start/theo chu kỳ tối đa30phút; video quá mốc24h có thể đợi chu kỳ dọn tiếp theo.
- Phiên thật180giây trước đổi profile:3file/~60.760KiB; playback không auth401/có auth200; MP4 thử10giây2.679.920byte. Người dùng xem được clip ghi sẵn bằng VLC trên Air.
- Profile720p có phiên native120giây, export MP4 mới65giây16.267.847byte. Sau bật service16:32, MP48giây từ chính interval của service tải được2.197.714byte/headerftyp; không lấy bằng chứng từ clip cũ.
- Hot-pause `PATCH /v3/config/paths/patch/live` record=false200, source vẫnready, readyTime/hai WebRTC reader identity không đổi và bytecounter tăng; record=true200 rồi dừng phiên thử sở hữu. Đây là kiểm cơ chế pause, không làm đầy SSD thật.
- Retention fixture riêng: bản sao file đặt mốc25h bị xóa,1h được giữ; bài không nối camera và không xóa bản ghi thật.
- Supervisor kiểm private mode/symlink, pin hash, flock chống trùng, log redaction/rotation5MiB+2bản, heartbeat10s, processgroup/cleanup có hạn và CWD/umask077. Loại overrideMTX_* khi spawn. Camera401/403 dừng trước retry native5giây và lưu auth-stop.latch. Low/unknown disk pause ghi quaAPI; không tự re-enable; pause không xác nhận thì dừng child.
- Playback riêng chỉ quyền playback/live, credential0600, không dùng lại camera password. Mọi listenerloopback; chưa có website Admin/RBAC hoặc truy cập từ Internet.

## 5. Kiểm tra phần mềm và nguồn

| Kiểm tra | Máy/kết quả |
|---|---|
| Python `make check` | PASS trên Mini: compileall, CLI help và22Python unittest (1,846s), không khởi động pipeline camera thật |
| Perl syntax và tests | PASS lần xác minh trước công bố trên Air: Perl syntax,14top-level/13subtests/75nested assertions, không warning |
| Mutation auth guard | Bản sao riêng đảo điều kiện auth khiến test fail đúng nhóm; bản gốc khôi phục/hash khớp |
| Native supervisor trial |25giây exit0, nguồnready/bytes tăng, playback401/200, duplicate invocation bị từ chối, kết thúc không còn listener |
| Plist |Template/rendered plist lintPASS; runtime session đã kiểm tra |
| Diff/docs/secret scan | PASS: diff/Markdown links/fences/plist, hash source và scan credential thực/private-key; runtime/ảnh/secret bịignore |

Snapshot source đã review/kiểm thử và lưu tại commit `31da5701060406b02f4f3b45b4cdb781238c572b`; các cập nhật bàn giao nằm trong commit tiếp theo trên main.

Source supervisor SHA256 `39123193766a16940ca08429370c6aa5f8f8f1e5d25cbb2d828997cbd61a3ede`; tests SHA256 `c1f75358d98aa00ae308f10b4542c4d6ad921e368acb88b2d8db67fc50b0c351`. CLI Python gốc và tests cũ không sửa. Những gate camera/network dùng bằng chứng riêng, không suy diễn từ fixture.

Lệnh nguồn:

```sh
# Tại Mini, kiểm tra phần mềm:
make check
# Tại Air, không khởi động native instance mới:
/usr/bin/perl -c scripts/air_recording_supervisor.pl
/usr/bin/perl tests/test_air_recording_supervisor.t
```

Bằng chứng private trên Mini: `.local/air-recording/` có codec gate, syntax/test/mutation/trial/bootstrap/latest-health và hình cấu hình; chỉ source/tests/docs/templates được công bố. Không cài Python/CLT trên Air, không tải thêm công cụ hoặc mở listener trong lần bàn giao.

## 6. Mạng Mini đã khôi phục

Người dùng lưu trong System Settings và Codex đọc lại:

1. Ethernet (en0)
2. Thunderbolt Bridge (bridge0)
3. Wi-Fi (en1)

Ethernet vẫn DHCP/inactive; default route192.168.1.1 qua en1; GitHub HTTPS200 sau thay đổi. Không thêm IP/host route, flush route hoặc bật lại helper. Helper cũ chỉ còn bản `.disabled.txt` riêng tư.

Hai panic report trước đây có `SOCD report detected: (iBoot async abort)`; chưa xác định nguyên nhân. Không kết luận việc khôi phục priority ngăn được restart. Không chạy lại helper, tự reboot/update OS/router/firmware để thử nghiệm.

## 7. Phần chưa hoàn tất

Endurance24h/retention dữ liệu thật đủ24h, recovery mất nguồn/reboot/WAN, auto-start bền vững, VPN bảo trì, publisher outbound tới server có xác thực/mã hóa, VPS/network Lào–Việt Nam, mobile/load200peers và Admin web/RBAC còn chưa triển khai/nghiệm thu. Kế hoạch tiếp theo nằm trong bản bàn giao; mọi chi phí/hạ tầng/persistent access cần quyền mới.

Nguồn cơ chế: [MediaMTX record](https://mediamtx.org/docs/features/record), [playback](https://mediamtx.org/docs/features/playback), [cleaner1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/recordcleaner/cleaner.go), [API1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/api/openapi.yaml), [FFmpeg download](https://ffmpeg.org/download.html), [Evermeet Intel builds](https://evermeet.cx/ffmpeg/).
