# Quản trị Air từ Mini và khôi phục sau cài lại Mini

Triển khai R1 ngày03/11/2026 theo yêu cầu người dùng. **SSH và SFTP qua VPS đã kiểm thành công; Screen Sharing chưa nghiệm thu**: user báo không đăng nhập được, đang xác minh đường xác thực macOS. Bảng kết quả chưa triển khai. Không tự đổi mật khẩu, bật VNC legacy, FileVault/auto-login hoặc reboot để chữa lỗi.

## Đường kết nối và quyền

- Air chủ động mở SSH bảo trì riêng tới ingress VPS2222. Agent `com.camera.air-maintenance-relay` RunAtLoad/KeepAlive/throttle30s, sau đăng nhập macOS; SSH key/config/known_hosts tại `.local/ssh/maintenance-relay/` trên Air. Tự động không có nghĩa tự mở khóa FileVault/bật nguồn.
- VPS chỉ mở reverse listener **127.0.0.1:19022**, chuyển tới SSH22 trên Air. Không public19022/5900/15900, không thêm public port mới. Cổng22 operator VPS vẫn chỉ IP nơi làm việc; key backup Mini giữ giới hạn cũ.
- Ba principal được ingress2222 cho phép: `devone-air` giữ đúng2reverse18554/19996; `camera-maint-relay` chỉ remote-listen19022; `camera-maint-jump` chỉ direct-forward tới127.0.0.1:19022. Tất cả public-key only/no shell/no PTY/root. Hai account mới home `/var/lib/<user>`, shell nologin, key restrict và permitlisten/permitopen tương ứng.
- Mini vào Air qua jump rồi xác thực bằng key Air riêng; jump key không đủ để đăng nhập Air. Air key mới chỉ chấp nhận từ127.0.0.1, không agent/X11/userrc, PermitOpen chỉ127.0.0.1:5900; shell/SFTP trên Air được cấp cho người quản trị. Key LAN cũ from192.168.1.8 giữ nguyên.
- Host keys/trust tái dùng từ known_hosts đã tin cậy; không thay key hoặc bỏ strict checking. Màn hình đi trong kết nối SSH đầu cuối Mini→Air. Người dùng đã tự bật Screen Sharing cho macbook; dseditgroup xác nhận macbook có quyền. Không suy kết quả đọc GroupMembership trống thành không có quyền: macOS có thể dùng membership theo UUID/nested group.

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

Chưa nghiệm thu Screen Sharing, Mini ở WAN khác hoặc relay tự phục hồi. Không gọi các phần chưa đo là PASS. User đã báo nhập mật khẩu Air không vào được; đã xác nhận quyền macbook có hiệu lực/RFB server đáp ứng, đang chờ kiểm authonly một lần do owner tự nhập tại Air. Không đổi password hoặc bật legacy authentication.

Backup trước đổi: VPS `/var/backups/devone-management-20261103/sshd_config_camera_tunnel.before`; Air `.local/management-backup-20261103/authorized_keys.before`. Nếu rollback: bootout đúng agent mới, chờ job/PID mất và19022 nhả; kiểm manifest rồi bỏ đúng key/user/rule mới, phục hồi ingress cũ sau sshd validation/HUP. Không restore đè authorized_keys khi đã có thay đổi mới ngoài scope; không đụng live/backup key hoặc dữ liệu ghi.

Tham khảo: [Apple reinstall](https://it-training.apple.com/support/tutorials/course/sup170/), [Apple restore từ Time Machine](https://support.apple.com/en-ie/102551), [OpenSSH ProxyJump](https://man.openbsd.org/ssh_config#ProxyJump), [policy forwarding](https://man.openbsd.org/sshd_config#PermitOpen), [Screen Sharing](https://support.apple.com/en-gb/guide/mac-help/mh11848/14.0/mac/14.0).
