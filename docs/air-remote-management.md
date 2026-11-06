# Quản trị Air từ Mini và khôi phục sau cài lại Mini

Triển khai và nghiệm thu R1 ngày03/11/2026 theo yêu cầu người dùng. **Terminal, SFTP và điều khiển màn hình đã hoạt động khi Mini dùng hotspot khác WAN với Air.** Relay bảo trì tự phục hồi sau thử ngắt riêng tiến trình; live/âm thanh giữ nguyên và ghi hình vẫn tắt. Bảng kết quả để giai đoạn sau. Chưa thử cài lại Mini hoặc di chuyển Air sang mạng Hà Nội/Lào.

## Đường kết nối và quyền

- Air chủ động mở SSH bảo trì riêng tới ingress VPS2222. Agent `com.camera.air-maintenance-relay` RunAtLoad/KeepAlive/throttle30s, sau đăng nhập macOS; SSH key/config/known_hosts tại `.local/ssh/maintenance-relay/` trên Air. Tự động không có nghĩa tự mở khóa FileVault/bật nguồn.
- VPS chỉ mở reverse listener **127.0.0.1:19022**, chuyển tới SSH22 trên Air. Không public19022/5900/15900, không thêm public port mới. Cổng22 operator VPS vẫn chỉ IP nơi làm việc; key backup Mini giữ giới hạn cũ.
- Ba principal được ingress2222 cho phép: `devone-air` giữ đúng2reverse18554/19996; `camera-maint-relay` chỉ remote-listen19022; `camera-maint-jump` chỉ direct-forward tới127.0.0.1:19022. Tất cả public-key only/no shell/no PTY/root. Hai account mới home `/var/lib/<user>`, shell nologin, key restrict và permitlisten/permitopen tương ứng.
- Mini vào Air qua jump rồi xác thực bằng key Air riêng; jump key không đủ để đăng nhập Air. Air key mới chỉ chấp nhận từ127.0.0.1, không agent/X11/userrc, PermitOpen chỉ127.0.0.1:5900; shell/SFTP trên Air được cấp cho người quản trị. Key LAN cũ from192.168.1.8 giữ nguyên.
- Host keys/trust tái dùng từ known_hosts đã tin cậy; không thay key hoặc bỏ strict checking. Màn hình đi trong kết nối SSH đầu cuối Mini→Air. Người dùng đã tự bật Screen Sharing cho macbook; dseditgroup xác nhận macbook có quyền. Không suy kết quả đọc GroupMembership trống thành không có quyền: macOS có thể dùng membership theo UUID/nested group.

## Ba thiết lập cần giữ trên Air

Trong System Settings → General → Sharing:

| Dịch vụ | Trạng thái cần giữ |
|---|---|
| Chia sẻ Màn hình / Screen Sharing | Bật; chỉ tài khoản `macbook` |
| Đăng nhập Từ xa / Remote Login | Bật; chỉ `macbook`; quyền truy cập toàn bộ ổ đĩa tắt |
| Quản lý Từ xa / Remote Management | Tắt |

Giữ tùy chọn mọi người yêu cầu điều khiển và mật khẩu VNC riêng tắt. Screen Sharing và Remote Management không bật đồng thời. Ảnh owner cung cấp cho thấy Remote Management đang bật và quản lý Screen Sharing; sau khi owner chuyển đúng dịch vụ, phiên màn hình đã đăng nhập/điều khiển được. Quyền nhóm và local `authonly` đúng chưa đủ chứng minh chế độ chia sẻ đang đúng.

Sau đổi dịch vụ, Remote Login từng bị tắt: phiên màn hình đã mở vẫn hoạt động nhưng kết nối SSH mới bị từ chối. Owner đã bật lại Remote Login; SSH mới và bài phục hồi sau đó thành công. Khi gặp lỗi, kiểm ba thiết lập và kết nối SSH mới trước; không đoán/đổi mật khẩu hoặc bật VNC legacy để chữa.

## Dùng trên Mini

Mini giữ key/trust tại `~/Library/Application Support/CameraRemote/ssh/`, quyền600/thư mục700. Profile ở `~/.ssh/camera-management/config`. **Không đặt profile dùng ProxyJump dưới đường dẫn có khoảng trắng:** OpenSSH đang dùng trên Mini đã tái hiện lỗi child `-F` không quote; chỉ `ssh -G` không phát hiện lỗi này. Key/trust có khoảng trắng trong đường dẫn vẫn được quote trong profile.

Từ checkout project trên Mini:

```sh
python3 scripts/camera_management.py ssh
python3 scripts/camera_management.py sftp
python3 scripts/camera_management.py screen
```

`screen` mở SSH local forward chỉ127.0.0.1:15900 và Screen Sharing bằng bundle ID. Nhập mật khẩu macOS của Air trực tiếp trong app; đây không phải passphrase SSH hoặc mật khẩu Mini. Không chọn lưu mật khẩu nếu chưa muốn. Giữ Terminal mở; Enter tại Terminal để đóng tunnel. Helper kiểm listener thuộc chính child vừa tạo, dọn process group sở hữu khi Enter/interrupt/đóng Terminal, không kill PID lấy từ tài liệu.

Không cần Python cho Terminal/SFTP cơ bản sau khi đã phục hồi profile:

```sh
/usr/bin/ssh -F "$HOME/.ssh/camera-management/config" camera-air
/usr/bin/sftp -F "$HOME/.ssh/camera-management/config" camera-air
```

Live không cần Mini bật. Air cần cắm nguồn, mở nắp, đăng nhập và có Internet cho outbound2222. Quản trị màn hình dùng thêm băng thông trong quota VPS, chưa đo tốc độ Hà Nội/Lào.

## Cài lại macOS trên Mini

Theo Apple, reinstall không erase thường giữ apps/dữ liệu; cài sạch xóa ổ trong sẽ xóa dữ liệu người dùng trên ổ đó. Không tự cài lại/xóa ổ trong scope này. Đã kiểm Developer là ổ **USB ngoài/APFS**, không phải ổ trong; không giả định nó an toàn nếu người dùng chọn xóa nhầm ổ. Giữ bản sao ngoại tuyến trước khi cài.

Gói riêng đã được user tạo tại:

```text
/Volumes/Developer/Projects/camera/.local/management-recovery/mini-connections-20261103.tar.gz.gpg
```

File ciphertext0600,4862byte, SHA256 `d21c2ce404e8c9ce16c43c23d75ce6cc6deae651c8646f411a007a2e384e0a5d`. User xác nhận công cụ đã xuất thành công sau tự thử giải mã/checksum. Không có password/phrase trong chat, argv hay environment.

Gói chứa14tệp chọn lọc: profile/key/trust Mini→VPS và Mini→Air; key/trust operator VPS hiện hành; key/trust LAN Air; export secret GPG đã có bảo vệ passphrase; key/trust chỉ tải metadata backup. **Không chứa video, browser session, mật khẩu Keychain hay toàn bộ project/máy.** Không backup lại private key relay nằm trên Air vì cài lại Mini không xóa Air. Cần giữ mật khẩu gói khôi phục và passphrase từng key/GPG riêng ngoài Mini; gói ngoài không thay mật khẩu bên trong key.

Sau khi cài sạch:

1. Giữ ổ Developer/gói mã hóa; khôi phục checkout đúng nhánh `tuanminh/secure-live-v1` chứa công cụ này. Cài lại Python3/GnuPG theo nguồn đã duyệt nếu thiếu; không cần chúng cho lệnh SSH cơ bản sau phục hồi.
2. Chạy verify rồi restore dưới đây trong Terminal mới. Tự nhập mật khẩu gói tại prompt. Công cụ chỉ chấp nhận danh sách member cố định, checksum/size/type; không extract tar paths, không ghi đè key hiện có khác nội dung, map lại home/project theo tài khoản/checkout mới.
3. Nạp hai key vào Keychain mới bằng passphrase do chủ sở hữu đã lưu. Đăng nhập website lại bằng tài khoản/MFA hiện có; cookie cũ không phải điều kiện để live chạy.
4. Kiểm SSH/SFTP/màn hình/Air live. GPG private export cần import lại và passphrase GPG cũ; tác vụ mirror backup Mini cần cài lại LaunchAgent/runtime từ runbook backup, không được công cụ restore tự bootstrap. Operator22/mirror vẫn bị chặn nếu Mini ở IP không được phép.

```sh
python3 scripts/camera_management_recovery.py verify .local/management-recovery/mini-connections-20261103.tar.gz.gpg
python3 scripts/camera_management_recovery.py restore .local/management-recovery/mini-connections-20261103.tar.gz.gpg
/usr/bin/ssh-add --apple-use-keychain -t 4h "$HOME/Library/Application Support/CameraRemote/ssh/mini-jump" "$HOME/Library/Application Support/CameraRemote/ssh/air-admin"
```

Nếu gói đặt ở USB/thư mục khác, thay đúng đường dẫn. Utility không lấy passphrase từ Keychain hoặc yêu cầu gửi vào chat; không tự xoay key/account khi không giải mã được. Giữ SSH22 operator làm đường khôi phục quản trị hiện hữu.

## Kiểm chứng và rollback

Đã kiểm62Python tests/compile/help trên Mini; gồm policy từng principal, fixture child ProxyJump có đường dẫn khoảng trắng, file/parent symlink/mode guards, archive traversal/link/duplicate/size/overwrite, GPG roundtrip/sai phrase/tamper. Candidate `sshd -t/-T` thực trên VPS cho3principal×2source IP PASS; parser đã xử lý đúng output AllowUsers nhiều dòng nhưng vẫn từ chối extra/duplicate/wildcard.

Đã cài user/key/policy sau sao lưu, HUP chỉ listening parent SSH thay vì restart cả control group; live child giữ nguyên. SSH qua jump nhận Darwin/uid501 trên Air. SFTP gửi/tải fixture65536byte/hash khớp và đã dọn fixture sở hữu. Jump key thực bị chặn VPS shell, direct tới3001 và remote-listen19023. Source live vẫn H264+Opus, ghi false/no latch; loop19022 chỉ127.0.0.1.

Nghiệm thu thực tế03/11:

- Owner xác nhận điều khiển Desktop Air từ Mini sau khi sửa đúng chế độ chia sẻ. Native client hiện cửa sổ Air và `Điều khiển màn hình=on`; mật khẩu do owner nhập, không lưu vào Keychain của client.
- Gửi TERM chỉ tới PID relay bảo trì vừa đọc/xác minh ownership; LaunchAgent tự nối lại. Thời gian quan sát tiến trình/TCP là0,282s, không phải latency màn hình hoặc p95. Native camera và tunnel live giữ nguyên PID; ghi false. SSH/SFTP mới sau phục hồi tiếp tục thành công.
- Owner chuyển riêng Mini sang hotspot, Air/camera/router giữ nguyên. IPv4 public Mini khác IP nơi làm việc; SSH mới qua2222 thành công; SFTP put/get65536byte/hash khớp, fixture đã dọn. Owner xác nhận điều khiển Air qua hotspot; native client hiện đúng Air/control on. Sau bài thử owner đã đưa Mini về Wi-Fi cũ; listener thử15900 đã đóng.
- Năm LaunchAgent chạy, một native; runtime hash khớp source và plist0600. Ghi native/disk=false, không auth latch, latest record mtime giữ nguyên; số file giảm do retention cũ. Không reboot hoặc đổi mạng Air trong bài R1 này.

Đây là bằng chứng Mini khác WAN, không phải thử Air ở subnet/WAN mới, Hà Nội/Lào, mất điện toàn hệ thống hoặc reboot bộ5agent. Chưa cài lại OS thật; giữ giới hạn này khi bàn giao. Chất lượng mạng khách vẫn cần DHCP/LAN không cách ly và outbound2222.

Backup trước đổi: VPS `/var/backups/devone-management-20261103/sshd_config_camera_tunnel.before`; Air `.local/management-backup-20261103/authorized_keys.before`. Nếu rollback: bootout đúng agent mới, chờ job/PID mất và19022 nhả; kiểm manifest rồi bỏ đúng key/user/rule mới, phục hồi ingress cũ sau sshd validation/HUP. Không restore đè authorized_keys khi đã có thay đổi mới ngoài scope; không đụng live/backup key hoặc dữ liệu ghi.

Tham khảo: [Apple reinstall](https://it-training.apple.com/support/tutorials/course/sup170/), [Apple restore từ Time Machine](https://support.apple.com/en-ie/102551), [OpenSSH ProxyJump](https://man.openbsd.org/ssh_config#ProxyJump), [policy forwarding](https://man.openbsd.org/sshd_config#PermitOpen), [Screen Sharing](https://support.apple.com/en-gb/guide/mac-help/mh11848/14.0/mac/14.0).
