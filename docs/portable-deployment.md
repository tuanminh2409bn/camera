# Di chuyển camera và Air không dùng ER605

Trạng thái 03/11/2026: **đã áp dụng và kiểm thực tế tại nơi làm việc** theo quyền riêng người dùng. Camera đã bật DHCP; Air tự tìm camera không có IP gợi ý trên đĩa; tunnel dùng SSH2222; bốn LaunchAgent đang chạy. Ghi mới tiếp tục tắt. Chưa chuyển thiết bị tới Hà Nội/Lào hoặc thử WAN-IP/subnet khác.

## Đấu nối tại khách hàng

1. Camera → cổng PoE của switch; UPLINK switch → cổng LAN router khách hàng.
2. Air kết nối Wi-Fi thuộc cùng LAN với camera. Tránh Wi-Fi khách hoặc chế độ cách ly Wi-Fi/LAN.
3. Cắm nguồn, mở nắp và đăng nhập macOS trên Air. Sau khi dịch vụ sẵn sàng, mở `https://lao6789.com` để kiểm live/âm thanh và trạng thái Admin.

Phương án không cần ER605, bộ phát riêng hoặc adapter LAN. Nó phụ thuộc router khách có DHCP IPv4, cho Air truy cập camera và truy vấn multicast SADP; Air cần Internet và outbound TCP2222 tới VPS. Không cần mở cổng camera trên router khách. Mạng chặn các điều kiện này cần người quản trị mạng hỗ trợ; không có bảo đảm chạy trên mọi router/ISP. Chưa kiểm thực địa Hà Nội/Lào.

## Cấu hình đã áp dụng

- Bật DHCP camera bằng cách đổi duy nhất `IPAddress/addressingType` từ `static` thành `dynamic`; giữ XML gốc riêng để khôi phục. Không đổi mật khẩu, codec, firmware hoặc router. Đọc lại địa chỉ/DHCP sau PUT để xác nhận firmware thực sự áp dụng.
- Cài `scripts/camera_roaming_proxy.pl` trên Air: listener RTSP TCP **chỉ `127.0.0.1:18556`**, SADP inquiry UDP37020 multicast TTL1 trên interface vật lý đang hoạt động. LaunchAgent thứ tư `com.devone.camera.camera-source` tự chạy sau đăng nhập. Không thay entry point/safety guard của supervisor. Runtime tại `.local/air-autostart-runtime`, plist trong `~/Library/LaunchAgents`.
- Đổi source MediaMTX sang proxy loopback, giữ credential/channel và TCP. Proxy không đọc tệp credential, không ghi RTSP/video ra đĩa: chỉ chuyển byte sau khi IP ứng viên đã qua kiểm tra HTTPS public-key pin. IP cache trong bộ nhớ phải còn cùng subnet và đúng pin; khi không hợp lệ, tìm lại bằng SADP khớp UUID/MAC/serial/IP nguồn rồi xác minh pin. Config hiện không có `lastKnownHost`, nên mỗi lần proxy khởi động dùng discovery thật. Nếu không tìm được thiết bị đúng thì chờ, không gửi RTSP tới IP chưa xác minh. Không tự tin cậy khóa mới khi camera reset/chứng thư thay public key.
- VPS có SSH ingress riêng **TCP2222** cho đúng user `devone-air`, public-key only, không shell/PTY/subsystem/root/direct forwarding; chỉ hai remote forward loopback18554/19996. Giữ cổng22 operator giới hạn IP nơi làm việc. Air dùng khóa/known_hosts hiện hữu, `HostKeyAlias` giữ đúng identity server đã tin cậy. Không mở rộng khóa chỉ tải backup trên Mini.
- Khởi động lại có kiểm soát source/supervisor/tunnel để áp dụng, live gián đoạn ngắn. Giữ `desired=false`, native/disk record=false, auth latch và reserve15GiB. Không ghi video thử, không đổi mạng Mini, không thêm dependency/dịch vụ trả phí hoặc reboot/logout Air.

File private identity, XML và rollback ở `.local/roaming-prep/` trên Mini, quyền0600/thư mục0700; không đưa lên Git. Clone mới không tự có identity/credential để chạy camera.

Đường camera→Air vẫn là RTSP/TCP trên LAN theo cấu hình hiện có; HTTPS dùng kiểm danh tính thiết bị. Air→VPS được mã hóa bằng SSH. Việc pin HTTPS không biến đường RTSP trên LAN thành TLS.

## Trình tự áp dụng và kiểm chứng

1. Đọc lại intent/status/PID sở hữu/source/config và sao lưu private file sắp đổi. Nếu trạng thái khác với ghi tắt đã duyệt, dừng để đối chiếu. Không dùng PID từ tài liệu.
2. Validate SSH candidate bằng `scripts/validate_roaming_ssh.py` và `systemd-analyze verify`. Sau quyền riêng cho listener, cài/start ingress2222 và firewall; kiểm host key/key-only/giới hạn user-forward. Không sửa dịch vụ SSH22 hoặc khóa operator.
3. Cài proxy và LaunchAgent khi đã được duyệt. Trước khi đổi DHCP, thử đường RTSP qua proxy với camera còn địa chỉ hiện tại. Xác minh source H264+AAC, live H264+Opus, ghi tắt. Bài socket fixture không thay được bài RTSP thiết bị thật; nếu camera/SDP/RTSP không tương thích, phục hồi source cũ trước khi đổi DHCP.
4. Đổi riêng DHCP sau khi proxy đã qua bài thật; discovery lại, kiểm đúng pin và đọc lại DHCP. Kiểm camera nhận IP mới và source phục hồi mà không sửa IP thủ công. Không PUT lặp khi chưa xác định kết quả; auth401/403 cuối cùng dừng và giữ latch.
5. Thay config tunnel sang2222. Khi thay job cùng label: bootout, chờ job **và PID cũ** kết thúc/remote forward cũ nhả hết rồi bootstrap; không tạo phiên tunnel/native thứ hai.
6. Kiểm một native, bốn job, loopback listeners, desired/native/disk record=false, không latch/pause, HTTPS/live/âm thanh/playback và monitor Admin. Kiểm diff/hash/plist/secret/ignore, cập nhật checkpoint theo bằng chứng thật.
7. Khi tới điểm mới, kiểm live bằng điện thoại qua Internet và Admin. Ghi rõ đây là nghiệm thu mạng mới; bài ở nơi làm việc không chứng minh chất lượng tuyến Lào.

Đổi WAN-IP cho camera không mở quyền bảo trì Mini hoặc mirror backup từ IP bất kỳ. SSH quản trị VPS22 và key tải backup mã hóa trên Mini vẫn giới hạn IP nơi làm việc. Nếu mang cả Mini sang mạng mới, mirror Mini chưa tải được từ đó; backup mã hóa trên VPS vẫn chạy theo lịch/giữ14ngày. Live và Admin web vận hành độc lập với Mini. Muốn đổi đường bảo trì/mirror cần scope riêng, không nới các key này theo quyền chỉ dành cho Air.

## Khôi phục nếu lỗi

Giữ SSH22 operator hiện hữu làm đường bảo trì. Nếu2222 không hoạt động, khôi phục file tunnel cũ và thay job theo quy tắc chờ PID trên. Nếu proxy chưa qua bài RTSP thật, dừng job proxy và phục hồi source cũ với ghi tắt; chưa đổi DHCP. Nếu DHCP đã áp dụng, chỉ phục hồi XML IP tĩnh gốc trên **LAN nơi làm việc tương thích subnet cũ**, tới IP camera hiện tại đã qua pin; không ép IP tĩnh cũ lên router khách khác subnet. Không reset camera, bỏ pin/latch, mở password SSH hoặc xóa bản ghi để chữa lỗi.

## Bằng chứng kiểm chứng

- Mini `make check`:48Python tests/compile/CLI help PASS, có4bài kiểm SSH policy chặn user/root/password/shell/forward quá quyền.
- Air `/usr/bin/perl -c scripts/camera_roaming_proxy.pl` và `tests/test_camera_roaming_proxy.t` trong workspace fixture riêng:36bài PASS; kiểm identity/XML/on-link/địa chỉ cũ sai pin/timeout/RTSP byte/binary/half-close. Không chạy native instance mới.
- Truy vấn thật trên Air:1camera SADP khớp identity, xác minh đúng HTTPS public-key pin; không mở listener18556. Kiểm curl riêng trên Air: đúng pin HTTP200/exit0; sai pin HTTP000/exit90.
- VPS: `sshd -t/-T` cho hai địa chỉ nguồn khác nhau và unit schema PASS; unit `devone-roaming-tunnel` active/enabled, firewall rate-limit2222, cổng22 chỉ cho IP nơi làm việc. Client Air đã nối thật tới2222 bằng key/host trust cũ; hai reverse listener chỉ127.0.0.1. Root bị từ chối qua ingress2222. Air key xác thực được nhưng session/shell bị từ chối mở channel, direct forwarding bị từ chối. Không đổi authorized_keys/host key.
- Trước DHCP, FFprobe thật trên Air qua proxy nhận H264720p + AAC16kHz mono. Sau thay source, Air native nhận H264+MPEG-4 Audio, ghi tắt; job/native cũ đã thoát trước bootstrap, đúng1native.
- PUT DHCP đúng1lần, HTTP200; GET qua HTTPS đúng pin xác nhận `addressingType=dynamic`. Router vẫn cấp192.168.1.64 ở bài này: **không có bằng chứng IP/subnet đã đổi**. Xóa IP gợi ý trên đĩa rồi thay job proxy: discovery thật tìm đúng camera và native tự nối lại, không đổi native PID. Thử dừng đúng proxy PID vừa xác minh: launchd tự phục hồi proxy và live, native vẫn cùng PID, ghi tắt, không latch.
- End-to-end VPS16:55:35+07: live H264+Opus ready, Air online/no pause/no latch, intent=false/revision3; đoạn xem lại03/11 14:33:15 dài3giây HTTP200, FFprobe H264+AAC. Chỉ đọc video trong RAM, không lưu trên VPS/Mini. API/web/media/audio/Caddy/PostgreSQL/monitor/backup và ingress mới active. Admin Chrome16:58 hiển thị12kiểm tra bình thường và ghi tắt.
- Chưa reboot với cả4agent, đổi WAN-IP/subnet thật hoặc nghiệm thu Hà Nội/Lào. Bài reboot/Wi-Fi trước đây thuộc bộ3agent cũ; không gọi thành bài reboot của cấu hình mới. Các miễn tải200/8h, endurance và optical vẫn giữ nguyên.

Tham khảo: [OpenSSH sshd_config](https://man.openbsd.org/sshd_config), [HostKeyAlias](https://man.openbsd.org/ssh_config), [curl pinnedpubkey](https://curl.se/docs/manpage.html#--pinnedpubkey), [Hikvision SADP](https://legacy.hikvision.com/sites/default/files/manual/sadp_user_manual.pdf). Hành vi discovery/pinning ở trên có bằng chứng trực tiếp trên camera/Air hiện tại; không suy thành tương thích mọi thiết bị Hikvision.
