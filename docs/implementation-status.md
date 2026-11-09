# Trạng thái triển khai DEV.ONE Secure Live

**Bàn giao mới nhất 09/11/2026:** Người dùng xác nhận thiết bị ở Lào hoạt động tốt. VPS release `20261108T101614Z`; lúc 15:46 +07 cả hai path ready H.264/Opus và byte tăng, năm dịch vụ NUC active và hai kết nối RTSP camera established. Đã mở quản trị từ Mac qua SSH jump và tunnel loopback, đối chiếu public-key pin; IP camera `192.168.1.6` là snapshot DHCP. Người dùng đăng nhập và sẽ tự chỉnh zoom quang/lấy nét, chưa xác nhận kết quả. Chưa kiểm fullscreen Safari/Chrome trên iPhone thật. Giữ ghi mới tắt, không sử dụng Air; trạng thái ghi chưa được kiểm lại trong snapshot này. Xem [chi tiết](v1-implementation.md#vận-hành-tại-lào-và-bàn-giao--09112026).

**Thử Ethernet NUC06/11:** Netplan đã lưu `enp1s0` DHCP IPv4, route-metric100, optional=true; cấu hình merge giữ match MAC hiện hữu, candidate SHA256 `6436b43640ce999c9d556c2fc2709f3731ef1115274d45e00133c5d0ffe8c865`. Owner tự thực hiện sudo và xác nhận readback. Dây DHCP192.168.1.12 được ưu tiên, Wi-Fi dự phòng192.168.1.11. Sau khi owner chạy bài thử có timer tự phục hồi: trong snapshot `wlo1` DOWN, camera RTSP và cả hai socket tunnel2222 đều ESTABLISHED từ IP Ethernet; native H264/AAC ready/record=false, VPS H264/Opus ready và gateway online/observed=false/no auth latch. Bài thử kết thúc success, Wi-Fi đã UP trở lại; các kết nối vẫn dùng Ethernet. Lần chuyển đầu live chờ cổng cũ VPS nhả trước khi tự nối lại, không đo thời gian phục hồi. Owner xác nhận live có hình và tiếng bình thường; chưa xác định thời điểm xem so với cửa sổ 70 giây hoặc model/trình duyệt. Chưa reboot sau đổi Netplan, thử mất điện thật, mạng khách/Hà Nội/Lào hoặc SSH/SFTP qua jump key riêng bị thiếu.

**Snapshot trước khi sửa Ethernet06/11 (lịch sử):** owner cắm cáp NUC; `enp1s0` UP/LOWER_UP và có IPv6 nhưng chưa có IPv4 (`IPv4AddressState=off`). Default IPv4, tuyến camera và cả hai socket tunnel thực tế vẫn dùng Wi‑Fi `wlo1`/192.168.1.11. Live H264/Opus và monitor12/12 bình thường, intent/record=false. Chưa nghiệm thu chạy hoàn toàn qua Ethernet; đang chờ owner nhập sudo cho lệnh chỉ đọc cấu hình generated Ethernet để phân biệt DHCP với lỗi router, chưa đổi cấu hình mạng.

**Snapshot sau reboot trước thử Ethernet06/11 (lịch sử):** owner xác nhận live có hình và tiếng bình thường sau NUC reboot. SSH/SFTP trực tiếp strict host key tại DHCP192.168.1.11 PASS; chưa nêu model/trình duyệt người xem. Runtime ghi=false; năm unit và ba reverse listener tự phục hồi, VPS H264+Opus. Chưa thử rút điện thật, Ethernet/mạng khách hoặc jump key quản trị riêng.

**Snapshot reboot trước thử Ethernet06/11 (lịch sử):** owner tự chạy reboot, boot ID đổi; NUC DHCP đổi 192.168.1.6 → 192.168.1.11. Sau boot cả năm unit active/enabled; tunnel VPS18554/19996/19022 tự phục hồi. Qua SSH operator/VPS proxy, host key NUC khớp trust cũ; camera H264/AAC ready, record=false. VPS H264+Opus ready, gateway online/observed=false/no auth latch, intent=false/revision3. Không đo thời gian phục hồi; chờ owner xác nhận hình/tiếng sau reboot. Chưa thử mất điện thật, Ethernet/mạng khách hoặc SSH qua jump key riêng bị thiếu.

**Snapshot sau cutover trước thử Ethernet06/11 (lịch sử):** owner duyệt và tự thêm UFW TCP22 chỉ IP WAN nhà đã được duyệt; SSH operator strict PASS. Đã cài hai public key NUC sau VPS preflight policy/intent=false/token/ports PASS; owner tự chạy sudo bật hai tunnel. Cả năm unit NUC active+enabled; VPS thấy listener loopback18554/19996/19022, gateway online/observed=false/no auth latch, media ready H264+Opus, intent=false/revision3. Monitor ban đầu đang recovering. Chưa xác nhận người xem, SSH/SFTP qua jump (key jump Mini hiện thiếu), reboot/mất điện sau cài, Ethernet/mạng khách; Air vẫn ngừng dùng. IP là snapshot.

**Snapshot cài local trước cutover06/11 (lịch sử):** owner đã duyệt tạo/cài hai khóa dịch vụ NUC, không cần xin lại cùng phạm vi. NUC đổi DHCP sang192.168.1.6 sau boot, SSH strict dùng đúng host key đã tin cậy; camera được discovery/pin tại192.168.1.9. Owner tự nhập sudo và bộ cài đã PASS: userdevone-edge, ba unit source/recording/gateway active+enabled, H264/AAC, record=false,0video, mọi listener media/gateway chỉloopback. Hai unit live/maintenance đã cài nhưng disabled; public key còn chờ cài VPS. VPS22 timeout từ Mac/NUC,2222 vẫn reachable; chưa đổi firewall hoặc mạng Mac, đang chờ console root hiện có. Chưa cutover website/kiểm reboot. Đọc [runbook NUC](nuc-linux-runtime.md); Air vẫn ngừng dùng.

**Snapshot chuẩn bị NUC05/11 (lịch sử):** owner đã tắt Air và bỏ tuyến Air. NUC Ubuntu26.04.1 đã SSH/SFTP key-only; Codex SSH trực tiếp được sau khi owner cấp quyền Mạng cục bộ và nạp khóa1h. Bản port Linux đã qua70Python tests, Perl và MediaMTX synthetic trên NUC; discovery thật tìm/pin camera DHCP192.168.1.23. Bài native camera thật nhận H264/AAC, record=false/0video và đã dừng sạch. Năm systemd unit/tunnel profile đã verify, chưa cài/start và chưa chuyển production. Xem [runbook NUC](nuc-linux-runtime.md); ghi mới vẫn OFF, không bật lại Air. Các kết quả Air bên dưới không phải kiểm runtime Linux hiện hành.

**Chuẩn bị NUC05/11:** Ubuntu Server26.04.1amd64 cho ASUS NUC14Essential N97/8GB/512GB, headless/không mã hóa ổ, tự chạy sau mất điện; Wi-Fi nhà/Ethernet DHCP khi di chuyển. ISO SHA256 khớp, Etcher đã quan sát `Flash Completed!`/`1 Successful target`; chưa xác nhận boot/cài OS trên NUC, chưa port runtime Linux hoặc chuyển production. Owner yêu cầu cập nhật GitHub để ChatGPT web hướng dẫn tiếp từ boot USB; xem [hướng dẫn và prompt](mini-pc-setup.md). Các bằng chứng Air/VPS03/11 dưới đây không phải kiểm NUC.

**R1 quản trị Air đã nghiệm thu03/11:** Terminal/SFTP/màn hình thực qua VPS PASS khi Mini dùng hotspot khác WAN; owner xác nhận điều khiển được. Relay bảo trì tự phục hồi sau ngắt tiến trình, camera/tunnel live giữ nguyên PID;5agent/1native, ghi vẫn tắt. Đã sửa đúng chế độ Air: Screen Sharing bật, Remote Login bật, Remote Management tắt; chỉ macbook, không VNC legacy/full-disk. Mini đã về Wi-Fi cũ, tunnel thử15900 đã đóng. Gói recovery14tệp mã hóa đã được owner tạo/kiểm; source R1 đã push `66a4ff6`. Xem [runbook](air-remote-management.md). Chưa di chuyển Air tới WAN/subnet mới, reboot bộ5agent hoặc cài lại Mini thật; bảng kết quả để sau.

**Di chuyển không ER605,03/11:** đã áp dụng sau quyền riêng người dùng: camera DHCP, discovery có pin/proxy loopback18556,4LaunchAgent, tunnel2222 cho riêng Air không giới hạn WAN-IP. Software48Python/36Perl và camera RTSP/discovery/pin/auto-recovery/live/playback thật PASS tại nơi làm việc; vẫn1native/record=false/revision3. Router chưa đổi IP camera trong bài này; chưa nghiệm thu WAN/subnet mới, Hà Nội/Lào hoặc reboot cả4agent. SSH22/mirror backup Mini giữ giới hạn nguồn cũ. Xem [runbook di chuyển](portable-deployment.md) và cuối checkpoint; GitHub đã nhận mốc trước `e5d41df`.

**Đưa vào vận hành03/11:** bản `/opt/devone/releases/20261103T082215Z` đã phát hành, có12kiểm tra/cảnh báo Admin; snapshot15:38 cho thấy tất cả bình thường. Reboot/đăng nhập Air và tắt/bật Wi-Fi riêng Air thật đã kiểm, dịch vụ tự phục hồi và playback còn hình/tiếng. User xác nhận điện thoại tốt theo hướng dẫn4G/5G; chưa rõ model/browser. Ghi mới vẫn=false/revision3 theo lựa chọn vận hành. Code đã lưu local `8810a4b`, `bd5e416`, `ac18d19`, `a113fc9`; chưa push. Xem [vận hành](operations.md), [checkpoint](v1-implementation.md). Chưa qua lịch backup đêm đầu tiên, chưa thử mất điện toàn bộ/đổi WAN-IP/mọi browser; phần miễn200/endurance/optical giữ nguyên.

**Hiện hành03/11,14:40+07:** web/audio đã phát hành; live H264+Opus, bản ghi AAC và người dùng xác nhận nghe cả hai. Ghi thử30giây đã tắt lại, desired/observed=false, revision3. Backup metadata mã hóa VPS02:15/14ngày; Mini lấy lúc đăng nhập/mỗi giờ/30ngày bằng khóa chỉ tải ciphertext. Đã restore bản lưu thật vào DB tạm và kiểm MFA; Mini agent exit0. Đọc [checkpoint](v1-implementation.md) và [backup](metadata-backup.md). Các phần dưới ghi mốc cũ là lịch sử; không phải trạng thái hiện hành.

**Cập nhật vận hành03/11,12:45+07:** SSH operator VPS đã khôi phục bằng key mới, host trust cũ giữ nguyên. Đã cài3LaunchAgent Air tự chạy sau đăng nhập; kiểm native tự phục hồi3,054s và tiến trình tunnel chạy lại0,523s, rồi kiểm riêng H264/playback qua VPS thành công. Ghi mới vẫn=false cả intent/native/disk,1065file/16.148.184.903byte không tăng; listener nội bộ chỉloopback, hash/plist khớp candidate. Đọc [runbook](air-autostart.md) và checkpoint. Retention1d vẫn chạy khi native hoạt động dù record=false/không người xem; native khởi động lại sẽ quét ngay. Chưa thử logout/reboot/mất WAN thật. Bài tải200/8h được miễn (`USER-ACCEPTED/WAIVED`), không ghi measured PASS.

**Kết thúc bài ghi 03/11 lúc10:27+07:** source H264 và ghi SSD ổn định đến lúc kiểm tra; người dùng chấp nhận kết thúc sớm bài dự kiến24h. Đã tắt ghi mới, giữ live/playback. Phiên chính thực tế17h54m08,786s (`USER-ACCEPTED`), chưa đo đủ24h. Đọc [checkpoint](v1-implementation.md) trước mọi thao tác bật ghi lại.

**Cập nhật 03/11/2026:** VPS DigitalOcean SGP1, tên miền `lao6789.com`, HTTPS, database, web/API và kết nối bảo mật Air → VPS đã được triển khai bản đầu theo yêu cầu. Đọc [checkpoint v1](v1-implementation.md) cho bằng chứng và các kiểm thử còn thiếu; các phát biểu chưa có VPS/domain/web bên dưới mô tả snapshot 02/11.

Cập nhật 02/11/2026. Tài liệu này mô tả snapshot hiện tại, thay cho các hướng đấu nối/bàn giao trước đó. Mac mini là máy phát triển; Air tiếp tục chạy recording tại điểm camera. Đọc [bản bàn giao](../HANDOFF_MAC_MINI.md) khi mở chat mới.

**Bổ sung phiên web v1, 02/11 tối:** người dùng đã duyệt Next.js/Fastify/PostgreSQL/Caddy cùng dependency/schema/API. Source web/Admin/RBAC, gateway Air và cấu hình triển khai đã có trên nhánh `tuanminh/secure-live-v1`; **chưa deploy**, chưa mua VPS/domain và chưa đổi phiên ghi Air. Mức tối đa200 live viewers đồng thời và8giờ/ngày, tải trung bình chưa biết; chỉ lưu video trên Air; nghiệm thu tại nơi làm việc, Lào làm sau. Đọc [checkpoint v1](v1-implementation.md) và [runbook triển khai web](web-deployment.md) để phân biệt bằng chứng local với các snapshot POC bên dưới.

## 1. Quyết định và tuyến hiện tại

- Phát triển tại `/Volumes/Developer/Projects/camera` trên Mac mini macOS26.7/arm64; Codex trực tiếp implement/review/verify. Đã gỡ Antigravity CLI/bridge, quy tắc delegation/model/quota và các worker runtime; source thay đổi chưa nhập về đã lưu private ngoài active workflow.
- Skill dev-flow đã đồng bộ đủ16/16file với commit `caefff8d7b82ec0f9facda875ef25c87bf55675e` từ `tuanminh2409bn/dev-flow-macos`; global rules riêng vẫn giữ. Không có cơ chế tự gọi lại worker.
- Camera → switch PoE → LAN bộ phát Wi-Fi; Mini/Air dùng cùng Wi-Fi. Camera192.168.1.64/24 static, Mini192.168.1.8, Air192.168.1.12 tại snapshot. ER605 không tham gia tuyến. Không cấu hình lại DHCP/IP để khớp các địa chỉ lịch sử.
- Mục tiêu người xem Lào/VN. LAN WebRTC được người dùng chấp nhận trực quan theo mục tiêu1giây và miễn bài đo optical. Ghi `USER-ACCEPTED/VISUAL`, không chuyển thành p95 đã đo. WAN/VPS/website Admin chưa triển khai.
- PDF và kế hoạch root đã cập nhật [v2](../KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md); bản gốc và runbook tuyến cũ đã bỏ khỏi checkout; truy vết bằng Git. Tuyến Air onsite là thay đổi đã được người dùng chọn so với thiết kế ban đầu.

## 2. Snapshot Air commissioning — 17:27:39+07 ngày 02/11

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

## 8. Kế hoạch v2 và dọn tuyến cũ - 02/11/2026

Theo yêu cầu người dùng, kế hoạch Markdown/PDF root là bản v2 hiện hành. Đã bỏ bản archive ngày 30/10, runbook/template ER605-WireGuard, Docker Compose POC tham khảo và quy trình đo LAN cũ khỏi checkout. Bản từng commit còn trong lịch sử Git; không rewrite history. CLI/tests hiện có được giữ vì việc dọn tài liệu không thay hợp đồng công cụ.

Snapshot đọc SSH allowlist lúc 17:55:53+07: supervisor running/ok, status cập nhật 17:55:46; H264 ready từ 16:32:53.622655+07, bytesReceived 1.250.917.160; record=true, pause/latch=false; SSD trống 99.196.829.696 byte. Retention=1d, segment=1m. Không đếm lại file/listener/launchd ở lần đọc này. Chưa đạt 24h.

P0 guards/config → P2 WAN → P3 web → P4 tải/thực địa; quan sát P1 song song. VPS/traffic, nơi lưu bản ghi website và auto-start còn mở. Dòng WHIPS destination 401 giả bị classifier nhận nhầm camera_auth_failure: phải sửa trước khi bật publisher; chưa sửa source trong đợt tài liệu này.

Kiểm tra: PDF 8 trang dựng từ Markdown và kiểm hình; liên kết Markdown, git diff --check, plist lint, ignore runtime và scan mẫu credential. Kết quả kiểm phần mềm và publish được ghi cùng commit sau khi xác minh. Không tác động phiên ghi Air, dữ liệu video, credential hoặc backup thiết bị.

Xác minh trước commit dọn tuyến cũ: `make check` trên Mini PASS 22 tests/1,855s; `plutil -lint infra/macos/recording-agent.plist.example` PASS; `git diff --check` PASS. Python kiểm toàn bộ link nội bộ Markdown còn tồn tại/fences/mẫu private-key và URL credential: PASS. PDF đọc lại đủ 8 trang, không còn tham chiếu archive/VPN cũ; render các trang nội dung thay đổi không tràn/cắt. `git fetch origin` và `git rev-list --left-right --count HEAD...origin/main` trả 0/0 trước commit. Người dùng đã cho phép commit/push lần dọn này; không force-push.
