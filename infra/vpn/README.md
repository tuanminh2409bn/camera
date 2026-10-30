# Runbook Cấu Hình Thủ Công WireGuard: TP-Link ER605 (Standalone) ↔ Singapore VPS (M2)

> **CẢNH BÁO QUAN TRỌNG:**
> - Tài liệu này chỉ hướng dẫn quy trình kiểm tra và cấu hình **thủ công** cho mốc **M2** sau khi có quyền phê duyệt hạ tầng.
> - **Tuyệt đối không** tự động chạy lệnh thay đổi định tuyến, tường lửa (iptables/nftables/ufw), WAN hoặc nạp firmware trên router/VPS.
> - Mọi địa chỉ IP LAN camera, IP tunnel và khoá trong tài liệu này đều là **VÍ DỤ (`[VÍ DỤ / EXAMPLE]`)** dùng dải tài liệu RFC 5737 (`192.0.2.0/24`) và không chứa khoá thật.
> - Không bao giờ cấu hình `AllowedIPs = 0.0.0.0/0` chỉ để làm đường hầm hoạt động.

## 1. Sơ đồ địa chỉ mẫu (chỉ dùng làm `[VÍ DỤ / EXAMPLE]`)

| Thành phần | Địa chỉ mẫu (`[VÍ DỤ / EXAMPLE]`) | Vai trò | Ghi chú bảo mật |
|---|---|---|---|
| Camera Hikvision (LAN tại điểm đặt) | `192.0.2.10/32` (thuộc `192.0.2.0/24` `[VÍ DỤ / EXAMPLE]`) | Nguồn RTSP cổng `554/tcp` + RTP/RTCP `udp` | Không mở port-forward ra WAN; đổi mật khẩu riêng cho RTSP |
| Router TP-Link ER605 (LAN Gateway) | `192.0.2.1/24` `[VÍ DỤ / EXAMPLE]` | Cổng mặc định của camera | Quản trị chỉ từ LAN nội bộ hoặc qua kênh bastion được duyệt |
| ER605 WireGuard Interface | `10.66.0.2/32` (trong `/30` `[VÍ DỤ / EXAMPLE]`) | Peer chủ động quay số (initiator sau NAT) | Bật `PersistentKeepalive = 25` giây |
| Singapore VPS WireGuard (`wg0`) | `10.66.0.1/32` (trong `/30` `[VÍ DỤ / EXAMPLE]`) | Peer lắng nghe (`UDP 51820`) + chạy MediaMTX | MediaMTX kéo luồng từ `192.0.2.10:554` qua `wg0` |

Tài liệu chính thức tham khảo của hãng:
- [TP-Link Omada / ER605 WireGuard Configuration Guide](https://support.omadanetworks.com/en/document/13120/)

## 2. Điều kiện tiên quyết trước khi chạm vào cấu hình (Cổng M0 → M2)

1. **Sao lưu cấu hình gốc (M0):**
   - Xuất bản sao lưu cấu hình hiện tại của ER605 và camera Hikvision, lưu ở nơi bảo mật ngoài git trước khi thực hiện bất kỳ thay đổi nào.
2. **Xác nhận phiên bản phần cứng & firmware ER605:**
   - Ghi nhận chính xác hardware version (ví dụ `ER605 (UN) v2.30`) và bản build firmware vào [`docs/m0-device-inventory.md`](../../docs/m0-device-inventory.md).
   - **Không tự ý nâng cấp firmware hoặc reset router** nếu chưa có người trực tại chỗ và phê duyệt rõ ràng.
3. **Lưu ý giới hạn Allowed IPs trên ER605 Standalone:**
   - Diễn đàn kỹ thuật TP-Link (03/2026) từng ghi nhận một số bản firmware ER605 standalone có giới hạn khi khai báo nhiều subnet trong `Allowed IPs`.
   - Vì vậy, bắt đầu với **một peer duy nhất** và **dải hẹp nhất**:
     - Phía ER605 cho phép peer VPS: `10.66.0.1/32` `[VÍ DỤ / EXAMPLE]`.
     - Phía VPS cho phép peer ER605: `10.66.0.2/32, 192.0.2.10/32` `[VÍ DỤ / EXAMPLE]` (chỉ đúng IP của ER605 tunnel và IP đơn lẻ của camera, hoặc tối đa subnet riêng của VLAN camera nếu bắt buộc).

## 3. Quy trình cấu hình thủ công

### Bước 3.1. Sinh cặp khoá WireGuard riêng biệt (trên từng thiết bị/máy trạm bảo mật)

- Sinh khoá trên máy đích hoặc trong giao diện ER605; **không lưu private key vào repository, lịch sử chat hay log**.
- Chỉ trao đổi **Public Key** giữa ER605 và VPS.

### Bước 3.2. Cấu hình phía Singapore VPS (tham khảo mẫu `wg0.vps.example.conf`)

Xem file mẫu [`wg0.vps.example.conf`](wg0.vps.example.conf). Các nguyên tắc bắt buộc:
- Chỉ lắng nghe cổng UDP WireGuard đã thống nhất (ví dụ `51820/udp`).
- `AllowedIPs` chỉ liệt kê địa chỉ tunnel của ER605 (`10.66.0.2/32` `[VÍ DỤ / EXAMPLE]`) và địa chỉ IP tĩnh của camera (`192.0.2.10/32` `[VÍ DỤ / EXAMPLE]`).
- Tuyệt đối không đặt `0.0.0.0/0` trong `AllowedIPs`.

### Bước 3.3. Cấu hình phía TP-Link ER605 (Standalone Web UI)

Theo tài liệu chính thức [TP-Link Document 13120](https://support.omadanetworks.com/en/document/13120/):
1. Vào **VPN → WireGuard → WireGuard** và tạo tunnel interface:
   - Local IP Address: `10.66.0.2` / `255.255.255.252` (`[VÍ DỤ / EXAMPLE]`).
   - Listen Port: cổng cục bộ (예: `51820`).
2. Vào tab **Peers** và thêm peer Singapore VPS:
   - Endpoint: `<VPS_PUBLIC_IP_PLACEHOLDER>:51820`.
   - Public Key: `<VPS_WG_PUBLIC_KEY_PLACEHOLDER>`.
   - Allowed IPs: `10.66.0.1/32` `[VÍ DỤ / EXAMPLE]` (địa chỉ nguồn của VPS khi MediaMTX chủ động mở kết nối RTSP về camera).
   - Persistent Keepalive: `25` giây (bắt buộc vì ER605 nằm sau NAT/CGNAT tại điểm đặt camera).

### Bước 3.4. Định tuyến chiều về (Return Route), Source Address và ACL trong Tunnel

Luồng kết nối thực tế là **server-originated**: MediaMTX trên VPS (`10.66.0.1` `[VÍ DỤ / EXAMPLE]`) chủ động kết nối tới `192.0.2.10:554` `[VÍ DỤ / EXAMPLE]`.

1. **Đường đi và đường về (Return Path):**
   - Camera (`192.0.2.10` `[VÍ DỤ / EXAMPLE]`) phải có Default Gateway trỏ về địa chỉ LAN của ER605 (`192.0.2.1` `[VÍ DỤ / EXAMPLE]`) để gói tin trả lời cho `10.66.0.1` đi qua ER605 vào lại tunnel WireGuard.
   - Kiểm tra xem ER605 có giữ nguyên source IP `10.66.0.1` khi chuyển tiếp gói vào VLAN camera hay không.
2. **Phương án dự phòng SNAT hẹp (chỉ dùng khi cần thiết):**
   - Nếu camera hoặc firmware ER605 chặn gói từ subnet khác (`10.66.0.1/32`) dù đã có default gateway và ACL, mới xem xét bật **SNAT giới hạn hẹp**: chỉ áp dụng cho nguồn `10.66.0.1/32` đi tới đích `192.0.2.10/32` (cổng `554/tcp` và dải UDP RTP/RTCP).
   - Nếu bật SNAT, phải ghi rõ vào biên bản nghiệm thu vì log trên camera sẽ thấy IP LAN của ER605 thay vì `10.66.0.1`.
3. **Chính sách ACL (Access Control List) trên ER605 và VPS:**
   - **Cho phép (Allow):** `10.66.0.1/32` → `192.0.2.10/32` trên TCP `554` (RTSP) và UDP (RTP/RTCP cho chế độ `rtspTransport: udp`), cùng gói trả lời chiều ngược lại.
   - **Chặn (Deny):** Không cho phép từ tunnel đi sang toàn bộ các máy khác trong LAN tại điểm đặt camera; không cho phép từ mạng camera khởi tạo kết nối ngược vào các dịch vụ nội bộ của VPS (PostgreSQL, MediaMTX Control API `9997`, v.v.).

## 4. Kiểm chứng TCP vs UDP và Phục hồi WAN (NET-01 & NET-02)

1. **Không dùng TCP 554 để suy diễn UDP đã thông:**
   - Việc mở được socket TCP `554` chỉ chứng minh phần signaling RTSP hoặc interleaved TCP.
   - Khi thử nghiệm A/B với `rtspTransport: udp`, phải kiểm tra thực tế bằng `ffprobe` / MediaMTX xem các gói RTP/RTCP UDP có đi qua tunnel và có chiều về ổn định hay không.
2. **Đo MTU / Fragmentation trước khi chỉnh:**
   - Kiểm tra kích thước gói thực tế qua đường hầm trước khi chỉnh MTU của WireGuard (thường xoay quanh `1420` hoặc thấp hơn nếu WAN dùng PPPoE). Không sao chép cứng một giá trị MTU cho mọi nhà mạng.
3. **Bài thử tự phục hồi WAN mất 60 giây (`NET-02`):**
   - Ngắt kết nối WAN phía ER605 trong 60 giây rồi khôi phục (lặp lại 3 lần có giám sát).
   - Mục tiêu: WireGuard tự bắt tay lại và MediaMTX tự kéo lại luồng video trong ≤ 30 giây sau khi WAN hoạt động trở lại, không cần con người đăng nhập vào router hay khởi động lại tiến trình.

## 5. Truy cập quản trị an toàn (Bastion / Rollback `OPS-01`)

- SSH vào VPS chỉ cho phép xác thực bằng SSH key, giới hạn IP nguồn hoặc truy cập qua kênh VPN quản trị riêng.
- Không mở cổng quản trị web/SSH của ER605 hoặc trang quản trị camera Hikvision ra Internet công cộng.
- Mọi thay đổi cấu hình mạng từ xa phải có phương án rollback tại chỗ để tránh mất kết nối hoàn toàn tới router ở Lào.
