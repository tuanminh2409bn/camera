# Đấu nối POC trên Windows

Sau khi dừng Mac ngày 01/11/2026, bắt đầu từ [HANDOFF_WINDOWS.md](../HANDOFF_WINDOWS.md).

## Sơ đồ

1. Camera → switch PoE 1.
2. Switch UPLINK 5 → ER605 LAN 4.
3. Windows → ER605 LAN 5.
4. Wi-Fi Windows giữ Internet cho Codex.
5. Mac không cần trong tuyến mới.

Camera đã Activated; lần cuối DHCP 192.168.0.101/24, gateway 192.168.0.1. Dò lại khi lease/mạng thay đổi; không đoán theo IP cũ 10.20.0.10, 192.168.1.64 hoặc 169.254.39.226. Switch quản trị vẫn 10.20.0.254/24.

## Chuẩn bị

- Intel 82579LM cần có link. Code 10 trước đó đã được người dùng xử lý bằng Disable/Enable riêng NIC.
- Đọc IP/route/metric trước khi chỉnh; nếu ER605 chưa có WAN, default Ethernet có thể làm Codex mất Internet. W1 trong bản bàn giao có quy trình ưu tiên Wi-Fi và rollback.
- Ghi giá trị trước/sau mọi thay đổi mạng; không sửa DNS/gateway hoặc tắt adapter hàng loạt.
- Kiểm tra PoE thực khi cảnh tối/đèn bật; tem/model không chứng minh đủ công suất.
- Backup camera/router trước thay đổi. Chưa có backup được nghiệm thu.

## Xác thực

Ảnh Windows: admin vào được .101; web limit 50, một dòng online; HTTP/RTSP digest/MD5; RTSP 554. Người dùng xác nhận IP/MAC filters tắt và không có log để xác định lỗi.

Mac vẫn 401 cả web/API/RTSP và thử IP nguồn riêng; nguyên nhân chưa biết. Người dùng khẳng định mật khẩu đúng. Không reset/kích hoạt lại, đổi mật khẩu hay tắt bảo vệ để thử đoán. Windows HTTP Digest stateless và RTSP chưa có kết quả.

## Profile camera

H.264 thường, 1280×720, 25fps, chỉ video/no audio; đo 0 B-frame thật; bắt đầu GOP 25, CBR khoảng 1,5 Mbps. Đọc khả năng main/sub trước chọn 101/102. Backup trước, chỉ chỉnh khi người dùng bắt đầu phiên Windows.

Không mở camera/admin/RTSP public, không tự đổi WAN/firmware/router/ACL. Chưa cần máy onsite bổ sung.

## Mac đã dọn

Alias/route thử được gỡ; runtime, công cụ, báo cáo và private credential đã xóa. Giữ Wi-Fi ưu tiên, DHCP Ethernet bình thường; không lặp lại alias/route chẩn đoán cũ. Source/tests giữ để port Windows; xem checkpoint cho giới hạn bằng chứng.
