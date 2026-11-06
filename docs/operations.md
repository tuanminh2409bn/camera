# Vận hành website camera

Phạm vi hiện tại: vận hành tại nơi làm việc, Chrome đã được nghiệm thu hình/tiếng/live/xem lại; mạng Lào làm sau. Xem [checkpoint](v1-implementation.md) trước thao tác. Người dùng chọn **giữ ghi mới tắt** và **chỉ hiển thị cảnh báo trên Admin**.

## Kiểm tra khi bắt đầu sử dụng

1. Giữ Air cắm nguồn, mở nắp và đăng nhập macOS. Ba LaunchAgent tự chạy sau đăng nhập; không có cam kết chạy trước màn hình đăng nhập hoặc tự bật máy khi mất điện. Không sửa FileVault, auto-login, sleep hoặc OpenCore.
2. Vào `https://lao6789.com`, đăng nhập Admin bằng MFA. Mở **Quản trị → Tình trạng hệ thống** và xem thời điểm cập nhật. Không hiểu dữ liệu cũ/mất giám sát là trạng thái bình thường.
3. Mở live, bấm bật âm thanh; kiểm tra đúng hình/tiếng. Dừng xem khi xong để trả suất phiên. Mỗi tài khoản có giới hạn phiên live riêng; nhiều tab/thiết bị đang xem dùng nhiều suất.
4. Ghi mới đang tắt theo lựa chọn vận hành. Live vẫn chạy, nhưng không có bản ghi mới; bản cũ hết hạn sẽ được dọn. Không tự bật ghi để kiểm tra. Xem lại/tải cần quyền riêng; tài khoản viewer chỉ có quyền Admin đã cấp.

## Cảnh báo trong Admin

Monitor trên VPS chạy mỗi60giây, UI lấy trạng thái mỗi10giây. Lỗi3lần liên tiếp mới mở cảnh báo, bình thường2lần mới đóng; lịch sử tối đa50sự kiện, Admin hiển thị10sự kiện mới nhất. Đây là quy tắc theo mẫu kiểm tra, không phải SLA thời gian thông báo. Một dấu hiệu mới hiện “Đang xác minh”, phục hồi chưa đủ mẫu hiện “Đang xác nhận phục hồi”. Snapshot cũ hơn180giây hoặc từ tương lai quá60giây không được hiển thị xanh; HTTP bị treo có hạn8giây.

| Mục | Ý nghĩa và cách xử lý |
|---|---|
| Đăng nhập/phân quyền, Website/HTTPS | Kiểm API, Caddy, PostgreSQL và chứng chỉ; không tắt MFA/HTTPS hoặc mở native public để chữa lỗi. Hạn chứng chỉ dưới14ngày được cảnh báo. |
| Hình, tiếng, luồng đang cập nhật | Kiểm nguồn Air/tunnel/audio adapter. H264, Opus và bytecounter phải tiến; trạng thái ready đơn thuần không chứng minh hình đang tiến. |
| Kết nối Air | Kiểm nguồn điện, Desktop đã đăng nhập, Wi-Fi và tunnel. Không mở pipeline native thứ hai. |
| Xác thực camera | Kiểm auth latch, dừng và review nguyên nhân. Không thử lặp mật khẩu hoặc tự gỡ latch. |
| Dung lượng Air | Cảnh báo dưới20GiB hoặc safety pause; supervisor vẫn có reserve15GiB riêng. Không xóa video thủ công để làm xanh kiểm tra. |
| Ghi đúng yêu cầu | So sánh intent đã lưu với quan sát Air. Tắt đúng yêu cầu là bình thường. |
| Dung lượng VPS | Cảnh báo dưới10GiB; xem tăng trưởng release/log/backup, không xóa bản đang dùng hoặc DB. |
| Backup/lịch backup | Bản phải còn tồn tại, đúng kích thước/private mode, đủ mới và đáp ứng lịch02:15. Sau02:45 chưa có bản của lần đến hạn sẽ cảnh báo qua quy tắc3mẫu; timer phải enabled/active. |

Cảnh báo chỉ hiện khi mở Admin; không gửi Telegram/email, không có monitor độc lập bên ngoài VPS. Khi VPS/website tắt hoàn toàn, Admin cũng không mở được. Monitor chỉ quan sát, không tự sửa dịch vụ, đổi quyền hoặc bật/tắt ghi.

Traffic hiển thị là outbound trên giao diện mạng public được đo từ khi monitor bắt đầu trong thángUTC; không cộng khoảng trước đó không biết và không đếm trùng khi counter/boot reset. Đây không phải hóa đơn/quota DigitalOcean. Kiểm Billing/traffic của nhà cung cấp trước mở rộng lượng người xem; không dùng số đo này để hứa tổng phí nằm trong ngân sách.

## Dữ liệu, backup và retention

Video chỉ ở Air. Retention1ngày được native cleaner xét khi khởi động và khoảng30phút/lần, độc lập việc có người xem hoặc record=false. Air tắt thì không dọn; native chạy lại sau đăng nhập mới dọn bản quá hạn. Xem [ghi hình](air-recording-service.md).

Backup metadata02:15 giờ Việt Nam, VPS giữ14ngày; Mini lấy lúc đăng nhập/mỗi giờ, giữ30ngày. Đã restore bản lưu thật/MFA vào DB tạm; lần chạy theo lịch đêm đầu tiên cần theo dõi khi đến giờ. Giữ export khóa riêng mã hóa và passphrase ở hai nơi an toàn, có bản ngoài Mini. Xem [runbook backup](metadata-backup.md). Không restore đè production để thử.

## Kiểm tra phục hồi có người đứng cạnh Air

Chỉ thực hiện trong cửa sổ được duyệt. Lưu boot time, source, trạng thái ghi và hash trước thử; không lấy PID từ tài liệu để signal.

1. Người dùng tự khởi động lại Air và tự đăng nhập. Codex đối chiếu boot time mới, đủ3LaunchAgent, đúng1native, source H264/AAC, gateway/tunnel và VPS H264/Opus; live/playback trở lại, recording=false và không latch/pause. Không chạy lệnh “bật dịch vụ” thủ công để che lỗi auto-start.
2. Sau khi bước1 đạt, người dùng tự tắt Wi-Fi **riêng Air** khoảng30giây rồi bật lại. Không đổi Mini, camera/router, thứ tự mạng/IP/DHCP. Kiểm trạng thái mất kết nối rồi phục hồi hình/tiếng/xem lại và giữ ghi tắt. Không hứa chính xác thời gian phục hồi khi chưa đo.
3. Thử trên điện thoại thực tế qua4G/Wi-Fi: đăng nhập viewer có quyền phù hợp, live/âm thanh, toàn màn hình, xem lại và dừng/đăng xuất. Fixture390px chỉ chứng minh bố cục; không thay bằng chứng Safari/iOS/Android thật. Đánh giá TURN nếu mạng không kết nối video, xin quyền trước hạ tầng/phí mới.

Không chạy lại bài tải200/8h, phần thời gian ghi dài hoặc optical latency đã được người dùng miễn/chấp nhận. Không đổi chúng thành kết quả benchmark.

## Bảo trì và rollback

- Runtime monitor: `/opt/devone/ops/operations_monitor.py`, `devone-monitor.service`/`.timer`. Private state root0600; thư mục0710 root:devone chỉ cho group đi xuyên, snapshot allowlist0600 do devone đọc. API chỉ Admin được xem; không trả log, config, token, boot ID hoặc counter nội bộ ra HTTP. File trạng thái không thay schema DB.
- Kiểm `systemctl status devone-monitor.timer devone-monitor.service` và cập nhật snapshot khi cảnh báo giám sát cũ. Không in raw config/environment/journal có bí mật. Lỗi probe được chuyển thành trạng thái; monitor không chạm recording intent.
- Khi đổi IP công cộng, SSH operator22 và mirror backup Mini vẫn có thể bị chặn theo giới hạn nguồn. Tunnel Air đã có ingress2222 riêng không giới hạn WAN-IP, chỉ đúng key/user và2reverse loopback; xem [di chuyển không ER605](portable-deployment.md). Không nới key/operator/mirror theo quyền roaming Air. Giữ strict known_hosts; không tự mở SSH quản trị cho mọi IP.
- Giữ release/config trước và hash artifact. Rollback bằng atomic symlink về release đã build, restart API/media/audio/web theo thứ tự unit rồi kiểm HTTPS, auth, hai track và ghi tắt. Không rollback/drop/restore đè database. Caddy tiếp tục quản TLS; không thêm Certbot cạnh tranh cổng.
- Source/dependency chỉ phát hành sau kiểm tra bắt buộc. Commit local và push là hai bước khác nhau; push/merge cần quyền riêng. Không đưa runtime, key, ảnh camera, video hoặc log riêng tư vào Git.
