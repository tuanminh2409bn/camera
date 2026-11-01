# Kiểm kê thiết bị và cấu hình nền (M0 Device Inventory)

Cập nhật: 01/11/2026. Camera đã được kích hoạt bằng HiTools trên Windows; SADP xác nhận Activated, DHCP bật, IP `192.168.0.101/24`, gateway `192.168.0.1`. Người dùng đã đăng nhập mới thành công trên web Windows tại IP này; Mac vẫn nhận 401, nguyên nhân chưa biết. HTTP Digest stateless/RTSP trên Windows chưa có kết quả. Đã dừng kiểm thử Mac và chuyển sang [bàn giao Windows](../HANDOFF_WINDOWS.md).

> **Quy tắc bảo mật:** Không ghi mật khẩu, RTSP URL chứa thông tin đăng nhập, serial nhạy cảm hoặc WireGuard private key vào tài liệu này. `.local/` trên Mac đã xóa theo yêu cầu. Khi tạo lại trên Windows phải dùng NTFS ACL riêng tư; 0600 chỉ áp dụng POSIX, không thay thế kiểm tra ACL trên Windows.

## 1. Camera IP Hikvision

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Họ model (Datasheet) | Hikvision `DS-2CD2643G2-LIZS2U` | `DS-2CD2643G2-LIZS2UHUN` khớp tem và phản hồi SADP 31/10 | Đã quan sát trực tiếp; UI còn chờ |
| Phiên bản Firmware | Xác nhận từ thiết bị | `V5.7.23 build 260320` do camera báo qua SADP | Đã nhận SADP; chưa đối chiếu UI |
| Nguồn cấp điện | PoE 802.3at Class 4 theo tem camera; kiểm tra switch cấp đủ | `PENDING` | `PENDING` |
| Địa chỉ IP LAN | IP thật theo thiết bị; POC hiện dùng LAN ER605 `192.168.0.x` | SADP 01/11: `192.168.0.101/24`, gateway `192.168.0.1`, DHCP=true, Activated=true | TCP 80/443/554/8000 mở, HTTP root 200, Windows web thành công; lease cần kiểm tra lại khi bắt đầu |
| Xác thực và phiên web | Đọc cấu hình thực, không hạ bảo vệ | HTTP/RTSP digest/MD5, RTSP 554; giới hạn 50, ảnh một admin row online; IP/MAC filters tắt theo người dùng | Web Windows đã vào; HTTP Digest stateless/RTSP Windows PENDING |
| Luồng thử nghiệm ưu tiên | Chọn `102` nếu hỗ trợ 720p/25fps, nếu không dùng `101` | `PENDING` | `PENDING` |
| Định dạng mã hoá (Video Codec) | H.264 thường (tắt H.264+ / H.265+ / Smart Codec) | `PENDING` | `PENDING` |
| Độ phân giải & Tốc độ khung hình | `1280x720` (720p) @ `25 fps` | `PENDING` | `PENDING` |
| H.264 Profile & B-frame | Profile `Baseline` (nếu có), **0 B-frame** (kiểm chứng bằng ≥ 60s frame thực) | `PENDING` | `PENDING` |
| GOP (I-frame interval) & Bitrate | Khởi điểm GOP `25` frame (1s), đối chứng `12-13` frame (~0,5s); `1,5 Mbps` CBR | `PENDING` | `PENDING` |
| Âm thanh (Audio) | **Tắt (Disabled)** trên luồng RTSP | `PENDING` | `PENDING` |
| Bản sao lưu cấu hình gốc (Backup) | Xuất file cấu hình trước khi chỉnh thông số POC | `PENDING` | `PENDING` |

## 2. Switch PoE và Mạng LAN tại điểm đặt

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Model Switch PoE | Xác nhận thực tế tại hiện trường | `DS-3E1505P-EI/M`, tem đã đối chiếu; nguồn vào ghi 54V/0,92A | Đã khớp model qua SADP; PoE budget thực còn PENDING |
| Firmware / IP switch | Kiểm tra trực tiếp | SADP báo `V3.0.13 build 241120`; IP `10.20.0.254/24`, gateway `10.20.0.1`, DHCP tắt | Đã nhận SADP |
| Chuẩn PoE & Ngân sách công suất (PoE Budget) | Đủ công suất cho camera cả khi bật hồng ngoại/đèn ban đêm | `PENDING` | `PENDING` |
| Tốc độ cổng LAN & Bộ đếm lỗi (CRC/Drops) | 100/1000 Mbps Full Duplex, không tăng gói lỗi | `PENDING` | `PENDING` |
| Nguồn điện dự phòng (UPS) | Ghi nhận hiện trạng | `PENDING` | `PENDING` |

## 3. Router VPN TP-Link ER605

| Hạng mục | Giá trị mục tiêu / Dự kiến | Giá trị thực tế kiểm kê | Trạng thái |
|---|---|---|---|
| Model & Phiên bản phần cứng | TP-Link `ER605` | `ER605 UN/2.30` theo tem đã đối chiếu | Quan sát ảnh; firmware còn PENDING |
| Phiên bản Firmware & Build Date | Xác nhận hỗ trợ WireGuard ở chế độ Standalone | `PENDING` | `PENDING` |
| Chế độ vận hành | Standalone (không phụ thuộc Omada Controller ngoài) | `PENDING` | `PENDING` |
| Địa chỉ LAN Gateway | Quan sát trước dừng Mac | `192.168.0.1`; khi còn cắm dây, Mac Ethernet `192.168.0.100/24`, link active 1 Gbps | Bằng chứng lịch sử route/ifconfig; UI router chưa đăng nhập; Ethernet Mac hiện không có link |
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

## Trạng thái bàn giao mạng

Camera đi DHCP LAN ER605; switch quản trị vẫn subnet `10.20.0.0/24`. Các địa chỉ camera `10.20.0.10`, `192.168.1.64`, `169.254.39.226` chỉ là lịch sử trước khi kích hoạt/đấu lại. Không sao chép route/alias cũ sang Windows.

Mac đã bỏ IP/route thử, giữ Wi-Fi ưu tiên và Ethernet DHCP; runtime/mật khẩu/báo cáo riêng đã xóa. Laptop Windows là máy phát triển kế tiếp, nối ER605 LAN 5, giữ Wi-Fi cho Internet. Xem W0/W1 trong bản bàn giao trước khi chạy POC hoặc chỉnh mạng.
