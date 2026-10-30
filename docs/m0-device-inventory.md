# Kiểm kê thiết bị và cấu hình nền (M0 Device Inventory)

Cập nhật: 30/10/2026. Trạng thái: **PENDING** (chưa kết nối phần cứng camera và router ER605).

> **Quy tắc bảo mật:** Không ghi mật khẩu, RTSP URL chứa thông tin đăng nhập, serial nhạy cảm hoặc WireGuard private key vào tài liệu này. Mọi thông tin mật chỉ lưu trong thư mục riêng tư `.local/` (mode `0600`).

## 1. Camera IP Hikvision

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Họ model (Datasheet) | Hikvision `DS-2CD2643G2-LIZS2U` | `DS-2CD2643G2-LIZS2UHUN` đọc trên ảnh `images/1.jpeg`; cần đối chiếu UI | `PENDING` |
| Phiên bản Firmware | Xác nhận từ trang quản trị cục bộ | `PENDING` | `PENDING` |
| Nguồn cấp điện | PoE 802.3at Class 4 theo tem camera; kiểm tra switch cấp đủ | `PENDING` | `PENDING` |
| Địa chỉ IP LAN (ví dụ mẫu) | `192.0.2.10/24` `[VÍ DỤ / EXAMPLE]` | `PENDING` (lưu IP thật trong `.local/camera-source.json`) | `PENDING` |
| Luồng thử nghiệm ưu tiên | Kênh `102` (sub-stream) đối chứng `101` (main-stream) | `PENDING` | `PENDING` |
| Định dạng mã hoá (Video Codec) | H.264 thường (tắt H.264+ / H.265+ / Smart Codec) | `PENDING` | `PENDING` |
| Độ phân giải & Tốc độ khung hình | `1280x720` (720p) @ `25 fps` | `PENDING` | `PENDING` |
| H.264 Profile & B-frame | Profile `Baseline` (nếu có), **0 B-frame** (kiểm chứng bằng ≥ 60s frame thực) | `PENDING` | `PENDING` |
| GOP (I-frame interval) & Bitrate | Khởi điểm GOP `25` frame (1s), đối chứng `12-13` frame (~0,5s); `1,5 Mbps` CBR | `PENDING` | `PENDING` |
| Âm thanh (Audio) | **Tắt (Disabled)** trên luồng RTSP | `PENDING` | `PENDING` |
| Bản sao lưu cấu hình gốc (Backup) | Xuất file cấu hình trước khi chỉnh thông số POC | `PENDING` | `PENDING` |

## 2. Switch PoE và Mạng LAN tại điểm đặt

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Model Switch PoE | Xác nhận thực tế tại hiện trường | `DS-3E1505P-EI/M`, tem ảnh `images/4.jpg`; nguồn vào ghi 54V/0,92A | Quan sát ảnh; PoE budget thực còn PENDING |
| Chuẩn PoE & Ngân sách công suất (PoE Budget) | Đủ công suất cho camera cả khi bật hồng ngoại/đèn ban đêm | `PENDING` | `PENDING` |
| Tốc độ cổng LAN & Bộ đếm lỗi (CRC/Drops) | 100/1000 Mbps Full Duplex, không tăng gói lỗi | `PENDING` | `PENDING` |
| Nguồn điện dự phòng (UPS) | Ghi nhận hiện trạng | `PENDING` | `PENDING` |

## 3. Router VPN TP-Link ER605

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Model & Phiên bản phần cứng | TP-Link `ER605` | `ER605 UN/2.30` theo tem `images/5.jpg` | Quan sát ảnh; firmware còn PENDING |
| Phiên bản Firmware & Build Date | Xác nhận hỗ trợ WireGuard ở chế độ Standalone | `PENDING` | `PENDING` |
| Chế độ vận hành | Standalone (không phụ thuộc Omada Controller ngoài) | `PENDING` | `PENDING` |
| Địa chỉ LAN Gateway (ví dụ mẫu) | `192.0.2.1/24` `[VÍ DỤ / EXAMPLE]` | `PENDING` | `PENDING` |
| Cấu hình WireGuard Peer | 1 peer hẹp tới VPS (`10.66.0.1/32` `[VÍ DỤ / EXAMPLE]`), `PersistentKeepalive = 25s` | `PENDING` | `PENDING` |
| Bản sao lưu cấu hình gốc (Backup) | Xuất file backup trước khi cấu hình VPN/ACL | `PENDING` | `PENDING` |

## 4. Đường truyền WAN / ISP tại điểm đặt Camera và VPS

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Vị trí đặt camera hiện tại | Lab (Việt Nam) hoặc Thực địa (Lào) | `PENDING` | `PENDING` |
| Nhà mạng (ISP) & Loại kết nối WAN | FTTH / IP động / CGNAT / PPPoE | `PENDING` | `PENDING` |
| Băng thông Upload thực tế giờ cao điểm | ≥ 3× bitrate đỉnh của luồng (ví dụ ≥ 6 Mbps cho đỉnh 2 Mbps) | `PENDING` | `PENDING` |
| Máy chủ VPS mục tiêu (M2) | Singapore (8 vCPU, 16 GB RAM, 1 Gbps NIC cho tải đầy đủ; hoặc VPS test M2) | `PENDING` | `PENDING` |
| RTT / Packet Loss / Jitter tới Singapore | Đo cả giờ bình thường và giờ cao điểm | `PENDING` | `PENDING` |

## Bằng chứng ảnh và phạm vi xác minh

Đã xem 6 ảnh trong `images/` do người dùng thêm trong lúc triển khai. Chỉ ghi model/thông số cần cho đấu nối; không sao chép serial, MAC, device key hoặc mã QR vào tài liệu. Ảnh cho thấy switch có PoE 1-4, uplink 5; router có WAN 1, LAN 4-5. Nhãn No MicroSD không chứng minh camera không có khe thẻ. Quan sát tem không chứng minh thiết bị đã cấp điện, firmware, codec hoặc VPN đang hoạt động. Các ảnh gốc được giữ nguyên và không đưa vào commit triển khai.
