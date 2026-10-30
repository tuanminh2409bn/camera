# Đấu nối cho POC M0-M1

Thiết bị chưa được nối, theo xác nhận của người dùng ngày 30/10/2026. Hướng dẫn này dựa trên ảnh cổng/tem đã xem; chưa xác minh firmware hoặc nguồn PoE thực tế.

1. Cấp nguồn đúng adapter cho ER605 và switch. Camera ghi PoE 802.3at Class 4; cần xác nhận switch/adapter đáp ứng trước khi thử.
2. Dùng Ethernet nối **camera → switch cổng PoE 1**.
3. Nối **switch cổng 5 UPLINK → ER605 cổng 4 LAN**.
4. Nối **Mac mini → ER605 cổng 5 LAN** bằng Ethernet. Khi thử LAN chưa cần đổi cấu hình WAN hoặc mạng Internet đang dùng của Mac.
5. Khi thử WAN/VPN, nối **modem/ONT → ER605 cổng 1 WAN**; DHCP/PPPoE phải xác minh với nhà mạng trước khi đổi cấu hình.
6. Xác định IP camera từ DHCP lease hoặc công cụ/giao diện thiết bị được phép dùng. Ghi nhận firmware ER605/camera và sao lưu trước khi chỉnh. Không đoán camera có IP ví dụ trong tài liệu.
7. Tạo file `.local/camera-source.json` mode `0600` từ mẫu, nhập IP và tài khoản RTSP thật tại máy. Không đưa mật khẩu vào chat. Xem lệnh configure/probe/run trong README.

Chỉ xác nhận camera online khi có video RTSP thật. Tiếp theo mới đo codec và glass-to-glass; xem được trang player không chứng minh đã nhận nguồn. Dừng nếu nguồn, PoE, model hoặc đường quản trị chưa được xác minh; không reset router hoặc nạp firmware để thử đoán.

Đã thấy trên ảnh: camera `DS-2CD2643G2-LIZS2UHUN`, switch `DS-3E1505P-EI/M`, router `ER605 UN/2.30`. Firmware, PoE budget và địa chỉ IP vẫn chưa biết. Các mã định danh/khóa trên ảnh không được chép vào tài liệu này.
