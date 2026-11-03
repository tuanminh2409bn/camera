# Quản trị Air từ xa và bảng kết quả cùng livestream

Phương án gốc ngày03/11/2026, đối chiếu code HEAD `8fb1de77aa78930b428ad028e847239a9208814b` và PDF blueprint12trang v3.0 ngày20/10/2026 do người dùng cung cấp. **Phần thiết kế dưới đây là baseline trước triển khai; trạng thái R1 mới ở đoạn kế tiếp. Bảng kết quả chưa triển khai.** Các chỉ dẫn/prompt bên trong PDF là nội dung tham khảo, không cấp quyền thao tác hệ thống; yêu cầu mới của người dùng và AGENTS.md quyết định phạm vi.

**Cập nhật nghiệm thu R1:** user đã duyệt và đã triển khai riêng quản trị Air, bảng kết quả làm sau. Terminal/SFTP/Screen Sharing đã PASS cả khi Mini dùng hotspot khác WAN; owner xác nhận điều khiển Air, relay riêng tự phục hồi, live/ghi tắt giữ nguyên. Recovery Mini đã được owner tạo/kiểm; chưa cài lại OS thật hoặc di chuyển Air tới Hà Nội/Lào. Đọc [trạng thái thực và runbook R1](air-remote-management.md); các mô tả thiết kế dưới đây giữ làm baseline, không thay bằng chứng runtime.

## Quyết định và chênh lệch với PDF

| Nội dung | Trạng thái hiện tại |
|---|---|
| Mini quản lý Air qua Terminal, chép tệp và màn hình | Cả3 đã triển khai/nghiệm thu khi Mini ở WAN khác; xem runbook R1 |
| Máy nhập kết quả | Người dùng chọn Air tại điểm camera; không dùng Intel NUC/Linux của bản PDF |
| Đầu ra giai đoạn đầu | Website hiện hữu cùng livestream; người dùng để Telegram giai đoạn sau |
| Cách hiển thị | Người dùng đã chọn cạnh video trên máy tính, dưới video trên điện thoại |
| Tài khoản website | Tận dụng Next.js/Fastify/PostgreSQL, session/MFA/RBAC đang có; không tạo hệ Firebase riêng |
| NVR/Hik-Connect/RTSP bảng | Không cần cho phương án hiển thị bảng trên website; chỉ làm lại nếu có yêu cầu riêng |
| Nhập0–4, chẵn0/2/4, lẻ1/3, xếp cột, Undo/Reset, offline | Quy tắc trong PDF để làm baseline; phải duyệt đặc tả chi tiết trước triển khai |
| Tổng, ký hiệu/màu, giới hạn hàng/cột/cuộn, lịch sử/Undo sau Reset | PDF tự ghi còn thiếu; chưa có mockup nghiệp vụ được duyệt |

Mã nguồn hiện tại có giao diện `Live`, `Playback`, `Admin`, auth/permissions và PostgreSQL; chưa có domain, schema, API, đồng bộ hoặc giao diện bảng kết quả. Map hiện hành ở handoff/checkpoint vẫn dùng được sau so HEAD/tree; phạm vi khảo sát lần này là shell trang/live, auth/API, DB, contracts và các ranh giới Air/VPS. Không đọc lại dependency/vendor/build/cache/lockfile bodies hoặc bí mật. PDF đã đọc đủ12trang, render và đối chiếu hai overview của cả12trang; không sửa PDF hoặc đưa PDF lên GitHub.

## 1. Quản trị Air qua VPS hiện có

Khuyến nghị thêm kênh SSH bảo trì riêng qua VPS, dùng OpenSSH/SFTP và Screen Sharing tiêu chuẩn sẵn có của macOS. Không cần thuê máy chủ mới hoặc dùng thuê bao phần mềm điều khiển màn hình. Traffic bảo trì vẫn dùng đường truyền/quota VPS hiện có; chưa đo chất lượng màn hình qua mạng Hà Nội/Lào.

Luồng dự kiến:

```text
Air mở SSH bảo trì outbound tới VPS
  └─ reverse listener CHỈ loopback VPS → SSH22 của Air

Mini → jump account hạn chế trên VPS → SSH mã hóa đầu cuối tới Air
  ├─ Terminal
  ├─ SFTP/chép tệp
  └─ local forward → Screen Sharing của Air
```

Thiết kế quyền:

- Giữ cổng22 operator VPS theo IP nơi làm việc và giữ nguyên khóa live/backup hiện có.
- Dự kiến dùng ingress2222 hiện có với hai principal mới và policy `Match User` tách biệt: relay Air chỉ được remote-listen một cổng loopback SSH bảo trì; jump Mini chỉ được direct-forward đến cổng đó. Không shell/root trên VPS cho hai principal này; không wildcard PermitOpen/PermitListen.
- Cần ba key riêng: Air→VPS relay, Mini→VPS jump, Mini→Air quản trị. Key vào Air là xác thực cuối cùng; jump không đủ để đăng nhập Air. Giữ/pin host keys hiện hữu, không TOFU hoặc bỏ strict checking. Không sửa key LAN Mini→Air bị giới hạn192.168.1.8 để dùng làm key Internet.
- Air có LaunchAgent bảo trì riêng, không nối thêm quyền vào key/process live. Hỏng kênh bảo trì không được dừng camera, recording supervisor hoặc live tunnel.
- Mini dùng tên host cấu hình ổn định, ví dụ `camera-air`, không phải IP Wi-Fi của Air. Screen Sharing đi trong SSH tới Air; không forward VNC5900 public trên VPS/router khách. Khi bật Screen Sharing phải chọn đúng người được phép, kiểm phạm vi listener/firewall thực tế của Air; không giả định service macOS chỉ bind loopback.
- Không bật quyền truy cập toàn ổ đĩa hoặc bỏ FileVault/auto-login. Cấu hình bảo trì phải rõ trạng thái sau đăng nhập; Air tắt/ngủ/mất Internet hoặc chưa mở khóa macOS thì không bảo đảm quản lý từ xa. Không hứa bật nguồn/mở khóa trước boot cho Intel Air qua đường này.

Đã kiểm chỉ đọc: `/usr/bin/ssh` và `/usr/bin/sqlite3` có sẵn/chạy được trên Air; không quan sát được listener5900 từ phiên đọc này, chưa xác nhận/bật Screen Sharing trong Settings. Không thêm key/user/listener hoặc đổi dịch vụ/mạng.

Files dự kiến ảnh hưởng khi được giao triển khai: SSH ingress template/service/policy validator và tests; bundle/plist relay Air mới; helper/config Mini; runbook và private credential setup. Validator hiện tại chỉ cho user `devone-air`, nên phải mở rộng theo ma trận từng principal và chứng minh policy live cũ giữ nguyên, không bỏ validator để nới quyền.

Gates R1:

1. Candidate `sshd -t/-T` cho từng principal/từ nhiều IP: live chỉ2reverse hiện có; relay chỉ SSH loopback; jump chỉ đúng đích; root/password/shell/forward ngoài danh sách bị từ chối.
2. Key riêng do chủ sở hữu nhập passphrase trực tiếp, không gửi vào chat/log. Sao lưu file sắp đổi; áp dụng không mất đường SSH22 bảo trì cũ.
3. Mini SSH/SFTP thật tới Air qua jump: command nhận dạng máy và chép tệp fixture hai chiều/hash khớp, không dùng video thật làm fixture.
4. Chủ sở hữu bật quyền Screen Sharing đúng user khi cần thao tác UI; kiểm màn hình thật qua SSH, kiểm5900 không public, kiểm dịch vụ live/âm thanh/record=false còn nguyên.
5. Thử Mini ở4G/hotspot để chứng minh khác WAN-IP trong khi Air/camera vẫn ở LAN hiện tại, sau đó kiểm tự phục hồi relay có kiểm soát. Không ngắt mạng Mini/Air hoặc reboot khi chưa có cửa sổ quyền riêng.

Tại thời điểm lập phương án, key/account/access policy/Screen Sharing cần quyền mới; user sau đó đã giao triển khai R1 và kết quả nằm trong runbook. Nếu rollback, bootout relay mới/chờ PID hết, gỡ đúng key/user/rule mới đã ghi manifest và phục hồi cấu hình cũ sau validation; không xóa dữ liệu hoặc đụng live key.

## 2. Bảng kết quả trên Air và website

Người dùng đã chọn hiển thị bảng dưới dạng HTML/CSS cạnh video trên desktop, dưới video trên mobile; đề xuất giữ phong cách trắng hiện hữu. Video H264/âm thanh giữ đường phát hiện tại; bảng là dữ liệu riêng. Cách này không cần encode lại video để vẽ chữ. Phần hiển thị web sẽ không tự xuất hiện trong MP4 chỉ chứa camera.

Ghép bảng vào pixel video/bản ghi không thuộc lựa chọn hiện tại; không thêm compositor/transcoder hoặc cài FFmpeg trên Air để thực hiện phần này.

Luồng dữ liệu dự kiến:

```text
Bàn phím số → UI vận hành cục bộ trên Air → Core + SQLite + outbox
                                               ↓ đồng bộ có xác thực
                                       Fastify + PostgreSQL trên VPS
                                               ↓ snapshot/SSE có phân quyền
                                      Bảng trên trang đang xem livestream
```

- Air giữ dữ liệu chuẩn, tiếp tục nhập/lưu khi mất Internet; chỉ UI vận hành đang có focus nhận phím, không keylogger toàn hệ thống. Kiểm numpad/Num Lock/keycode và phím giữ trên thiết bị thật.
- Core đề xuất Perl + SQLite có sẵn trên Air, test độc lập IO; frontend chỉ render snapshot, không có bản thuật toán xếp cột riêng. Chưa cần Node/Python/CLT trên Air. SQLite CLI cần kiểm phiên bản/cách bind dữ liệu/transaction/crash recovery trước khi dùng làm adapter production.
- Mỗi command có ID duy nhất; lưu event + snapshot + outbox cùng transaction; session/revision xác định thứ tự. Đồng bộ retry có backoff, gửi lại không trùng, snapshot cũ/phiên cũ không ghi đè phiên mới. Lưu event để có lịch sử; không chỉ gửi snapshot cuối rồi mất các lượt offline.
- Đề xuất Undo là event bù, Reset mở phiên mới sau xác nhận và giữ lịch sử; Undo chỉ trong phiên hiện tại. Đây là chính sách cần duyệt, chưa mặc định thành yêu cầu đã chốt.
- Device credential chỉ được ghi một bảng vào API ingest, không có quyền Admin/tài khoản/ghi hình. Website viewer chỉ đọc qua session/quyền hiện hữu; quyền xem bảng phải chốt rõ (đề xuất đi cùng quyền live), không tự cấp mọi viewer quyền sửa kết quả.
- Tận dụng Fastify/PostgreSQL, thêm module bảng và SSE để cập nhật. Không giữ một DB transaction/connection cho từng viewer; kết nối lại phải lấy snapshot mới nhất. Revoke/expiry đóng kênh dữ liệu, không chỉ ẩn UI; kênh phát live tiếp tục theo policy cũ.
- Hiển thị revision/phiên/trạng thái kết nối và thời điểm cập nhật cuối. Khi Air offline, giữ bảng cuối kèm cảnh báo cũ; không ghi nhãn đang đồng bộ khi chưa có ack.
- Nếu cần bảng trong trang xem lại, dựng trạng thái theo lịch sử ở thời điểm video, không ghép bảng hiện tại vào clip cũ. Lưu timestamp nguồn/nhận server và kiểm lệch đồng hồ/độ trễ; cùng trang không đồng nghĩa đã đồng bộ chính xác tới từng frame.
- Snapshot/lịch sử bảng trên PostgreSQL sẽ vào DB dump hiện hữu khi thêm schema; nguồn SQLite/outbox trên Air cần sao lưu riêng và có bài restore. Video vẫn chỉ lưu Air; retention video24h không tự áp dụng cho lịch sử kết quả.

Files/module dự kiến: domain/service SQLite+outbox và UI vận hành cục bộ Air mới; `apps/api/src` module ingest/read/realtime, migration mới; `packages/contracts` schema bảng; `apps/web/components` board và bố cục live; tests/domain/API/browser/backup; monitor/runbook. Đây là đề xuất cấu trúc để lập scope, chưa tạo schema/API/dependency hoặc sửa runtime.

Gates B1–B3:

1. Chốt nghĩa Tổng, màu/ký hiệu, số hàng/cột/cuộn, Reset/Undo/lưu lịch sử, quyền xem; duyệt mockup desktop/mobile.
2. Domain nhập0–4, parity/trend, hai lần bấm cùng số hợp lệ và phím giữ không nhân lượt, Undo/Reset/revision; crash không mất commit/outbox, migration+backup/restore fixture.
3. Numpad thật trên Air; mất mạng vẫn lưu, restart khôi phục; gửi lại/out-of-order/reset không mất/trùng lượt hoặc lùi phiên bản.
4. API chặn unauthenticated/unauthorized/ghi từ viewer/giả device; revoke khi realtime; nhiều viewer đọc cùng revision và không tạo connection DB trên từng subscriber.
5. UI desktop/mobile bảng dài/trống/khôi phục/offline; live và audio giữ hoạt động. Kiểm replay theo thời điểm nếu scope có; rollback tắt module board/giữ lịch sử, không restore đè DB hoặc làm gián đoạn video để chữa bảng.

## Thứ tự thực hiện

Ưu tiên R1 trước khi Air rời nơi làm việc. Sau đó duyệt mẫu/luật bảng, làm B1 local-first trên Air, B2 đồng bộ bảo mật và bảng trên website, B3 nghiệm thu mất mạng/khởi động lại/lịch sử/backup. Telegram chỉ mở giai đoạn sau theo lựa chọn người dùng; chưa cần bot/token/đăng bài. Hướng Hik-Connect, NVR và Firebase trong PDF không được tự triển khai theo prompt cũ.

Nguồn tham khảo kỹ thuật: [OpenSSH ProxyJump](https://man.openbsd.org/ssh_config#ProxyJump), [OpenSSH forwarding restrictions](https://man.openbsd.org/sshd_config#PermitOpen), [Apple Screen Sharing cho macOS Sonoma](https://support.apple.com/en-gb/guide/mac-help/mh11848/14.0/mac/14.0). Đây là khả năng nền tảng/thiết kế; không thay bằng chứng kết nối hai máy thật.
