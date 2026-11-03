# Tự khởi chạy và dọn bản ghi trên Air

Trạng thái ngày03/11/2026,12:45+07: **đã cài và kiểm phục hồi thực tế trong phiên đăng nhập**. Ba plist nằm tại `/Users/macbook/Library/LaunchAgents/`, runtime Perl tại `/Users/macbook/Developer/camera/.local/air-autostart-runtime/`; không sửa các script cũ trong `scripts/` trên Air. Ghi mới=false trên disk/native/VPS intent. Bộ ứng viên `.local/autostart-prep/candidate-20261103/` trên Mini và `.local/autostart-candidate-20261103/` trên Air được giữ để đối chiếu hash. Backup private trên Air `.local/autostart-backup-20261103/`; runtime/plist cũ giữ để rollback, không bootstrap duplicate.

SSH operator VPS đã khôi phục bằng `.local/ssh/server-operator/id_ed25519_recovery_20261103`, dùng known_hosts cũ. User tự reset root/đổi password và tự thêm public key. `/usr/bin/ssh -o UseKeychain=yes -o IdentityAgent=none` với strict trust/key mới đã kết nối thành công; không đọc/hiện passphrase. Password/kbd-interactive SSH VPS vẫn tắt, public-key bật, không đổi firewall hoặc account tunnel Air.

## Cơ chế giữ 24 giờ

Air hiện dùng MediaMTX1.21.3, `recordDeleteAfter: 1d`, segment khoảng1phút. Đây là cửa sổ lưu cuốn chiếu theo tuổi đoạn ghi, không phải cứ24giờ xóa toàn bộ. Cleaner quét ngay khi native khởi chạy, sau đó khoảng30phút/lần; file quá hạn có thể tồn tại thêm khoảng30phút khi dịch vụ chạy bình thường. Không có file thì không cần xóa. Việc quét không phụ thuộc người xem live hay `record=true`; tắt ghi mới vẫn dọn bản ghi cũ.

Nếu Air tắt/ngủ hoặc MediaMTX không chạy thì không có tiến trình dọn. Khi dịch vụ chạy lại, nó tính tuổi bản ghi theo thời gian hiện tại và quét ngay, không đợi thêm24giờ. Đồng hồ hệ thống cần đúng; lỗi ổ đĩa/quyền truy cập có thể ngăn dọn. File xuất thủ công ngoài `.local/recordings/` không thuộc retention này. Chốt lỗi xác thực camera vẫn dừng native; người vận hành phải xử lý trước khi dịch vụ và cleaner có thể hoạt động lại.

Nguồn đúng phiên bản: [cleaner1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/recordcleaner/cleaner.go), [khởi tạo cleaner độc lập với cờ ghi](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/core/core.go#L649).

## Bộ đã cài

- `scripts/air_login_supervisor.pl`: entry point riêng, giữ CLI phiên ghi cũ. Chạy supervisor ở managed mode: gỡ override `MTX_*` từ môi trường rồi đặt duy nhất `MTX_PATHS_LIVE_RECORD=false` trước native exec. Server chỉ reconcile lại intent đã lưu khi gateway online và safety guard cho phép. Với intent hiện tại=false, ghi mới tiếp tục tắt, kể cả lúc tunnel chưa nối lại.
- Managed mode cho native chạy với ghi tắt khi disk thấp/không đọc được để cleaner có thể giải phóng các đoạn hết hạn; `recordingPaused=true` giữ quyền bật ghi bị khóa trong phiên đó. Không xóa thủ công và không bật lại tự động sau safety pause. CLI session cũ vẫn từ chối khởi chạy khi thiếu dung lượng như trước.
- Ba LaunchAgent cùng label hiện có, chạy quyền user `macbook`: supervisor, gateway, tunnel. Supervisor restart khi thoát lỗi, throttle60giây; camera auth latch trả successful exit để không bị launchd thử lại. Gateway/tunnel giữ chính sách reconnect hiện có, không thêm listener hoặc mở rộng SSH trust.
- `scripts/prepare_air_autostart.py` chỉ tạo bundle mới trong thư mục private ignored, không cài/khởi động service. Manifest ghi hash và destination cho3script/3plist, không chứa credential. Các bản script sẽ đặt tại `.local/air-autostart-runtime/`, tách source đang chạy.

Đây là **tự chạy sau đăng nhập**, không phải daemon trước đăng nhập. Air phải bật, mở nắp, cắm nguồn và đăng nhập user. Không thay FileVault, auto-login, power-on-after-failure, sleep toàn máy hoặc mạng. Khôi phục sau mất điện không bảo đảm tự bật máy hay tự mở khóa. Apple mô tả [user agents chỉ chạy trong phiên đăng nhập](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).

## Vận hành và thay thế dịch vụ

1. Lần cài/restart3dịch vụ ngày03/11 đã hoàn tất theo quyền được cấp. Khi bảo trì tiếp, đọc checkpoint và kiểm actual intent/status trước thao tác; không tự bật ghi, reboot/logout Air, đổi FileVault/auto-login hoặc mở rộng SSH. Không yêu cầu passphrase trong chat.
2. Kiểm lại status, latch, dung lượng, PID sở hữu và intent server; nếu ghi đang bật hoặc có thay đổi người dùng, dừng để review. Backup source/plist/config hiện tại bằng file private, giữ hash.
3. Đối chiếu bundle hash, copy atomic runtime/plist0600; chuẩn bị fallback `record=false` và validate trước khi unload. Đọc PID từ job/status mới, bootout rồi **đợi job biến mất và tiến trình cũ thoát hết** trước bootstrap cùng label. `bootout` trả0 chưa chứng minh đã xong cleanup; nạp ngay có thể lỗi5. Không dùng `run_bounded_aux_command` để chạy launchctl vì nó signal tiến trình khi EOF dù IPC chưa xong. Operator helper hiện chờ mã thoát thực tế/timeout có giới hạn, không signal job mới. Bootstrap supervisor trước rồi gateway/tunnel.
4. Xác minh đúng một native/listener loopback, source H264 ready, desired/observed=false, không tăng byte/tệp ghi, gateway/tunnel/HTTPS còn phục vụ. Kiểm restart có kiểm soát và native vẫn record=false. Không tạo hay xóa video thử trên thư mục thật.
5. Nếu lỗi: bootout đúng3label, phục hồi file/plist đã backup và bootstrap phiên cũ với cấu hình ghi=false đã validate. Không gỡ auth latch, không mở rộng trust, không xóa video.

## Bằng chứng kiểm chứng

- Đã kiểm hash3runtime/3plist đúng candidate, owner501/mode0600,3job loaded từ Library/LaunchAgents. Đúng1native, các listener native chỉ127.0.0.1; recording config record=false/deleteAfter1d. Directory vẫn1065file/16.148.184.903byte, không tăng file/byte sau cài và thử phục hồi.
- Dừng có kiểm soát đúng native PID vừa đọc/đối chiếu process identity: supervisor thoát lỗi và launchd tự chạy lại, Air H264 online/record=false sau3,054s. Dừng đúng SSH client PID của tunnel: tiến trình mới xuất hiện sau0,523s; số đó không phải thời gian phục hồi media WAN. Đã kiểm riêng sau đó: VPS nhận H264, gateway online, clip3giây qua tunnel trả200/956.891byte/headerMP4 hợp lệ. Chỉ đọc trong RAM, không lưu video lên Mini/VPS.
- Thay cùng label với child giả cleanup2s tái hiện lỗi5; sau chờ PID cũ kết thúc, bootstrap mới PASS (đợi2,092s). Cả3schema profile cũng PASS bằng job giả riêng; các fixture đã bootout/dọn. Hai lần chuyển dịch vụ đầu gặp lỗi operator và được phục hồi về phiên cũ; lần cài thứ ba thành công, không sửa phần mềm native hoặc làm yếu safety guard.
- Software tại cùng source hash: Mini29Python tests PASS; Air supervisor18top-level/gateway30assertions PASS; syntax/plist/hash/mode/ignore đã kiểm. Native source/library mới hash`209a897b459b7726c24654b169bb5ad00e2edfad8742cd039049f9c7be1e8b7d`.
- Evidence private ignored trên Mini: `.local/autostart-prep/post-install-air.json`, `final-air.json`, `native-recovery.log`, `tunnel-recovery.log`, `end-to-end-server.json`, và3apply log. Không commit runtime, config riêng tư, SSH key hoặc video.

Chưa logout/reboot Air, thử WAN mất mạng thật hoặc kiểm browser decode mới ở lượt cuối (Chrome không còn kết nối với công cụ). Không biến fixture/config validation thành các kết quả đó. Việc xóa video thật quá24giờ vẫn chưa đo ở phiên hiện tại; không yêu cầu chạy lại bài endurance đã miễn. User đã nghiệm thu bỏ bài tải200/8h (`USER-ACCEPTED/WAIVED`), không phải benchmark đo được.
