# Đấu nối hiện tại: Mac mini phát triển, Air chạy camera

Đọc [bản bàn giao](../HANDOFF_MAC_MINI.md) trước thao tác. Sơ đồ này phản ánh tuyến đã có hình thật, thay cho các tuyến thử trước đây.

## Đấu nối

1. Camera → cổng PoE1 trên switch Hikvision.
2. Switch UPLINK5 → cổng LAN bộ phát Wi-Fi đang dùng.
3. Mac mini và MacBook Air → cùng mạng Wi-Fi đó.
4. Air đặt cùng camera, cắm nguồn, mở nắp và giữ đăng nhập để phiên ghi hoạt động.

Camera static192.168.1.64/24; tại snapshot Mini192.168.1.8, Air192.168.1.12. ER605 không tham gia tuyến; không cắm lại để thử mật khẩu hoặc đổi DHCP/IP camera. IP quản trị switch không phải địa chỉ nguồn video.

## Xem và ghi

Camera kênh101 H264 Baseline720p/25fps/no audio/CBR2048Kbps/GOP25. MediaMTX v1.21.3 trên Air nhận một nguồn RTSP/TCP, WebRTC/playback chỉloopback. Recording ghi SSD nội bộ khoảng24h gần nhất; xem [runbook](air-recording-service.md).

Safari/VLC và native ingest đã có bằng chứng; không dùng lại raw RTSP client bị401 hoặc liên tục thử mật khẩu. Không mở camera/admin/RTSP ra Internet.

## Mạng Mac mini

Thứ tự gốc đã khôi phục **Ethernet → Thunderbolt Bridge → Wi-Fi**. Ethernet DHCP/inactive; Internet hiện qua Wi-Fi. Giữ nguyên priority này. Không thêm alias/host route hoặc chạy lại helper chẩn đoán cũ.

Từng có restart khi chạy helper; chưa xác định nguyên nhân. Khôi phục network priority không phải bằng chứng sửa được lỗi phần cứng/hệ thống. Nếu thay dây/mạng cần đọc trạng thái thực trước; không đổi route/DNS/gateway tự động.

## Chưa nghiệm thu

PoE budget trong cảnh đêm, counters LAN/CRC/drop, UPS, độ bền24h và phục hồi mất điện/WAN chưa có đủ bằng chứng. Full backup camera mã hóa đã lưu private trước chỉnh profile, chưa kiểm restore. Không cập nhật firmware/reset camera/router hoặc đổi mạng chỉ để khớp kế hoạch cũ.
