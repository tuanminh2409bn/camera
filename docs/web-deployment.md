# Web v1 — triển khai và vận hành

**Âm thanh/backup03/11:** live hiện thêm FFmpeg AAC→Opus trên VPS qua RTSP publish chỉ127.0.0.1:18555; H264 copy. Bản ghi AAC chỉ trên Air. Người dùng đã nghe xác nhận live/xem lại; ghi mới đã tắt lại. [Checkpoint](v1-implementation.md), [backup định kỳ](metadata-backup.md). Các mô tả chưa triển khai bên dưới là snapshot cũ.

**Cập nhật 03/11/2026:** người dùng đã mua VPS DigitalOcean Basic Regular SGP1 và `lao6789.com`, đồng thời cho phép triển khai bản đầu, cấu hình firewall/DNS/HTTPS và kết nối Air. Các đoạn chọn mua và tuyên bố chưa được triển khai phía dưới là snapshot trước phê duyệt; xem [checkpoint](v1-implementation.md) cho trạng thái và bằng chứng mới. Không suy từ bản chạy đầu thành nghiệm thu 200 peers, độ bền hay mạng Lào.

## Quyết định và phạm vi

Đã được duyệt trong chat: Next.js, Fastify, PostgreSQL, Caddy; live Internet, Admin/RBAC, xem lại từ Air, mức tối đa 200 live viewers đồng thời và 8 giờ/ngày; người dùng xác nhận tải thực tế thường thấp hơn, chưa có số liệu trung bình. Nghiệm thu tại nơi làm việc hiện tại. Lào là giai đoạn sau. Ngày 03/11 người dùng duyệt triển khai bản đầu lên VPS/domain đã mua, gồm firewall, HTTPS và kết nối Air; không suy ra quyền mua thêm dịch vụ hoặc chạy bài tải phát sinh chi phí.

Nguồn video: camera → MediaMTX trên Air → kết nối SSH do Air chủ động mở → MediaMTX server → WebRTC tới browser. Server phân phối một luồng Air cho nhiều người xem. HTTPS chỉ vận chuyển giao diện, đăng nhập và WHEP signaling; Node không chuyển tiếp từng frame live.

Xem lại: browser có session → API kiểm quyền → SSH reverse forward → Perl gateway loopback trên Air → playback native. Video đi qua RAM/socket có backpressure, không có file/cache video trên server. Danh sách thời gian được cache RAM 10 giây để hạn chế đọc SSD Air khi nhiều người mở trang. Air offline thì không xem lại được. Không có đồng bộ bù.

Chọn reverse SSH cho bản đầu vì Air đã có OpenSSH và Perl core; không cần cài Node/Python/VPN lên Air, không đổi cấu hình/khởi động lại phiên ghi hiện tại. Tuyến cũ WHIP không được tự bật. Bản sửa supervisor vẫn phân biệt lỗi forward với lỗi camera để không tạo auth latch sai nếu dùng publisher sau này.

## Mua hạ tầng ngoài Việt Nam: ưu tiên Singapore sau khi làm rõ tải tối đa

**200 người × 8 giờ/ngày là mức tối đa, không phải dự báo tải trung bình.** Đề xuất Đức trước đó đã dùng kịch bản cực đại làm cơ sở chọn traffic không giới hạn; sau khi người dùng làm rõ, Singapore là region ưu tiên để dành thêm dư địa cho độ trễ gần1giây. Chưa thuê hoặc trả tiền cho bất kỳ phương án nào. Không thuê server tại Việt Nam; domain Cloudflare giữ nguyên.

Tách hai đại lượng khi chọn gói:

- **Công suất đỉnh:** 2.048 Mbps × 200 =409.6 Mbps payload; dự trù15% thành471.04 Mbps. Dù chỉ đạt200 người trong thời gian ngắn, vẫn phải kiểm năng lực phát ở mức này. Cổng danh nghĩa≥1Gbps là tiêu chí ban đầu, không tự chứng minh throughput thực tế hoặc CPU đủ tải.
- **Traffic tháng:** mỗi người xem một giờ dùng0.9216GB payload, khoảng1.05984GB khi cộng15%. Tính theo tổng giờ xem của từng người; không mặc định lấy200×8×30.

| Ví dụ tải trung bình mỗi ngày, trong30ngày | Traffic tháng, đã cộng15% |
|---|---|
| 20 người ×2 giờ |1.27TB |
| 50 người ×3 giờ |4.77TB |
| 100 người ×4 giờ |12.72TB |
| 200 người ×8 giờ, kịch bản cực đại |50.87TB |

Các dòng là ví dụ tính toán, chưa phải số liệu người dùng đã xác nhận. Chưa cộng playback/download hoặc biến động ngoài15% dự trù. Bài nghiệm thu200 peer trong8giờ có thể dùng khoảng1.70TB riêng; tính cả traffic kiểm thử vào tháng đầu.

**Đề xuất hiện tại: [DigitalOcean Droplet tại Singapore/SGP1](https://www.digitalocean.com/pricing/droplets), 4vCPU/8GiB RAM.** [Availability của hãng](https://docs.digitalocean.com/products/droplets/details/availability/) có cả Basic và CPU-Optimized tại SGP1. Hai mức để lựa chọn:

| Plan | CPU / RAM / disk | Transfer gồm trong tháng đầy đủ | Giá niêm yết trước thuế |
|---|---|---|---|
| CPU-Optimized Regular — ưu tiên độ ổn định CPU |4vCPU dedicated,8GiB,50GiB SSD |5,000GiB ≈5.37TB |$84/tháng |
| Basic Regular — phương án tiết kiệm cần benchmark trước production |4vCPU shared,8GiB,160GiB SSD |5,000GiB ≈5.37TB |$48/tháng |

Ưu tiên CPU-Optimized nếu vẫn giữ mục tiêu chất lượng trong ngân sách3triệu/tháng; không cần64GB RAM chỉ để phục vụ luồng H264 passthrough. Basic là lựa chọn giảm chi phí nếu bài tải đỉnh chứng minh CPU chia sẻ đáp ứng. Chưa gói nào được coi là đã đạt200 viewer thật. DigitalOcean công bố [trần throughput2Gbps cho Droplet thường](https://docs.digitalocean.com/products/droplets/details/limits/); đó là mức tối đa, không phải cam kết tối thiểu471Mbps tới mọi ISP. CPU-Optimized Regular không phải Premium10Gbps.

[Bandwidth billing](https://docs.digitalocean.com/platform/billing/bandwidth/) tính outbound vượt quota$0.01/GiB, inbound miễn phí. Quota cộng dồn theo thời gian tồn tại server trong tháng và gộp theo team; cần tính trường hợp tạo giữa tháng, traffic kiểm thử và playback. Theo mô hình bảng trên: 50 người×3giờ/ngày dùng khoảng4,442GiB, nằm trong5,000GiB nếu server tồn tại trọn tháng và không có tải khác;100 người×4giờ/ngày dùng khoảng11,845GiB, giá CPU-Optimized thành khoảng$152.45 trước thuế, không còn phù hợp ngân sách. Vì chưa biết tải trung bình, giá$84 không phải cam kết tổng hóa đơn cố định. Chọn trả theo tháng/usage, theo dõi và cảnh báo traffic/chi phí trước khi tăng tải. Không coi cảnh báo là hard spending cap.

[SLA CPU Droplet](https://www.digitalocean.com/sla/cpu-droplets) công bố99.99% uptime từng instance với service credit theo điều kiện; không bảo đảm độ trễ video, hiệu năng ứng dụng, Air hoặc đường truyền ISP. Cần kiểm checkout/tỷ giá/thuế và tổng ngân sách trước thanh toán. Không tạo account/credential, cài server, mở public hoặc chạy bài tải trả phí trong bước chọn gói.

### Bằng chứng đường truyền và giới hạn kết luận

Đo nhẹ từ Mini hiện tại,5gói mỗi endpoint: `fsn1-speed.hetzner.com` tại Đức có RTT min/avg/max189.444/190.555/193.686ms; `sin.icmp.hetzner.com` có54.993/58.181/59.331ms. Cả hai mẫu nhận5/5gói. [Locations của Hetzner](https://docs.hetzner.com/cloud/general/locations/) xác nhận FSN1 tại Đức và SIN tại Singapore. Đây là các đầu thử Hetzner, **không phải kết quả DigitalOcean hoặc mạng Lào**, và không phải số đo độ trễ hình. Endpoint DigitalOcean speedtest cũ không resolve DNS trong lần thử; không ghi kết quả ping DigitalOcean giả hoặc coi endpoint thử đã nghỉ là lỗi của region.

Kết quả cho thấy mẫu đường Singapore hiện tại có RTT thấp hơn đáng kể. Đức vẫn có thể đạt hình gần1giây nếu tổng pipeline đáp ứng, nhưng không được suy từ ping; đường xa làm giảm dư địa khi gặp jitter/mất gói. Vì ưu tiên trải nghiệm tại VN/Lào và tải tháng chưa chắc lớn, không tiếp tục khuyên mua AX41 tại Đức làm phương án chính. Chỉ xem lại phương án Đức nếu nhu cầu traffic tăng mạnh và bài camera/WAN chứng minh trải nghiệm chấp nhận được.

Ưu tiên nghiệm thu tại nơi làm việc: camera thật → Air → server Singapore → browser; đo riêng lúc ít người và lúc200 peer, xem xét startup, độ trễ hình, frame/packet loss và tài nguyên. Mạng Lào vẫn thiết kế/đo sau theo yêu cầu đã chốt. Không suy từ uptime SLA thành cam kết hình≤1giây; không yêu cầu lại bài optical đã được người dùng miễn.

### Các phương án khác

- [Hetzner AX41/FSN1](https://www.hetzner.com/dedicated-rootserver/ax41/) từng được xem với giá hiển thị€59/tháng, setup€0 trước VAT,1Gbps dedicated/unlimited. Ưu điểm traffic lớn; vị trí Đức kém phù hợp hơn với ưu tiên độ trễ hiện tại. Không còn là lựa chọn mặc định.
- [OVH Singapore](https://www.ovhcloud.com/en-sg/vps/vps-singapore/) có quota APAC rồi giảm còn10Mbps. Sau khi làm rõ tải tối đa, không loại chỉ vì thấp hơn51TB, nhưng phải chọn quota đủ dùng; giảm10Mbps sẽ không đáp ứng đỉnh200 người.
- [Contabo fair-use](https://help.contabo.com/en/support/solutions/articles/103000271195-are-there-any-bandwidth-or-traffic-limits-at-contabo-) cho phép throttle theo chính sách; không coi unlimited là cam kết đỉnh500Mbps.
- [OneAsiaHost](https://oneasiahost.com/) có SGKVM-8G4vCPU/8GB/20TB tại$40/tháng với uplink10Gbps burst; SLA công bố99.5%. Có lợi thế traffic/giá, nhưng không xác nhận throughput duy trì từ uplink burst hoặc coi SLA này tương đương99.99%. Không tự chốt nhà cung cấp này chỉ dựa vào quota lớn.

Domain: [Cloudflare Registrar pricing](https://pricing.registrar.cloudflare.com/) snapshot `.win` đang hiển thị đăng ký ưu đãi$4.18, gia hạn$5.18/năm; `.com`$11.17/năm đăng ký và gia hạn; `.xyz`$12.30 năm đầu và$11.20 gia hạn, không rẻ hơn`.com` ở snapshot này. Nếu ưu tiên giá thấp, chọn tên`.win` còn trống theo giá checkout; nếu ưu tiên tên quen thuộc thì`.com`. Không mua tên premium hoặc add-on ngoài nhu cầu. Bật2FA/DNSSEC; domain/DNS không quyết định đường truyền video. Dùng DNS-only tới Caddy cho bản đầu, không mặc định đưa tải video qua dịch vụ proxy/CDN. Chi phí tên miền tính riêng, giá/tỷ giá/VAT kiểm lại lúc mua.

## Phần mềm và kiểm thử tại Mini

Node 26.13.0 LTS, npm 11.20.0 được ghi trong repo sau cập nhật bảo mật 03/11. `@types/node` ghim nhánh24 tương thích API sử dụng vì dependency `thread-stream` chưa tương thích tên type đã bỏ ở nhánh26; **không tắt skipLibCheck**. Dependencies/lockfile ghim chính xác; `.npmrc` tắt lifecycle scripts. Argon2, Next và esbuild chạy được bằng prebuilt đã cung cấp trên Mini và trong build Linux đã kiểm; không bật toàn bộ install scripts để chữa lỗi.

```sh
cd /Volumes/Developer/Projects/camera
npm ci --ignore-scripts
make check
npm run check
python3 scripts/poc.py install-mediamtx --platform darwin_arm64
npm run test:browser
```

Browser tests dùng Chrome có sẵn, một PostgreSQL tạm trong `.local/test-databases/`, MediaMTX arm64 riêng tại các cổng loopback18889/19997/18189, API3001 và Next3000. Fixture H.264 là màn hình “STREAM IS OFFLINE” do native sinh, **không phải camera thật**. Fake Air chỉ kiểm UI; bài này không chứng minh phát lại video Air. Không chạy nếu các cổng đang được dịch vụ khác sử dụng. Test không tái sử dụng server cũ.

PostgreSQL embedded chỉ là devDependency. Hydration symlink được giới hạn trong package đã kiểm; không tạo user hệ thống, không dùng database hiện hữu. Runtime PostgreSQL production cài độc lập.

## Secret và bootstrap production — chỉ thực hiện sau phê duyệt

1. Dùng user hệ thống riêng `devone`, database/user `devone` chỉ loopback, không superuser. Migration dùng transaction và version table; backup DB trước mọi nâng cấp. Một API process sở hữu native media, có PostgreSQL advisory lock giữ suốt vòng đời. Không chạy cluster/PM2 nhiều worker cho bản này.
2. Tạo `/etc/devone`0700, `server.json`0600 thuộc `devone`, dựa trên `infra/server/server.example.json`. Origin phải HTTPS chính xác. Sinh secret ngẫu nhiên riêng cho DB, MediaMTX, Air gateway, khóa AES256; không dùng giá trị example. Không đưa secret vào lệnh CLI, URL public hoặc Git.
3. API bootstrap input0600 chứa `username`, `password`≥12 ký tự và `totpSecret` base32≥32 ký tự được nhập vào ứng dụng authenticator. Admin không có public signup; CLI từ chối nếu đã có Admin. Không tự thay key MFA đã dùng.
4. Chạy từ checkout release đã build, chỉ trỏ `DEVONE_CONFIG` tới đường dẫn file:

```sh
npm run migrate -w @devone/api
npm run bootstrap-admin -w @devone/api -- /path/to/private-bootstrap.json
```

Sau khi đăng nhập/MFA thành công, xóa đúng input bootstrap đã tạo; giữ bản phục hồi secret mã hóa theo chính sách người vận hành. Khóa AES cần được backup cùng DB; mất khóa thì MFA Admin không giải mã được. Cookie production `__Host-`, Secure/HttpOnly/SameSite=Strict; mutations kiểm Origin và CSRF. Viewer mặc định12 giờ (đủ soak8 giờ cộng ramp-up), Admin tối đa8 giờ; hết hạn phải đăng nhập lại. Không đưa mật khẩu/token vào localStorage.

`api_watchdog.py` dừng API nếu health bị treo; `devone-media.service` có BindsTo API để native không tiếp tục phát khi mất bộ kiểm quyền. Đây là thiết kế fail-closed cần kiểm **trên Linux/systemd thật** trước mở public. Khi API bị dừng/SIGSTOP, phải chứng minh native dừng trong≤30 giây; khi DB hỏng, từ chối phiên mới và ngắt media. Restart phục hồi theo unit, tối đa5 lần/120 giây rồi cần người vận hành xử lý. Air ghi cục bộ phải tiếp tục bình thường.

## Air outbound và gateway — cửa sổ triển khai riêng

- Không thay key/trust `.local/ssh/air-poc` đang dùng từ Mini. Tạo **key riêng trên Air** cho account server `devone-air`; kiểm fingerprint host qua console nhà cung cấp trước thêm known_hosts. Không dùng `StrictHostKeyChecking=no` hoặc tự chấp nhận key đổi.
- Áp dụng SSH Match block và authorized_keys hạn chế theo `infra/server/sshd-air-tunnel.conf.example`; kiểm `sshd -t` và cấu hình hiệu lực trước reload. Chỉ hai reverse listen `127.0.0.1:18554` và `127.0.0.1:19996`; không shell/PTY/agent-forward; server loopback không mở ra Internet.
- Air gateway đọc `.local/web-gateway.json`0600 với trường `token` ngẫu nhiên base64url43+ ký tự, và playback credential hiện hữu `.local/recording-admin.json`. Token khớp `airToken` server. Gateway bind127.0.0.1:9900, chỉ `/status`, `/recording`, `/recordings`, `/playback`; không nhận URL/filename tùy ý. Tối đa8 child, body1KiB, headers16KiB, deadline hữu hạn.
- Lệnh foreground dự kiến trên Air, chưa chạy trong phiên này:

```sh
cd /Users/macbook/Developer/camera
/usr/bin/perl scripts/air_web_gateway.pl /Users/macbook/Developer/camera
/usr/bin/ssh -N -F .local/ssh/server-tunnel/config devone-server
```

Ngày03/11 đã cài3LaunchAgent gateway/tunnel/supervisor, sau đó thêm agent thứ4 cho [di chuyển không ER605](portable-deployment.md): DHCP camera/discovery có pin/proxy18556/tunnel2222. Xem [runbook Air](air-autostart.md). Runtime dùng `.local/air-autostart-runtime`, SSH config/key vẫn vị trí cũ; không chạy hai lệnh foreground trên khi các agent đang loaded. Log/runtime0700, files0600. Khi thay cùng label phải đợi tiến trình cũ thoát hết sau bootout. Đã kiểm reboot/Wi-Fi thật ở bộ3agent; bộ4agent mới kiểm proxy tự phục hồi, chưa reboot/đổi WAN-IP thật.

`scripts/render_deployment.py air` tạo **candidate mới**, không ghi đè runtime: nhận source private và playback account, render fMP4 part1s/segment1m/retention1d. `server` tạo JSON/YAML native không ghi video, nguồn reverse RTSP18554, WHEP/API loopback, ICE8189. Không chạy file Air renderer trên Air vì không cài Python; render tại Mini rồi chuyển candidate được review. Không bật candidate chỉ để thử nếu làm gián đoạn bài endurance.

Renderer Air cũ tạo source trực tiếp theo IP trong input, không tự cài discovery/proxy mới. **Không dùng candidate đó đè source roaming đang chạy**; giữ source loopback18556/TCP cùng credential/channel và kiểm theo runbook di chuyển trước khi thay runtime.

Ví dụ cấu trúc lệnh tại Mini (input riêng tư phải được cung cấp và kiểm mode trước):

```sh
python3 scripts/render_deployment.py air --source-file .local/camera-source.json --playback-account .local/recording-admin.json --output .local/mediamtx.recording.candidate.yml
python3 scripts/render_deployment.py server --backend-account .local/server-media-account.json --public-ip VPS_PUBLIC_IPV4 --output .local/server-media.candidate.json
```

Gateway bật ghi chỉ khi status supervisor mới≤30 giây, không auth latch, không disk pause, trống≥15GiB; kiểm lại sau thao tác. Không gỡ latch, xóa video hoặc tự khởi động native. Giao diện lưu desired trước và báo observed/offline; lần cài đầu chỉ quan sát, không tự bật/tắt ghi cho tới thao tác Admin đầu tiên.

## HTTPS, firewall và nhận bàn giao

Template trong `infra/server/` chỉ là candidate. Kiểm đường dẫn Node/binary thực tế, checksum MediaMTX **v1.21.3 Linux đúng kiến trúc**, build release và owner/mode trước cài unit. Không dùng binary Intel Air trên server hoặc Mini. `systemd-analyze verify`, `caddy validate`, `sshd -t`, migration/backup/restore smoke phải PASS trên server thật.

Public TCP80/443 (ACME/HTTPS), UDP/TCP8189 (WebRTC), SSH22 giới hạn IP vận hành và SSH2222 riêng cho Air roaming (rate-limit/key-only/no shell). DB5432, API3001, Next3000, WHEP8889, native9997 và reverse18554/19996 chỉ loopback. Kiểm từ máy ngoài rằng không vượt qua auth bằng native URL. Caddy tự quản TLS; kiểm renewal/cert expiry, không tạo Certbot cạnh tranh cổng80. Origin/CSP chặn script ngoài, iframe và form khác nguồn.

ICE trực tiếp có TCP fallback; chưa có TURN. Nếu nhà mạng tại nơi làm việc chặn cả UDP/TCP8189, chưa được coi live WAN đạt: cần phương án TURN/TLS, báo lại chi phí và kiểm tuyến trước mở rộng. Không hứa mọi mạng/browser đã tương thích. Chrome Mini đã kiểm; Safari/iOS/Android, WAN/recovery và Linux chưa có bằng chứng.

Quyền tải là quyền gọi download endpoint, không phải DRM: người đã được xem vẫn nhận byte video. API giới hạn mặc định5 playback/download đồng thời, đoạn1–300 giây, tối đa8 giờ Admin/12 giờ viewer. Tua theo thời gian trên Air; native gửi `Accept-Ranges: none`, không có hỗ trợ byte-range206. Kiểm Safari và playback file thật trước nghiệm thu.

## Đo 200 peers và 8 giờ

1. Đo trước1→10→50→100→200 peer tại server đã thuê. Người dùng theo dõi hình thật ở nơi làm việc; tải phát sinh từ máy đo riêng để không biến đường xuống văn phòng thành nút thắt duy nhất. Không stress Mini đang làm việc.
2. `scripts/load_webrtc.ts` nhận file0600 theo `infra/server/load-shard.example.json`. Một shard≤25 browser peers, video H264 giải mã thật; chia8 shard trên các máy đủ tài nguyên. Dùng tài khoản viewer test do Admin tạo, có thời hạn12h; không dùng Admin vào soak.
3. Chỉ khi đã được phép tạo tải, chạy mỗi shard: `npx tsx scripts/load_webrtc.ts --run /path/to/private-shard.json`. Script ghi bytesReceived/framesDecoded/packetsLost/freezeCount mỗi5s, không lưu mật khẩu/video; PASS chỉ cho shard, không tự tuyên bố đạt200. SIGINT/SIGTERM hoặc lỗi/không tiến frame bị đánh FAIL và đóng phiên.
4. Đồng bộ giờ trên máy đo, dùng cùng `startAt` ISO trong tương lai cho8 shard (ví dụ10 phút để ramp-up). Shard phải đủ peer nhận frame trước giờ này, tới muộn sẽ FAIL. Đếm native/server đúng200, kiểm request201 trả409; tập hợp8 shard có **8 giờ giao nhau** đủ200 peer, không ghép các thời đoạn không đồng thời. Không rút ngắn tiêu chí để lấy PASS.
5. Thu server CPU/RAM/swap/network, packet loss, tiến triển frame và báo lỗi/phiên; thử quota/tài khoản/kick/expiry/reconnect. Chạy playback đồng thời theo quota5 đã chọn, đo uplink Air và frame loss live. Ngân sách cổng1Gbps cần còn dư; benchmark HTTP hoặc200 reservation không thay thế được bước này.
6. Mục tiêu cảm nhận một giây vẫn `USER-ACCEPTED/VISUAL`; không ghi p95 đã đo. Endurance ghi Air24h và retention cần mốc riêng, không suy từ soakweb.

## Rollback và vận hành

Giữ release trước cùng config/private backup mã hóa. Nếu lỗi web: dừng unit API (native bị BindsTo dừng theo), dừng web/tunnel/gateway mới nếu cần; **không dừng supervisor ghi Air**, không đổi camera/router/network order. Release đầu chưa có dữ liệu người dùng production; sau khi đã có dữ liệu, không rollback DB bằng DROP hoặc restore đè khi chưa duyệt. Migration này chỉ tạo schema ban đầu, không có destructive down migration.

Theo dõi health/API, Air online/disk/latch, dung lượng DB, băng thông/quota và TLS expiry. API health503 khi bộ thu hồi phiên không làm việc; Admin có `/api/admin/service-status`. Logs không request body/header/token. Không cấu hình access log URL media nhạy cảm. Backup DB mã hóa cùng khóa MFA, kiểm phục hồi riêng; video không nằm trong backup server.
