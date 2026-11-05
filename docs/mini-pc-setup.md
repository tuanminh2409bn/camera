# Chuẩn bị mini PC thay MacBook Air

Ngày 05/11/2026, giờ Việt Nam. **Trạng thái: đã tạo USB và quan sát Etcher báo thành công; chưa xác nhận boot/cài Ubuntu trên NUC, chưa port runtime hoặc chuyển production.** Source ứng dụng đối chiếu: `63fadbe`, nhánh `tuanminh/secure-live-v1`.

## Điểm tiếp tục cho ChatGPT web

**Bắt đầu từ boot USB trên NUC, không cần tạo lại USB.** Owner đã yêu cầu cập nhật hướng dẫn này lên GitHub để ChatGPT web hướng dẫn từng màn hình. Dùng đúng nhánh `tuanminh/secure-live-v1`; nhánh mặc định `main` vẫn là mốc POC cũ.

- ISO đã tải từ Ubuntu: `ubuntu-26.04.1-live-server-amd64.iso`. SHA256 đã đối chiếu với `SHA256SUMS` chính thức: `cc8a95cde20f6ced61a322420de00f10cc3c90ced545daa46cb9c1a117f1d927`. Chưa xác minh chữ ký GPG.
- USB đích là **Kingston DataTraveler 3.0, 61,9 GB**, trước đó mang tên `Install macOS Tahoe`. Owner đã đồng ý xóa bộ cài Tahoe để chuyển sang Linux. USB này khác ổ USB/APFS `Developer` chứa project và dữ liệu riêng tư.
- Etcher2.1.9 bản macOS arm64 đã được cài từ release chính thức. Sau khi owner ghi USB, Codex đọc trực tiếp cửa sổ: **`Flash Completed!` / `1 Successful target`**, effective speed12,2MB/s. Màn hình cuối không hiện riêng chi tiết Validation; không ghi thành đã thực hiện thêm bài readback độc lập.
- `diskutil` cũng cho thấy USB đã có bố cục mới khoảng2,9GB + EFI, không còn volume Tahoe. Disk identifier là snapshot; không dùng lại số disk để ghi/xóa ở phiên sau.
- Chưa có ảnh hoặc kết quả boot/cài OS trên NUC. Bước kế tiếp: cắm USB/màn hình/bàn phím vào NUC → F10 lúc POST → chọn USB UEFI → Try or Install Ubuntu Server.

Đoạn owner có thể dán vào ChatGPT web cùng liên kết tài liệu này:

```text
Hãy hướng dẫn tôi từng màn hình cài Ubuntu trên ASUS NUC 14 Essential Intel N97,
RAM 8 GB, SSD NVMe 512 GB. Đọc tài liệu tại liên kết tôi gửi, nhánh
tuanminh/secure-live-v1 của repo tuanminh2409bn/camera.
Tôi đã có USB Ubuntu Server 26.04.1 LTS amd64; Etcher báo Flash Completed!
và 1 Successful target. Tôi chuẩn bị boot USB trên NUC, chưa xác nhận đã cài OS.
Máy chủ yếu chạy không màn hình; tôi chọn tự chạy sau mất điện, không mã hóa
toàn ổ. Thử ở nhà bằng Wi-Fi nếu Ubuntu nhận card; khi mang tới Hà Nội/Lào
sẽ dùng Ethernet DHCP cùng LAN camera. Hostname đề xuất camera-edge,
tài khoản quản trị đề xuất cameraadmin; mật khẩu do tôi tự nhập và lưu riêng.
Hãy theo màn hình thực tế tôi cung cấp, hướng dẫn từng bước và kiểm đúng SSD
512 GB trước xác nhận xóa. Không yêu cầu tôi gửi mật khẩu/private key.
Mục tiêu lượt này là cài OS, kiểm mạng và chuẩn bị SSH/SFTP. Runtime camera
Linux chưa được port; Air/VPS đang phục vụ, ghi mới phải tiếp tục tắt.
Nếu không đọc được liên kết GitHub, nói rõ để tôi cung cấp nội dung tài liệu.
```

## 1. Thiết bị và lựa chọn đã chốt

- Hóa đơn owner cung cấp: ASUS `RNUC14MNK9700000` (NUC 14 Essential, Intel N97), RAM Kingston 8 GB DDR5, SSD GIGABYTE 512 GB NVMe. Đây là thông tin trên hóa đơn; cần kiểm BIOS/OS để xác nhận linh kiện thực lắp.
- Owner chọn chủ yếu chạy không màn hình; đã có USB từ 8 GB, màn hình và bàn phím để cài.
- Owner chọn tự chạy sau mất điện, **không mã hóa toàn ổ**. Người có quyền truy cập vật lý vào SSD có thể đọc dữ liệu; quyền file và SSH không thay thế mã hóa ổ đĩa.
- Chọn **Ubuntu Server 26.04.1 LTS, Intel/AMD 64-bit (`amd64`)**, không GUI. `amd64` dùng cho Intel N97; không tải ISO ARM theo kiến trúc Mac mini dùng để tạo USB.

ASUS xác nhận dòng này đã kiểm Ubuntu 24.04 nhưng cũng ghi nhận lỗi LAN với Realtek driver 9.015.00 trên một số bản 24.04 cũ và khuyên dùng bản Ubuntu/driver mới. Vì vậy lựa chọn ban đầu 24.04 được điều chỉnh sang LTS 26.04.1 hiện hành. Đây là lựa chọn kỹ thuật để có kernel mới hơn, **không phải bằng chứng LAN trên máy này đã đạt**. Không dùng bản 26.10 chỉ vì số phiên bản lớn hơn.

Mac mini vẫn là máy phát triển. Mini PC mới thay vai trò runtime tại camera; website/API/PostgreSQL/audio adapter vẫn ở VPS. Ubuntu Server không có màn hình desktop để điều khiển như Screen Sharing trên Air; quản trị ban đầu bằng SSH/SFTP. Nếu sau này cần UI nhập bảng/numpad tại máy, thiết kế giao diện đó riêng; bảng kết quả hiện chưa triển khai.

### Wi-Fi tại nhà và Ethernet khi di chuyển

Owner chọn thử NUC tại nhà bằng Wi-Fi; mẫu NUC này được ASUS công bố có Wi-Fi6E, nhưng card/driver thực tế trên Ubuntu vẫn cần kiểm. Nếu installer nhận interface Wi-Fi thì chọn mạng nhà và nhập mật khẩu trực tiếp trên NUC. Nếu chưa thấy interface hoặc không kết nối được, ghi nhận màn hình/lỗi và kiểm driver; có thể dùng Ethernet tạm để cài/cập nhật, không cài script driver từ nguồn lạ. Thử OS chỉ cần Internet; thử camera cần camera và NUC cùng LAN, không phải Wi-Fi khách cách ly.

Khi tới Hà Nội/Lào, dùng Ethernet DHCP: Camera → PoE switch → LAN router; NUC → một cổng LAN thường cùng mạng. LAN thông thường không cần tên/mật khẩu Wi-Fi. Router phải cấp DHCP, cho hai thiết bị truy cập/discovery multicast và cho NUC kết nối ra VPS TCP2222. Không gán IP nhà làm địa chỉ cố định tại khách hàng. Dự kiến ưu tiên Ethernet trên **NUC** khi có dây; đây chưa là cấu hình đã áp dụng/đã thử. Giữ nguyên thứ tự mạng Mac mini. Khả năng cắm dây rồi tự phục hồi dịch vụ chỉ được nghiệm thu sau khi hoàn thành bản Linux và thử mạng thật.

## 2. Tạo USB trên Mac mini

1. Tải `ubuntu-26.04.1-live-server-amd64.iso` từ [Ubuntu releases chính thức](https://releases.ubuntu.com/26.04.1/). Tại đây cũng có `SHA256SUMS` và chữ ký. Tên phải có `live-server-amd64`.
2. Đối chiếu SHA256 trước khi flash. Nếu file nằm trong Downloads, chạy trên **Mac mini**:

   ```sh
   shasum -a 256 ~/Downloads/ubuntu-26.04.1-live-server-amd64.iso
   ```

   So với dòng có đúng tên ISO trong `SHA256SUMS` lấy qua HTTPS tại cùng trang. Đây là kiểm checksum tải xuống; không gọi là đã xác minh chữ ký GPG nếu chưa làm bước đó.
3. Tải [balenaEtcher chính thức](https://etcher.balena.io/), bản **macOS arm64** cho Mac mini Apple Silicon. App tạo USB là ARM, còn ISO đích vẫn là amd64.
4. Trong Etcher: **Flash from file → chọn ISO → Select target → chọn USB trống → Flash**; chờ cả ghi và validate hoàn tất.
5. Flash xóa USB được chọn. Kiểm tên/dung lượng thật; tuyệt đối không chọn ổ `Developer`, ổ backup hoặc SSD ngoài khác. Không dùng lệnh `dd` với disk number đoán từ ví dụ.
6. Nếu macOS báo không đọc được USB sau flash, chọn **Ignore/Eject**, không Initialize/Erase. Rút USB an toàn.

## 3. Cài trên mini PC mới

Giữ Air/camera/VPS đang chạy. Cắm mini PC bằng Ethernet tới LAN router đang nối switch camera, dùng một cổng LAN thông thường còn trống. Không cắm máy vào cổng PoE thụ động, không rút uplink camera và không đổi DHCP/IP camera. Chỉ kết nối mini PC mới với màn hình/bàn phím/USB cài; tháo các ổ dữ liệu ngoài khỏi mini PC để tránh chọn nhầm đĩa.

1. Bật máy, bấm **F2** vào BIOS. Xác nhận CPU N97, RAM khoảng 8 GB, SSD khoảng 512 GB. Nếu SSD/RAM không được nhận thì xử lý phần cứng trước khi cài.
2. Dùng UEFI; giữ Secure Boot ở cấu hình mặc định nếu installer chạy được. Không cập nhật BIOS, ép RAM hoặc đổi firmware để chuẩn bị thông thường.
3. Nếu BIOS có **After Power Failure / AC Power Recovery**, chọn **Power On** theo nhu cầu owner. ASUS mô tả menu `Power → Secondary Power Settings`; nhãn trên BIOS thực có thể khác. Đây chỉ cấu hình, cần kiểm phục hồi thật sau khi máy mới đã được chuẩn bị.
4. Lưu BIOS, khởi động lại và bấm **F10 khi POST** để mở boot menu; chọn mục UEFI của USB. F10 khi đang trong BIOS có thể là Save & Exit, khác với F10 lúc POST.
5. Chọn **Try or Install Ubuntu Server**. Installer điều khiển bằng phím mũi tên, Tab, Space và Enter.

Các lựa chọn đề xuất trong installer:

| Màn hình | Giá trị |
|---|---|
| Language / keyboard | English / English (US), để dễ đối chiếu lỗi và lệnh |
| Installer update | Có thể cập nhật installer từ nguồn Ubuntu khi mạng đã hoạt động |
| Installation type | Ubuntu Server thông thường; không chọn minimized cho lần đầu |
| Network | Ở nhà có thể dùng Wi-Fi nếu installer nhận card; nhập SSID/mật khẩu trực tiếp. Ethernet dùng IPv4 DHCP; để nguyên địa chỉ router cấp |
| Proxy | Trống nếu mạng không yêu cầu |
| Mirror | Mirror Ubuntu do installer chọn, phải kiểm truy cập thành công |
| Guided storage | Use an entire disk, chọn đúng SSD GIGABYTE 512 GB |
| LVM | Bỏ chọn cho bố cục đơn giản một SSD; xem lại root ext4 dùng phần lớn dung lượng sau EFI/boot |
| Encryption | Không mã hóa toàn ổ theo lựa chọn owner |
| Your name | Tên tùy chọn |
| Server name | `camera-edge` |
| Username | `cameraadmin` — tài khoản quản trị, runtime sẽ dùng user quyền hẹp riêng |
| Password | Owner tự đặt và lưu trong trình quản lý mật khẩu; không gửi vào chat |
| Ubuntu Pro | Skip for now, không đăng ký gói trả phí trong bước cài |
| SSH | Chọn Install OpenSSH server; không import hàng loạt key GitHub/Launchpad |
| SSH password | Chỉ tạm dùng trên LAN tin cậy để bootstrap nếu chưa có public key; sẽ chuyển sang key trước khi vận hành |
| Featured server snaps | Không chọn thêm |

**Xác nhận storage sẽ xóa dữ liệu trên đúng SSD đã chọn.** Chỉ tiếp tục khi đã nhận diện đúng ổ mới và không có dữ liệu cần giữ. Nếu màn hình chia ổ khác bảng trên, đối chiếu trước khi xác nhận; không chọn ổ dựa duy nhất vào tên `/dev/sda` hoặc `/dev/nvme0n1`.

Nếu installer không thấy Ethernet hoặc không nhận DHCP: kiểm dây/cổng LAN và thông báo thực tế, dừng trước cutover. Không cài driver từ script/forum, tắt Secure Boot, đổi router hay đổi OS liên tục để đoán nguyên nhân. Cảnh báo Realtek của ASUS là lý do phải kiểm LAN thật, không phải chẩn đoán mọi lỗi mạng.

Đợi cài và cập nhật hoàn tất; Reboot Now; rút USB khi được yêu cầu. Đăng nhập bằng `cameraadmin`. Màn hình dòng lệnh là bình thường với Ubuntu Server.

## 4. Chuẩn bị OS sau cài

Các lệnh dưới đây chạy **trên mini PC mới**, tại màn hình/bàn phím của máy. Không chạy chúng trên Mac mini, Air hay VPS:

```sh
sudo apt update
sudo apt upgrade
sudo apt install ca-certificates curl perl python3 openssh-server
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

Đọc kết quả từng lệnh; nếu lỗi thì giữ thông báo để xử lý, không tiếp tục bằng cách bỏ qua lỗi. Đây chỉ gói nền OS; chưa cài MediaMTX/FFprobe hoặc dịch vụ dự án. Máy mới chưa phục vụ camera nên có thể khởi động lại để nhận kernel cập nhật, bằng `sudo reboot` do owner thao tác trên chính máy này.

Sau khi đăng nhập lại, lấy dữ liệu chỉ đọc:

```sh
cat /etc/os-release
uname -m
uname -r
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
df -h /
ip -br address
ip route
timedatectl status
systemctl is-active ssh.service ssh.socket
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Kết quả mong muốn: Ubuntu 26.04.x, `x86_64`, RAM/SSD khớp máy, root có dung lượng phù hợp, Ethernet có IPv4/default route, đồng hồ đồng bộ. Ubuntu có thể kích hoạt SSH qua socket; không coi riêng trạng thái service chưa active là lỗi nếu socket đang nghe đúng. Dòng `ssh-keygen` chỉ đọc fingerprint public host key, không đọc private key.

Gửi lại IP LAN, phiên bản OS và fingerprint public này để thiết lập quản trị. Không gửi password, private key, raw config camera hoặc môi trường. Không forward SSH trên router và không dùng ngay profile `camera-air`: máy mới phải có host identity/profile riêng.

Trước vận hành: cấu hình key Ed25519 từ Mini, đối chiếu host fingerprint qua màn hình vật lý, kiểm SSH/SFTP mới thành công, sau đó tắt password/kbd-interactive/root SSH; validate cấu hình trước reload và kiểm một kết nối mới trong khi console vẫn còn. Firewall chỉ cho đường quản trị cần thiết sau khi biết interface/subnet thật; không mở rộng key/firewall của Air/VPS để tiện bootstrap.

## 5. Công việc chuyển runtime sang Linux

**Không copy nguyên thư mục runtime Air rồi chạy.** Các điểm sau cần triển khai và kiểm trên mini PC trước cutover:

| Hạng mục hiện tại | Công việc Linux |
|---|---|
| `poc.py` chỉ có archive/detection Darwin | Hỗ trợ Linux amd64, MediaMTX vẫn ghim v1.21.3, xác minh checksum/binary Linux từ nguồn chính thức |
| Supervisor ghim hash MediaMTX macOS Intel | Chọn hash đúng nền tảng, vẫn từ chối binary sai; kiểm process group, disk probe và private file guards trên Linux |
| Discovery `/sbin/ifconfig -l`, interface `enN`, `uuidgen` | Adapter Linux theo interface IPv4/netmask/UP thực tế; không chỉ cài net-tools hoặc hardcode `eth0` |
| LaunchAgent/caffeinate/Aqua login | Các systemd unit chạy bằng user quyền hẹp sau boot, không phụ thuộc GUI/login; cleanup/timeout/restart có hạn |
| `SuccessfulExit=false` + auth latch | Unit phải giữ fail-stop khi camera 401/403 và không retry latch vô hạn |
| Đường `/Users/macbook/...` | Workspace/runtime Linux và owner/mode mới; giữ dirs0700/files0600 |
| Hai SSH client live/bảo trì | Key riêng cho máy mới, trust VPS đã xác minh, principal/forward quyền hẹp; không phát tán key operator VPS vào mini PC |
| Screen Sharing macOS | SSH/SFTP cho scope headless; GUI remote chỉ bổ sung nếu có nhu cầu rõ ràng |
| Gateway/playback/recording | Giữ HTTP contract hiện có, streaming/backpressure, auth/disk guards; không đổi schema/API theo việc đổi OS |

Thiết kế dịch vụ tương ứng: camera source proxy, recording supervisor, web gateway, outbound live tunnel, maintenance relay. Các listener media/gateway vẫn loopback; discovery multicast chỉ trên LAN phù hợp. Chi tiết unit/đường dẫn/hash là candidate cần review, chưa có artifact Linux sẵn trong repo ở mốc này.

Giữ video H264/AAC trên edge, FFmpeg AAC→Opus tiếp tục ở VPS. Không chuyển website/PostgreSQL sang mini PC hoặc tự cài thêm Docker/GUI/Node chỉ để mô phỏng Air. Retention vẫn1d/reserve15GiB, managed startup và config trên đĩa đều record=false; không suy SSD lớn hơn thành được tăng retention hoặc bật ghi.

## 6. Chuyển giao và nghiệm thu

1. Đọc trạng thái thật của Air/VPS, intent/revision/latch/source và lưu baseline allowlist trước thao tác production. Trạng thái ghi tắt trong tài liệu cũ chỉ là snapshot, cần đối chiếu lại.
2. Kiểm Python/Perl fixtures và native Linux config/hash trên máy mới, chưa nối camera hoặc chiếm các reverse port production. Test trên Mini không chứng minh Linux đã đạt.
3. Kiểm LAN, discovery/pin đúng-sai, proxy RTSP, live H264+Opus và playback H264+AAC thật trong cửa sổ chuyển giao; tránh tạo client xác thực camera lặp không kiểm soát. Không tự bật ghi để có clip thử.
4. Air đang giữ reverse ports VPS18554/19996/19022. Hai máy không thể cùng giữ các listener này. Chuẩn bị rollback rồi chỉ dừng đúng các tunnel cũ và chờ nhả port trước khi máy mới kết nối. Không tự mở thêm port hoặc dùng `ExitOnForwardFailure=no` để che xung đột.
5. Ghi cũ vẫn ở SSD Air nếu còn dữ liệu. Chốt cách giữ/truy cập trước cutover; không tự sao chép/xóa video hoặc coi bản ghi cũ đã chuyển sang SSD mới.
6. Kiểm trên website thật: auth/RBAC, live hình/tiếng, playback nếu có bản ghi hợp lệ, Admin/monitor và ghi vẫn tắt. Các field tên Air có thể tạm giữ để tương thích, không tự đổi public contract.
7. Owner thử reboot mini PC mới, bỏ màn hình/bàn phím, kiểm dịch vụ tự chạy và SSH mới. Sau đó thử mất/khôi phục mạng và điện trên **máy mới** theo cửa sổ riêng; ghi đúng bằng chứng, không thử bằng rút điện Air/router đang phục vụ.
8. Chỉ tháo Air khỏi vận hành khi các gate thật đạt. Nếu lỗi, dừng tunnel mới, đợi nhả port, khôi phục tunnel Air theo baseline và kiểm lại live/ghi tắt; không factory reset hay restore đè DB/camera.

Không lặp các bài tải200/8h, optical hoặc phần endurance đã miễn trên Air. Bài reboot/mạng/điện của thiết bị mới là nghiệm thu nền tảng mới, không phải yêu cầu làm lại các bài đã miễn.

## 7. Nguồn và bằng chứng của bước chuẩn bị

- [ASUS đúng SKU N97](https://sg.store.asus.com/nuc-14-essential-intel-core-n97-barebone.html), [ASUS Linux/Realtek](https://rog.asus.com/us/support/faq/1055246/).
- [Ubuntu Server tải chính thức](https://ubuntu.com/download/server), [release26.04.1/ISO/checksum](https://releases.ubuntu.com/26.04.1/), [vòng đời LTS](https://ubuntu.com/about/release-cycle).
- [Ubuntu tạo USB trên macOS](https://ubuntu.com/desktop/docs/en/latest/how-to/create-a-bootable-usb-stick/), [Etcher](https://etcher.balena.io/).
- [Installer từng màn hình](https://canonical-subiquity.readthedocs-hosted.com/en/latest/tutorial/screen-by-screen.html), [storage/LVM/LUKS](https://canonical-subiquity.readthedocs-hosted.com/en/latest/howto/configure-storage.html), [OpenSSH](https://ubuntu.com/server/docs/openssh-server/).
- [ASUS tự bật khi có điện](https://www.asus.com/uk/support/faq/1052162/), [manual boot menu đúng dòng NUC](https://dlcdnets.asus.com/pub/ASUS/NUC/NUC_14_Essential/E25722_NUC14MNB_NUC14MNK_TPS_EM_V2_WEB.pdf?model=NUC14MNB).
- Repo: [portable discovery](portable-deployment.md), [supervisor](../scripts/air_recording_supervisor.pl), [proxy](../scripts/camera_roaming_proxy.pl), [gateway](../scripts/air_web_gateway.pl), [R1](air-remote-management.md), [checkpoint](v1-implementation.md).

Bằng chứng hiện có gồm checksum ISO, trạng thái Etcher và bố cục USB; chưa có benchmark hoặc kiểm Linux trên NUC. Trong đợt chuẩn bị này không SSH, restart, đổi key/config hoặc bật ghi trên Air/VPS. Owner đã yêu cầu commit/push tài liệu lên GitHub để tiếp tục hướng dẫn cài OS; việc xuất bản tài liệu không phải triển khai runtime Linux.
