# Các cổng triển khai hiện tại

Theo [kế hoạch v2](../KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md), cập nhật tuyến đã được người dùng chọn: Mac mini phát triển, Air onsite nhận/ghi camera qua AP Wi-Fi. ER605/WireGuard là phương án tham khảo, không tự nối lại để đạt gate cũ.

Không đánh dấu phần cứng/mạng/latency PASS bằng unit test hoặc synthetic. Snapshot và lệnh kiểm tra nằm trong [checkpoint](implementation-status.md).

## M0 — thiết bị và nền phần mềm

| Gate | Kết quả hiện tại | Phần còn thiếu |
|---|---|---|
| M0-INV-01 camera |Model/firmware/IP/profile đã đọc từ camera và có video |Không công bố định danh riêng |
| M0-INV-02 tuyến/router |Tuyến switch→AP Wi-Fi→Air đã xem được |ISP/modelAP/vị trí thực Lào chưa xác định; ER605 không trong tuyến |
| M0-INV-03 nguồn/cổng |Camera nhận PoE và có link/video |PoE budget đêm, CRC/drop/UPS chưa nghiệm thu |
| M0-BAK-01 backup |Full encrypted camera backup đã lưu trước chỉnh720p, hash khớp hai máy |Restore chưa thử; router backup chưa có |
| M0-SW-01 phần mềm |CLI Python và supervisor có unit fixtures/guard tests |Xem số lượng/lần chạy mới nhất ở checkpoint; không dùng unit để suy ra WAN |

## M1 — LAN và ghi cục bộ

| Gate | Bằng chứng | Trạng thái |
|---|---|---|
| Native runtime |MediaMTX v1.21.3/API/loopback/player/cleanup trên Air |PASS cho phạm vi đã thử |
| CODEC-01 |Mẫu ghi thật65,0329s/1.628frames,H.264 Baseline 720p/25,033fps,0B/0audio,GOPmedian/max25 |PASS recorded-frame sample |
| M1-PLAYER-01 |Safari Air có hình WebRTC chuyển động, người dùng xác nhận |USER-VERIFIED; Codex không trực tiếp quan sát UI Air |
| LAT-01 |Người dùng miễn đo quang học và chấp nhận tốc độ bằng mắt |USER-ACCEPTED/VISUAL; không có p95 đã đo |
| RECORD-01 |Bản ghi tăng/xoay, playback401/200, xuấtMP4, người dùng xem clip cũ bằngVLC |PASS native POC; chưa có Admin website |
| RETENTION-01 |Fixture25h bịxóa,1h còn; recordDeleteAfter1d |PASS cơ chế; chưa qua đủ24h dữ liệu thật |
| GUARD-01 |Lock/redaction/authlatch/diskpause/cleanup fixtures; native hot-pause giữ live |PASS phạm vi kiểm tra; chưa cố làm đầy SSD thật |
| ENDURANCE-01 |Service session đang chạy từ 16:32+07 |PENDING24h; chưa tự phục hồi qua logout/reboot |

## M2 — đường ra server và recovery

Publisher outbound có xác thực/mã hóa từ Air là phương án tiếp theo cần chốt. Chưa thuê/deployVPS hoặc càiVPN; không phát public RTSP/admin camera.

| Gate | Điều kiện cần có | Trạng thái |
|---|---|---|
| NET-01 |Server được duyệt nhận video thật qua đường đã chốt, liên tục≥2h, có kiểm tra packet loss/jitter và A/B khi cần |PENDING |
| NET-02 |Mất WAN60s/khôi phục lặp3lần có giám sát, ghi thời gian phục hồi |PENDING |
| HW-01 |Camera/AP/Air phục hồi sau mất điện/reboot, cần người hỗ trợ tại chỗ và quyền thao tác |PENDING |
| OPS-01 |Kênh bảo trì từ xa có xác thực, quyền hẹp và rollback |PENDING |

Sau khi có bằng chứng mạng/recovery phù hợp mới mở website Admin/RBAC/HTTPS và đánh giá trình duyệt/mạng Lào–Việt Nam/tải200peers. Quy trình đo quang học được giữ làm tham khảo; không coi lựa chọn miễn đo LAN là số đo WAN.
