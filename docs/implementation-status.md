# Checkpoint bàn giao Windows

Cập nhật 01/11/2026, Asia/Ho_Chi_Minh.

## Quyết định hiện tại

Người dùng dừng mọi kiểm thử trên Mac; dọn runtime/công cụ tải về/mật khẩu/báo cáo; giữ source/tests/PDF/kế hoạch/ảnh, giữ Wi-Fi ưu tiên; bàn giao Windows và publish GitHub. Không chạy lại camera, unittest, smoke hoặc probe trong lần dọn.

Đọc [HANDOFF_WINDOWS.md](../HANDOFF_WINDOWS.md). Việc tiếp theo trên Windows là W0 — hỗ trợ native của CLI, rồi W1/W2. Yêu cầu curl Windows cũ chưa có kết quả và không được tự tiếp nối sau lệnh dừng.

## Snapshot và project map

- Source baseline giữ nguyên: 644572402302ec9af31f1ee84f0ac4269870e37c.
- SHA256 scripts/poc.py: 08c8f4e2fd3991ac1818ecfcb54c03e2340a48adde2794d4c9eee31f30cea635.
- scripts/poc.py: validate/private write, hash-pinned installer, renderer, bounded runtime, FFprobe/analyzer.
- tests/test_poc.py: validation, redaction, archive/path confinement, timeout/cleanup, codec evidence.
- infra/: mẫu loopback/Docker và VPN, chưa phải production deployment.
- PDF 14 trang, kế hoạch gốc 307 dòng được giữ.
- Maintained source/tests/config/docs đã được đọc trong triển khai gốc; tái sử dụng map sau đối chiếu HEAD/diff. Secrets, binary, cache và generated evidence không được tính là source đã đọc.
- Ảnh chỉ được dùng xác định model/cổng; không publish serial/MAC/device key.

Không sửa hành vi application source trong lần bàn giao. Các kết quả dưới đây là lịch sử Mac, không phải bằng chứng Windows.

## Bằng chứng trước lệnh dừng

Môi trường lịch sử: macOS arm64, Python 3.9.6, Git 2.55.0, MediaMTX v1.21.3. FFprobe portable n4.4.1 dùng riêng trong chẩn đoán; không cài trên PATH và nay đã xóa. Docker/FFmpeg/shellcheck không có trên PATH ở lần kiểm tra gốc; không cài system package cho POC.

| Hạng mục | Kết quả |
|---|---|
| make check macOS arm64 | PASS: compileall, CLI help, 22 unittest; recheck 31/10: 1,387 giây |
| python3 scripts/poc.py smoke | PASS native MediaMTX v1.21.3, loopback listener/API/player, process dừng sạch |
| Darwin arm64 archive | Hash khớp pin; binary/runtime nay đã xóa |
| Video trong smoke | media_decoded=false, camera_connected=false |
| Discovery | DS-2CD2643G2-LIZS2UHUN, V5.7.23 build 260320, Activated, DHCP .101/24, gateway .1 |
| Windows web | Người dùng báo đăng nhập mới thành công; có ảnh cấu hình .101 |
| Mac web/API/RTSP | 401, kể cả Python/curl và RTSP DESCRIBE có giới hạn |
| IP nguồn .250/32 | Được cho phép riêng; một credential-bearing DESCRIBE vẫn 401; alias đã gỡ |
| Sau gỡ alias | DHCP .100/24, default Wi-Fi en1/.1.1, HTTPS Internet 200, TCP camera nguồn .100 |
| Cấu hình đã đối chiếu | IP/MAC filters tắt; giới hạn 50, một admin row; HTTP/RTSP digest/MD5 |
| curl guard | max-redirs=0 chưa gửi credential; mock xác nhận limit 1 cho một Digest; lần thật 1 Authorization →401 |
| Windows Digest/RTSP | Chưa có kết quả, dừng theo yêu cầu |
| CODEC/LAT/VPN/mobile/200 peers | Chưa xác minh |

Người dùng khẳng định mật khẩu đúng. Chưa xác định nguyên nhân; không kết luận camera cấm macOS hoặc yêu cầu đổi mật khẩu/tắt bảo vệ để thử đoán.

Worker Argon dùng worktree riêng: một lần hết thời gian, một lần bị chặn command trong headless; không bypass quyền. Người dùng cho Codex hoàn tất/review/kiểm tra độc lập source. Worktree/task/log cũ đã dọn; source hoàn tất giữ ở main.

## Dọn Mac

Đã xóa .local: private JSON, YAML sinh, báo cáo/log, helper nhập mật khẩu/kiểm tra IP, archive, MediaMTX native, FFprobe portable và gói HP chưa cài. .runtime không còn. Worker inactive được xác nhận trước khi dọn worktree/branch/task/packet/log; cache Python riêng của project được xóa.

Không còn MediaMTX/ffprobe/Python POC chạy hoặc IP/route thử do task để lại theo kiểm kê. Ethernet giữ DHCP; Wi-Fi ưu tiên theo lựa chọn mới nhất, không đảo về Ethernet-first đã từng làm mất Internet.

Kiểm kê cuối: Ethernet ở DHCP Configuration, en0 inactive/không có IPv4; Wi-Fi en1 active, default route qua en1; thứ tự Wi-Fi → Ethernet → Thunderbolt Bridge. Không có route 10.20.*, 192.168.1.64/.250 hoặc 192.168.0.250 do thử nghiệm để lại. Không thay cấu hình quản trị thiết bị để đạt trạng thái này.

Giữ PDF/kế hoạch/scripts/tests/infra/Makefile/ảnh; không gỡ Git/Codex/Python/gh có sẵn, không đổi PATH, firmware/WAN/router/camera trong lần dọn. Mật khẩu không được giữ để chuyển GitHub.

## Khoảng trống Windows

Installer chỉ Darwin tar.gz; đường binary chưa có .exe; private-file code dùng 0600/0700/os.fchmod; runtime selectors trên pipe. Phải xử lý thật cho NTFS/Windows, không bỏ guard hoặc mock thành PASS. Windows native, Docker và WSL chưa nghiệm thu.

Repo đích: https://github.com/tuanminh2409bn/camera . Công khai; chỉ publish source/docs/placeholder. Không publish ảnh tem/raw evidence/binary/credentials.

## Kiểm tra của lần bàn giao

Chỉ kiểm kê/dọn tài nguyên, soát tài liệu/liên kết, git diff --check, quét bí mật và đối chiếu publish. Không chạy lại tests hoặc xác thực camera. Phiên Windows sau phải ghi kết quả thực, không suy diễn từ tài liệu.

Kết quả soát trước commit: 11 Markdown không có liên kết file nội bộ hỏng hoặc code fence lẻ; git diff --check đạt; hash CLI giữ nguyên. 22 file trong index không chứa runtime/ảnh/binary/key; quét 39 blob lịch sử và index không thấy mẫu token/private key có độ tin cậy cao. Trước khi xóa credential đã đối chiếu giá trị password thật với toàn bộ 39 blob lịch sử, không có khớp; giá trị đó không được in hoặc ghi vào báo cáo. Sáu ảnh thiết bị vẫn ở Mac và được ignore.
