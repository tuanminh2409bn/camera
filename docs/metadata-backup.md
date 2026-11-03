# Sao lưu tài khoản và cấu hình

Đã triển khai03/11/2026 theo quyền người dùng. Video vẫn chỉ trên Air. Live và bản ghi mới có âm thanh; backup trong tài liệu này là metadata, không chứa video.

- VPS: `devone-backup.timer`, hằng ngày02:15 Asia/Ho_Chi_Minh, Persistent=true, giữ14ngày trong `/var/backups/devone`0700. Service timeout15phút, lỗi không xóa bản tốt trước đó. Theo dõi `systemctl status devone-backup.timer devone-backup.service` và `status.json` riêng tư.
- Mini: LaunchAgent `com.camera.metadata-backup`, RunAtLoad và mỗi3600giây khi đăng nhập, giữ30ngày trong `~/Library/Application Support/CameraBackup/archives`. Log riêng0600 tại `~/Library/Logs/CameraMetadataBackup/mirror.log`. Exit0 đã kiểm. Khi Mini tắt, lịch VPS vẫn chạy; Mini mở/đăng nhập lại sẽ lấy các bản còn trên VPS. Đây chưa phải bằng chứng reboot thật.
- Tác vụ nền Mini dùng khóa SSH riêng0600 trong runtime trên ổ người dùng. Forced command chỉ nhận `list` hoặc `stream metadata-...zip.gpg`, giới hạn IP nơi làm việc, restrict/no PTY/no forwarding/no shell. Đã kiểm tải được bản mã hóa và lệnh `id` bị từ chối. Giữ known_hosts đã tin cậy; không bỏ strict checking. Khi đổi IP cần review firewall/tunnel/key, không tự mở rộng nguồn.

Mỗi bản `metadata-<UTC>-<nonce>.zip.gpg` gồm custom-format PostgreSQL dump, `server.json`, `mediamtx.json`, `air-gateway.json` và manifest SHA256. Dump/ZIP được stream thẳng qua GPG trên VPS, không tạo file dump plaintext. File ciphertext/sidecar0600 được đổi tên sau khi hoàn tất; khóa chống chạy trùng và checksum bảo vệ mirror. Retention chỉ dọn cặp tên metadata mới có descriptor hợp lệ, giữ backup cũ `camera-*.tar.gz.gpg` và tệp khác.

VPS chỉ có public key GPG. Private key trên Mini có passphrase người dùng tự đặt, tại `.local/backup-keyring`; bản export khóa riêng vẫn được mã hóa trong `.local/production-backups/metadata-secret-key.asc`. Người dùng cần giữ thêm bản export này ở nơi an toàn khác Mini và lưu passphrase riêng. Không gửi khóa/passphrase vào chat. Không tự tải khóa lên dịch vụ khác. Quên passphrase hoặc mất cả private key/export sẽ không giải mã được backup.

Đã kiểm chính bản `metadata-20261103T073257Z-fcad6a53.zip.gpg`: giải mã, checksum/membership ZIP, restore bằng role `devone` không superuser vào DB tên ngẫu nhiên riêng; 2users/1Admin, MFA giải mã thành công,21audit events. DB tạm được drop sau kiểm; không restore đè `devone`. Restore check tạo ZIP plaintext tạm0600 trong thư mục0700 trên Mini và dọn khi xong. Không coi đây là phục hồi toàn VPS hoặc kiểm restore cấu hình camera.

Nguồn vận hành: [backup](../scripts/metadata_backup.py), [client/khóa GPG](../scripts/metadata_backup_client.py), [cài mirror](../scripts/install_backup_mirror.py), [forced download](../scripts/metadata_backup_download.py), [restore check](../scripts/metadata_restore_check.py), [service](../infra/server/devone-backup.service.example), [timer](../infra/server/devone-backup.timer.example). Runtime VPS ở `/opt/devone/ops`; tạo bản thủ công bằng `python3 /opt/devone/ops/metadata_backup.py create` qua SSH operator. Mirror thủ công chạy client đã cài với action `mirror`, không yêu cầu passphrase giải mã.

Clone mới không có key/runtime. GnuPG cần cài đúng nguồn đã duyệt; chạy client `setup` trong Terminal để chủ sở hữu tự nhập passphrase, tạo key/bản đầu và restore check. Cài mirror cần quyền rõ ràng tạo SSH credential bằng `scripts/install_backup_mirror.py`. Không dùng operator key trong LaunchAgent trên ổ Developer: macOS đã chặn bằng TCC. Không cấp Full Disk Access để né lỗi này.

Khi cần phục hồi thật: chọn bản đã kiểm checksum, chuẩn bị VPS/DB riêng, nhập passphrase trực tiếp trên Mini và dùng khóa AES trong backup để kiểm MFA. Phục hồi đè production, đổi credential hoặc xoay khóa cần quyền riêng. Không đặt passphrase vào argv/environment, không in cấu hình/SQL dump và không dùng database production làm mục tiêu thử.

Giới hạn: chưa đi qua một đêm để chứng minh lần02:15 kế tiếp; đã kiểm timer enabled/next-fire và chạy service thật thành công. Mirror cần Mini đăng nhập và đường SSH từ IP được phép. Bản sao trên cùng Mini không thay cho bản khóa an toàn ngoài máy; không có dịch vụ lưu trữ ngoài nào được mua.
