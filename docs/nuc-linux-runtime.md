# Chuyển runtime camera sang NUC Ubuntu

**Thử Ethernet NUC06/11:** Netplan đã lưu `enp1s0` DHCP IPv4, route-metric100, optional=true; cấu hình merge giữ match MAC hiện hữu, candidate SHA256 `6436b43640ce999c9d556c2fc2709f3731ef1115274d45e00133c5d0ffe8c865`. Owner tự thực hiện sudo và xác nhận readback. Dây DHCP192.168.1.12 được ưu tiên, Wi-Fi dự phòng192.168.1.11. Sau khi owner chạy bài thử có timer tự phục hồi: trong snapshot `wlo1` DOWN, camera RTSP và cả hai socket tunnel2222 đều ESTABLISHED từ IP Ethernet; native H264/AAC ready/record=false, VPS H264/Opus ready và gateway online/observed=false/no auth latch. Bài thử kết thúc success, Wi-Fi đã UP trở lại; các kết nối vẫn dùng Ethernet. Lần chuyển đầu live chờ cổng cũ VPS nhả trước khi tự nối lại, không đo thời gian phục hồi. Owner xác nhận live có hình và tiếng bình thường; chưa xác định thời điểm xem so với cửa sổ 70 giây hoặc model/trình duyệt. Chưa reboot sau đổi Netplan, thử mất điện thật, mạng khách/Hà Nội/Lào hoặc SSH/SFTP qua jump key riêng bị thiếu.

**Snapshot trước khi sửa Ethernet06/11 (lịch sử):** owner cắm cáp NUC; `enp1s0` UP/LOWER_UP và có IPv6 nhưng chưa có IPv4 (`IPv4AddressState=off`). Default IPv4, tuyến camera và cả hai socket tunnel thực tế vẫn dùng Wi‑Fi `wlo1`/192.168.1.11. Live H264/Opus và monitor12/12 bình thường, intent/record=false. Chưa nghiệm thu chạy hoàn toàn qua Ethernet; đang chờ owner nhập sudo cho lệnh chỉ đọc cấu hình generated Ethernet để phân biệt DHCP với lỗi router, chưa đổi cấu hình mạng.

**Snapshot sau reboot trước thử Ethernet06/11 (lịch sử):** owner xác nhận live có hình và tiếng bình thường sau NUC reboot. SSH/SFTP trực tiếp strict host key tại DHCP192.168.1.11 PASS; chưa nêu model/trình duyệt người xem. Runtime ghi=false; năm unit và ba reverse listener tự phục hồi, VPS H264+Opus. Chưa thử rút điện thật, Ethernet/mạng khách hoặc jump key quản trị riêng.

**Snapshot reboot trước thử Ethernet06/11 (lịch sử):** owner tự chạy reboot, boot ID đổi; NUC DHCP đổi 192.168.1.6 → 192.168.1.11. Sau boot cả năm unit active/enabled; tunnel VPS18554/19996/19022 tự phục hồi. Qua SSH operator/VPS proxy, host key NUC khớp trust cũ; camera H264/AAC ready, record=false. VPS H264+Opus ready, gateway online/observed=false/no auth latch, intent=false/revision3. Không đo thời gian phục hồi; chờ owner xác nhận hình/tiếng sau reboot. Chưa thử mất điện thật, Ethernet/mạng khách hoặc SSH qua jump key riêng bị thiếu.

**Snapshot sau cutover trước thử Ethernet06/11 (lịch sử):** owner duyệt và tự thêm UFW TCP22 chỉ IP WAN nhà đã được duyệt; SSH operator strict PASS. Đã cài hai public key NUC sau VPS preflight policy/intent=false/token/ports PASS; owner tự chạy sudo bật hai tunnel. Cả năm unit NUC active+enabled; VPS thấy listener loopback18554/19996/19022, gateway online/observed=false/no auth latch, media ready H264+Opus, intent=false/revision3. Monitor ban đầu đang recovering. Chưa xác nhận người xem, SSH/SFTP qua jump (key jump Mini hiện thiếu), reboot/mất điện sau cài, Ethernet/mạng khách; Air vẫn ngừng dùng. IP là snapshot.

Cập nhật 06/11/2026, giờ Việt Nam. **NUC đã phục vụ live qua VPS; Ethernet được kiểm tại nhà khi Wi-Fi NUC tắt.** Owner đã tắt MacBook Air và yêu cầu ngừng dùng Air, chuyển runtime sang ASUS NUC. Mac mini vẫn là máy phát triển; VPS Singapore tiếp tục giữ website/API/database/audio adapter. Không bật lại Air để kiểm tra hoặc rollback. Ghi mới tiếp tục **OFF**.

## Snapshot06/11 trước cutover: đã cài ba dịch vụ nội bộ (lịch sử)

- Owner đã tiếp tục và cấp quyền rõ tạo/cài hai service key Ed25519 riêng NUC; không cần xin lại quyền này. Hai khóa không passphrase đã tạo trên NUC, khóa riêng không chuyển khỏi NUC. Public key live dành cho principal hiện hữu `devone-air`, chỉ reverse18554/19996; maintenance dành cho `camera-maint-relay`, chỉ19022→NUC22. Không thêm listener public, principal hoặc quyền shell.
- NUC đã boot lại qua đêm trước khi cài runtime; DHCP nay192.168.1.6, camera192.168.1.9. SSH host key NUC khớp khóa đã xác minh qua console; dùng `HostKeyAlias=192.168.1.22` trong lệnh riêng, không sửa global known_hosts/mạng Mac. Camera discovery/pin đúng identity, không đổi IP/DHCP camera.
- Owner tự chạy launcher và nhập sudo. Bộ cài root đã provision user/group `devone-edge`, source/binary root-owned, config/key600, thư mục private700, năm unit và hai profile SSH. Không cài dependency hoặc đổi OS/firmware/SSH/firewall.
- Đã đọc báo cáo cài đặt và kiểm systemd/kernel socket trực tiếp: `devone-edge-source`, `devone-edge-recording`, `devone-edge-gateway` đều active/running+enabled,0restart ở snapshot. Nguồn ready H264/MPEG-4Audio(AAC), gateway online, native record=false,0video. RTSP8554,WebRTC8889,API9997,playback9996,gateway9900,proxy18556 chỉ127.0.0.1.
- Hai unit `devone-edge-live-tunnel` và `devone-edge-maintenance-relay` đã cài nhưng disabled/inactive; chưa thử xác thực trên VPS. Khóa riêng bản runtime600 thuộc user dịch vụ; bản staging private vẫn giữ trên NUC để đối chiếu, không đưa vào Git.
- SSH22 tới VPS hiện timeout từ cả Mac/NUC,2222 reachable. Chưa xác định nguyên nhân hoặc sửa firewall. Đang chờ owner mở Recovery Console và đăng nhập root hiện có để kiểm fresh intent/token/policy/port, rồi cài đúng hai public key được duyệt, giữ nguyên các key cũ. Bộ cài key đã chuẩn bị có backup/readback và từ chối policy/token/port không phù hợp; chưa chạy trên VPS.
- Chưa có bằng chứng live website từ NUC, quản trị qua relay, tự phục hồi/reboot sau cài unit, Ethernet hoặc WAN/subnet mới. Ghi vẫn OFF; video cũ trên Air chưa chuyển. Mốc boot qua đêm không thay kiểm nghiệm tự khởi động runtime vừa cài.

## Snapshot đã kiểm05/11 trước khi cài

- NUC `camera-edge`, Ubuntu Server26.04.1 LTS, kernel7.0.0-42-generic, Linuxamd64, Python3.14.4, systemd259.5. Perl core/curl/iproute2/OpenSSH có sẵn. Root còn khoảng436GiB trống; đồng hồ NTP đồng bộ, timezone hiện vẫn UTC.
- SSH/SFTP bằng khóa Ed25519 riêng của Mac đã được owner kiểm, dùng public-key only; Codex sau đó SSH trực tiếp thành công. Host fingerprint đã đối chiếu qua console và `known_hosts`; không đổi trust. `sudo -n` chưa có quyền; thao tác root trên NUC cần owner tự nhập mật khẩu.
- Owner xác nhận camera → PoE switch → LAN router đã nối đầy đủ, NUC dùng Wi-Fi cùng LAN. NUC đang có DHCP192.168.1.22/24 trên `wlo1`; Ethernet chưa cắm. Đây là snapshot, không gán IP tĩnh từ tài liệu.
- Linux discovery thật từ NUC đã tìm camera ở **192.168.1.23** và xác minh đúng HTTPS public-key pin bằng identity private đã có. Không gửi credential trong SADP/HEAD, không PUT cấu hình camera, không chạy RTSP hoặc ghi video trong bài discovery này.
- MediaMTX Linuxv1.21.3 đã tải/kiểm checksum và chạy smoke trên NUC trong workspace validation riêng: API/RTSP/player loopback PASS, supervisor xác nhận đúng hash binary. Smoke dùng synthetic path, không có camera/media decode hoặc benchmark độ trễ.
- Bài native camera thật có thời hạn sau đó đã PASS: source ready, tracks `H264`/`MPEG-4 Audio` (AAC),119.176byte nhận ở snapshot, supervisor running/ok, không auth latch, record=false/retention1d và0tệp video. Native/proxy của bài thử đã dừng; `ss` xác nhận không còn listener media, status native PID=null/proxy stopped. Đây không phải WebRTC browser decode, endurance hoặc đo latency.
- NUC kết nối được outbound TCP2222 tới VPS. Host ED25519 của ingress2222 khớp byte-for-byte với trust operator hiện hữu; không chấp nhận key mới từ keyscan. Chưa xác thực/cài khóa tunnel NUC hoặc kiểm policy server bằng operator.
- Năm unit candidate đã qua `systemd-analyze verify` trên NUC. Có hai warning `CPUAccounting` từ unit XFS sẵn của Ubuntu; không sửa các unit hệ điều hành này. Candidate chưa cài/enable/start trong systemd.

## Các thay đổi Linux

- [CLI](../scripts/poc.py) nhận `linux_amd64`, giữ MediaMTXv1.21.3 và các target POC macOS hiện có.
- [Supervisor](../scripts/air_recording_supervisor.pl) chọn pin binary theo OS/CPU, vẫn từ chối target chưa xác minh. Giữ managed startup buộc record=false, auth latch401/403, reserve15GiB, retention1d và private file guards. Tên module/entry point cũ được giữ để tránh thay contract.
- [Proxy](../scripts/camera_roaming_proxy.pl) đọc `ip -j -4 address` trên Linux, chỉ chọn interface vật lý có carrier/IPv4/multicast; không dùng `ifconfig -l`, hardcode `eth0` hoặc chọn Docker/VPN làm LAN camera. UUID probe lấy từ OS random, không cần cài `uuidgen`.
- Profile quản trị legacy có `IgnoreUnknown UseKeychain` để OpenSSH Linux đọc được tùy chọn macOS này; các ràng buộc key/host/forward giữ nguyên. Không áp dụng lại profile hoặc can thiệp Air.
- [Bộ chuẩn bị NUC](../scripts/prepare_nuc_runtime.py) tạo bundle private có manifest/hash, source, năm unit và hai profile tunnel; không tạo credential, cài/start service hoặc đổi VPS. Bundle không có camera password/private key/gateway token.

Archive Linuxamd64 có SHA256 `0a2ea7eba96023631efa1bea7804823a9145b043b6646a8a05798d4ac24ed635`; binary ELF amd64 có SHA256 `bfa372a169751bbf6da2ebddcbcd2f7d3ab3dca3cc553022162eda36fe03e73d`. Đã đối chiếu [checksum publisher](https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/checksums.sha256) và [release chính thức](https://github.com/bluenviron/mediamtx/releases/tag/v1.21.3), không chạy binary Linux trên Mac.

## Bản dịch vụ đã chuẩn bị

Workspace đích: `/var/lib/devone-edge/camera`. User/group dịch vụ: `devone-edge`, không dùng tài khoản quản trị `cameraadmin` để chạy runtime.

| Unit | Vai trò | Khởi động lại |
|---|---|---|
| `devone-edge-source` | Discovery/pin và RTSP proxy127.0.0.1:18556 | Khi thoát, có giới hạn tần suất |
| `devone-edge-recording` | Managed supervisor/MediaMTX, bắt đầu record=false | Chỉ khi lỗi; exit0 do auth latch giữ dừng |
| `devone-edge-gateway` | Gateway có token, chỉ127.0.0.1:9900 | Khi thoát, có giới hạn tần suất |
| `devone-edge-live-tunnel` | Hai reverse18554/19996 qua VPS2222 | Khi mất kết nối; không hết restart budget do mạng mất lâu |
| `devone-edge-maintenance-relay` | Reverse19022 → SSH22 NUC | Độc lập với camera/live |

Các unit chạy sau boot tại `multi-user.target`, không cần GUI/login. `KillMode=control-group` dọn child; user không có capability, có `NoNewPrivileges`, filesystem read-only ngoài `.local`, chặn ghi vào tools/SSH trust trong service và cho AF_NETLINK để đọc interface. Cấu hình dựa trên tài liệu [systemd.service](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml) và [systemd.exec](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml); các unit và sandbox đã chạy trên NUC thật, reboot trước thay đổi Netplan đã kiểm. Chưa kiểm reboot sau thay đổi Netplan.

Tạo candidate tại Mac mini:

```sh
python3 scripts/prepare_nuc_runtime.py \
  --server-ip 168.144.137.69 \
  --output .local/nuc-migration/bundle-NEW
```

Không ghi đè bundle cũ. Mọi artifact0600/dir0700; manifest ghi quyền đích riêng: source root:devone-edge0640, unit root:root0644, SSH profile devone-edge0600. Cần provisioning đúng owner/dir trước khi start; không copy rồi chạy bằng root.

## Kế hoạch05/11 trước cutover (quyền khóa và cài local đã hoàn thành06/11)

1. Đọc trạng thái VPS bằng khóa operator recovery hiện có và host trust cũ: intent phải còn false, chính sách ingress2222, listener18554/19996/19022 và gateway token. Lần đọc đầu trong phiên này bị `Permission denied (publickey)`; đã yêu cầu owner nạp **khóa hiện có** vào SSH agent. Không mở password SSH, đổi trust/key/firewall để chữa.
2. Chuẩn bị và review cấu hình private NUC với camera identity đã xác minh; source RTSP chỉ qua proxy loopback, không có IP gợi ý trên đĩa. Giữ credential trong file0600, không đưa password vào argv/log/Git.
3. Xin quyền cụ thể trước khi tạo/cài **hai khóa dịch vụ mới riêng NUC**: live và maintenance. Khóa quản trị Mac→NUC đã có không được dùng làm khóa tunnel; không chép private key Air/VPS operator lên NUC. VPS vẫn dùng các principal/forward quyền hẹp hiện có, không thêm public listener hoặc quyền shell.
4. Provision user dịch vụ/source/binary/private config/unit trên NUC sau khi bundle và quyền đã chốt. Owner tự nhập mật khẩu cho thao tác root. Không cài thêm Docker/GUI/Node hoặc nâng firmware/OS ngoài phạm vi duyệt.
5. Chỉ start tunnel sau khi xác nhận các reverse port cũ đã nhả. Dùng `ExitOnForwardFailure=yes`; không cho Air và NUC tranh port hoặc che lỗi forward. Giữ host trust và cấu hình website/API/DB hiện hữu.
6. Kiểm thật RTSP101 H264/AAC, managed startup record=false, đúng một native và listener loopback; sau đó HTTPS/live H264+Opus/Admin/monitor qua VPS. Camera401/403 phải giữ auth latch và dừng, không thử credential lặp. Video cũ trên Air chưa chuyển sang NUC; không coi playback cũ đã có trên máy mới.
7. Khi service/gate cơ bản đã đạt, chốt cửa sổ owner thử reboot NUC/headless, mất/khôi phục mạng và nguồn trên NUC. Ethernet DHCP, WAN/subnet khác và Hà Nội/Lào cần bằng chứng riêng. Không thử bằng rút nguồn router/camera/Air, không lặp tải200/endurance/optical đã miễn.

Nếu triển khai lỗi: dừng đúng unit/tunnel NUC sở hữu, chờ PID/port nhả, giữ config/private backup/latch và record=false để sửa. Không xóa video, reset camera/OS hoặc bật lại Air tự động. Chưa có bản production Linux cũ để gọi là đã rollback thành công.

## Kiểm tra trước khi hợp nhất vào main — 06/11/2026

- Mac mini: `make check` PASS 70 bài, 1 SKIP vì GnuPG không có trong PATH; `npm run check` PASS, gồm format, typecheck, 13 bài API và build web/API. Bài Python thử đồng thời ban đầu timeout; khi chạy lại riêng cả gate đã PASS, không đổi timeout hoặc bỏ kiểm tra.
- NUC Linux thật: `tests/test_air_recording_supervisor.t` 18 subtest, `tests/test_camera_roaming_proxy.t` 36 bài, `tests/test_air_web_gateway.t` 30 bài và `tests/test_linux_runtime.t` 3 subtest đều PASS. Hash source/test NUC khớp bản local được kiểm. Bộ supervisor không dùng kết quả chạy trên Mac mini ARM làm bằng chứng target Intel/Linux.
- Không chạy lại browser test hoặc pipeline camera/native trên Mini cho đợt công bố; bằng chứng live thật, reboot trước đổi Netplan và thử Ethernet ghi ở trên. Chưa nghiệm thu reboot sau đổi Netplan, mất điện thật, mạng Hà Nội/Lào hoặc SSH/SFTP qua jump key riêng.
- Mã chuẩn bị bundle chỉ tạo artifact, không tự cài hoặc chứa credentials. Root installer và cấu hình riêng đang lưu trong `.local` trên máy vận hành, không nằm trong source; clone mới không thể tự dựng lại NUC nếu thiếu provisioning và credentials. Không push key, video, config riêng hay bản sao lưu.

## Bằng chứng phần mềm

- TDD: bài mới ban đầu fail đúng ở target Linux chưa hỗ trợ/hàm parser/pin chưa có. Gate cuối `make check` trên Mac:70bài,69PASS/1SKIP do GnuPG chưa có trong PATH; compileall/CLI help PASS.
- Trên NUC thật: compileall/CLI help PASS; Python70/70PASS gồm GPG integration. Supervisor Perl syntax +18subtest PASS; proxy syntax +36bài PASS; gateway syntax +30bài PASS. Bộ Linux mới3subtest/29assertions PASS.
- Sáu bài chuẩn bị unit/tunnel/private bundle nằm trong gate70bài, đã PASS trên Mac và NUC; profile được OpenSSH thật parse, unit được systemd259 verify. Bằng chứng chạy thật, tunnel và reboot trước thay đổi Netplan được ghi ở đầu runbook.

Các test và candidate này không thay bằng chứng vận hành. Xem [hướng dẫn OS/SSH](mini-pc-setup.md), [portable discovery](portable-deployment.md), [checkpoint](v1-implementation.md).


## Tạm dừng theo owner — tối05/11/2026

- Owner yêu cầu tạm dừng, sáng hôm sau tiếp tục. Câu trả lời này **không cấp quyền** tạo/cài hai khóa dịch vụ NUC mới; chưa tạo các khóa đó. Không triển khai thêm khi đang tạm dừng.
- Sau khi owner nạp recovery key, SSH operator VPS đã PASS: intent=false/revision3,18554/19996/19022 không có listener cũ, cả ba principal ingress2222 qua validator; API/web/media/monitor/ingress vẫn hoạt động, audio adapter đang chờ nguồn. Nguồn live chưa được NUC phục hồi. Đã lấy gateway token hiện có vào candidate private0600, không hiện giá trị.
- Bài camera NUC đã dừng sạch; chưa có user/unit/runtime production NUC, chưa có tunnel/key dịch vụ mới hoặc thao tác root NUC. Không có lệnh cài đặt đang chờ chạy. Air vẫn ngừng dùng theo owner.
- Khi owner yêu cầu tiếp tục: đọc runbook/checkpoint và trạng thái thực; agent keys1h có thể hết hạn. Chốt quyền hai service key trước khi tạo, rồi chuẩn bị/apply root installer và cutover. Không tự bật ghi, bật Air, push source hoặc coi kiểm thử đã là nghiệm thu production.
