# Kiểm kê thiết bị và cấu hình nền

Cập nhật 02/11/2026. [Checkpoint](implementation-status.md) là nơi ghi kết quả và giới hạn; IP/PID/dung lượng chỉ là snapshot. Không lưu serial, QR/device key, mật khẩu hoặc private key trong repo.

## Thiết bị và vai trò

| Thành phần | Giá trị đã biết | Bằng chứng/giới hạn |
|---|---|---|
| Máy phát triển |Mac mini, macOS26.7, arm64; `/Volumes/Developer/Projects/camera` |Đọc trực tiếp Mini; Codex làm trực tiếp |
| Runtime onsite |MacBook Air2017/MacBookAir7,2, Intel, macOS14.8.9/Sonoma qua OpenCore |SSH đã xác minh host fingerprint; không update OS/OCLP tự động |
| Camera |Hikvision DS-2CD2643G2-LIZS2UHUN, V5.7.23 build260320, Activated |SADP/HTTP deviceInfo và UI; không công bố định danh riêng |
| Camera LAN |Static192.168.1.64/24, gateway192.168.1.1, DHCPfalse |Tuyến AP Wi-Fi đã nhận video; không dùng IP lịch sử để sửa cấu hình |
| Switch |Hikvision DS-3E1505P-EI/M; firmware lịch sửV3.0.13 build241120 |Model/PoE1–4 vàUPLINK5 đã quan sát; IP quản trị chưa đọc lại trong lần bàn giao |
| Router/AP hiện tại |Bộ phát Wi-Fi cùng LAN với switch/Mini/Air |Model/ISP và vị trí Lào chưa được xác định |
| ER605 |UN/2.30 theo ảnh tem |Không tham gia tuyến hiện tại; firmware/WireGuard/backup chưa nghiệm thu |

## Video và backup

| Hạng mục | Giá trị thực tế | Trạng thái |
|---|---|---|
| Kênh |101/main |MediaMTX ingest thật trên Air |
| Codec/profile |H264 Baseline, H264+/SVCoff |HTTP readback và bản ghi thật |
| Kích thước/fps |1280×720, configured25fps, observed25,033fps |Mẫu65,0329giây/1.628frames |
| B-frame/audio |0B,0audio trong mẫu |CODEC-01 PASS |
| GOP/bitrate |ConfiguredGOP25/CBR2048Kbps; observedGOPmin2/median25/max25 |Không nói mọi GOP đều bằng25 |
| Latency |Người dùng chấp nhận trực quan theo mục tiêu1giây |USER-ACCEPTED/VISUAL, chưa có p95 đã đo |
| Full camera backup |File mã hóa3.507.904byte trên Mini/Air, hash khớp |Có trước khi chỉnh720p; user giữ mật khẩu; restore chưa thử |

## Runtime và lưu trữ

MediaMTX v1.21.3 native Intel, FFprobe9.0.2 Intel chỉ trong project Air, Perlcore5.34.1. Air chưa có Python developer toolchain được xác minh; không kích hoạt cài CLT ngầm.

Snapshot17:27:39+07:61tệp/914.709.916byte, trống99.648.942.080byte. Ghi SSD nội bộ, reserve15GiB, fMP4part1s/segment1m/retention1d; cleaner tối đa30phút mỗi chu kỳ. Chưa có dữ liệu endurance24h.

## Mạng và nguồn điện

Mini192.168.1.8/Wi-Fi en1, Air192.168.1.12, camera192.168.1.64. Thứ tự dịch vụ Mini đã trả về Ethernet → Thunderbolt Bridge → Wi-Fi; Ethernet đanginactive. KeySSH bị giới hạn nguồnMini hiện tại. Không tự thay alias/route/SSH policy khi DHCP thay đổi.

PoE802.3at Class4 theo tem camera, nguồn switch54V/0,92A theo ảnh. Công suất thực ở cảnh đêm, lỗi cổng, UPS và recovery mất điện/WAN còn PENDING. Ảnh tem gốc được giữ local trong `images/`, bịignore và không đưa lênGitHub.
