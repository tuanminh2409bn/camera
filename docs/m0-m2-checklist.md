# Danh mục kiểm tra các cổng M0–M2 (M0–M2 Gate Checklist)

Tài liệu này cụ thể hóa điều kiện qua cổng cho giai đoạn **M0 → M1 → M2** theo [`KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md`](../KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md).
**Quy tắc bắt buộc:** Không đánh dấu `PASS` cho bất kỳ hạng mục phần cứng, mạng hoặc độ trễ nào khi chỉ mới chạy dữ liệu giả lập (synthetic).

## 1. Cổng M0: Kiểm kê thiết bị và khóa thiết kế POC

| Mã kiểm tra | Nội dung yêu cầu | Bằng chứng cần có | Trạng thái hiện tại |
|---|---|---|---|
| `M0-INV-01` | Xác nhận đúng mã model/suffix và firmware thực tế của camera Hikvision | Cập nhật bảng trong [`m0-device-inventory.md`](m0-device-inventory.md) | `PENDING` |
| `M0-INV-02` | Xác nhận hardware version (ví dụ `UN v2.30`) và firmware của router TP-Link ER605 | Cập nhật bảng trong [`m0-device-inventory.md`](m0-device-inventory.md) | `PENDING` |
| `M0-INV-03` | Xác nhận ngân sách PoE (PoE budget), cáp mạng và tốc độ cổng LAN không bị drop | Số liệu kiểm tra thực tế trên switch/router | `PENDING` |
| `M0-BAK-01` | Sao lưu cấu hình gốc của camera và ER605 trước khi chỉnh sửa | Bản backup lưu bảo mật ngoài git | `PENDING` |
| `M0-SW-01` | Bộ công cụ POC cục bộ (`scripts/poc.py`), kiểm tra cấu hình/redaction/permissions và unit tests | `python3 -m unittest discover -s tests -v` | `Verified (Local Software Unit Tests)` |

## 2. Cổng M1: LAN Baseline, Codec Gate và Sàn độ trễ

| Mã kiểm tra | Tham chiếu Kế hoạch | Điều kiện đạt (Pass Criteria) | Lệnh / Quy trình kiểm chứng | Trạng thái hiện tại |
|---|---|---|---|---|
| `M1-SW-SMOKE` | POC Local Runtime | MediaMTX `v1.21.3` chạy trên loopback `127.0.0.1`, parse hợp lệ file config `0600` (`moq: no`), trang player tích hợp mở được và tiến trình dừng sạch sẽ | `python3 scripts/poc.py smoke` | `VERIFIED (Native v1.21.3; chưa có video nguồn)` |
| `CODEC-01` | Mục 5.1 & 9.3 | Luồng thật từ camera đạt đúng `H.264`, `1280x720`, `25 fps`, **không có audio**, **0 B-frame quan sát được** trong mẫu ≥ 60 giây (~1.500 frame), đo được GOP thực tế | `python3 scripts/poc.py probe --source-file .local/camera-source.json --duration 60` | `PENDING (Chưa kết nối camera & thiếu ffprobe trên PATH)` |
| `M1-PLAYER-01` | Mục 5.3 & 7 (M1) | Trình duyệt thực mở `http://127.0.0.1:8889/live`, hiển thị hình ảnh chuyển động thực từ camera qua WebRTC loopback | Mở trình duyệt trên máy trạm kết nối LAN với camera | `PENDING (Chưa kết nối camera)` |
| `LAT-01` | Mục 7 (M1) & 9.1 | Đo độ trễ quang học glass-to-glass trong LAN (hướng tới LAN p95 ≤ 400 ms để còn ngân sách cho WAN), thử cả cảnh sáng và tối, chạy ≥ 60 phút cho profile được chọn | Theo [`latency-measurement-procedure.md`](latency-measurement-procedure.md) | `PENDING (Chưa kết nối camera)` |

## 3. Cổng M2: Singapore VPS và Đường hầm WireGuard

| Mã kiểm tra | Tham chiếu Kế hoạch | Điều kiện đạt (Pass Criteria) | Lệnh / Quy trình kiểm chứng | Trạng thái hiện tại |
|---|---|---|---|---|
| `HW-01` | Mục 9.3 | Reboot PoE/camera/router có người hỗ trợ tại chỗ: camera online lại, WireGuard tự kết nối lại, cấu hình được giữ nguyên | Thực hiện theo [`../infra/vpn/README.md`](../infra/vpn/README.md) | `PENDING` |
| `NET-01` | Mục 5.2 & 9.3 | VPS Singapore đọc được luồng RTSP thật của camera qua tunnel WireGuard liên tục ≥ 2 giờ; so sánh A/B giữa `rtspTransport: tcp` và `udp`; không mở public RTSP/admin của camera hay router | Chạy `poc.py probe` & MediaMTX trên VPS qua giao diện `wg0` | `PENDING` |
| `NET-02` | Mục 2, 7 & 9.3 | Giả lập đứt WAN 60 giây rồi khôi phục, lặp lại 3 lần có giám sát: tunnel và luồng video tự phục hồi (hướng tới ≤ 30 giây sau khi WAN có lại) | Ghi thời gian phục hồi từng lần vào báo cáo | `PENDING` |

## 4. Điều kiện mở khóa các mốc tiếp theo (M3+)

- Chỉ khi **toàn bộ `CODEC-01`, `LAT-01`, `HW-01`, `NET-01`, `NET-02`** có bằng chứng thực tế đạt yêu cầu thì mới chuyển sang **M3** (thử nghiệm trình duyệt/mạng hai quốc gia Lào & Việt Nam trên HTTPS) và **M4A/M4B** (xây dựng Fastify API, PostgreSQL, Next.js và Recording).
