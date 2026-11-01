# Bàn giao DEV.ONE Secure Live sang Windows

Cập nhật 01/11/2026, giờ Việt Nam. Đây là điểm bắt đầu cho người dùng và Codex trên Windows.

**Quyết định:** dừng toàn bộ kiểm thử trên Mac mini; giữ mã nguồn POC và tests; xóa runtime, công cụ tải về, mật khẩu và báo cáo thử. Giữ Wi-Fi ưu tiên trên Mac. Tiếp tục triển khai khi người dùng bắt đầu phiên mới trên Windows.

## 1. Mục tiêu đã thống nhất

- Một camera Hikvision, H.264 thường, 1280×720, 25 fps, không âm thanh.
- Glass-to-glass p95 ≤1.000 ms; hướng tới p50 ≤500 ms. Chưa có số đo đạt mục tiêu.
- Người xem tại Lào và Việt Nam; vị trí và ISP camera tại Lào còn chưa biết.
- Camera → switch PoE → ER605/WireGuard → MediaMTX Singapore → WebRTC.
- Không có PC/NUC/Edge Agent tại nơi đặt camera trong hệ thống đích. Laptop Windows là máy phát triển/POC.
- Chỉ M0–M2 trước. Chưa xây website/API/DB production, recording hay tải 200 peers.
- [PDF gốc](DEVONE_Secure_Live_Codex_Blueprint_Ban_Moi_20261030.pdf) và [kế hoạch gốc](KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md) giữ nguyên.

## 2. Tải repo và mở Codex

Nếu chưa có Git, cài từ [Git for Windows chính thức](https://git-scm.com/downloads/win). Dùng thư mục cục bộ, ví dụ C:/Developer/camera.

~~~powershell
New-Item -ItemType Directory -Force C:/Developer
Set-Location C:/Developer
git clone https://github.com/tuanminh2409bn/camera.git
Set-Location C:/Developer/camera
git status
~~~

Nếu thư mục đã tồn tại, kiểm tra thay đổi trước; không xóa hoặc reset --hard để làm sạch.

Theo [Windows app](https://learn.chatgpt.com/docs/windows/windows-app) và [quickstart chính thức](https://learn.chatgpt.com/docs/quickstart): mở ứng dụng desktop, đăng nhập, chọn Codex và mở thư mục repo. Chọn Windows native/PowerShell cho tuyến đầu; không cần WSL chỉ để mở dự án. Khả năng cài app trên bản Windows cụ thể phải xác nhận trên laptop.

Giữ sandbox/phê duyệt bình thường theo [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox). PowerShell bên ngoài vào được LAN chưa chứng minh agent trong sandbox cũng vào được; xử lý đúng lỗi quyền và phạm vi cần thiết, không vô hiệu hóa bảo vệ toàn máy.

Repo không chứa credential, backup thiết bị, runtime binary hoặc báo cáo riêng. Phải tạo lại private config cục bộ khi cần. Ảnh tem gốc giữ trên Mac, không publish vì có định danh/khóa; thông số cần thiết đã được ghi bằng chữ.

## 3. Bản đồ dự án

| Đường dẫn | Vai trò |
|---|---|
| AGENTS.md | Phạm vi, bảo mật và trạng thái bàn giao |
| HANDOFF_WINDOWS.md | Quy trình bắt đầu và công việc Windows |
| scripts/poc.py | Python stdlib: doctor/install/configure/run/smoke/probe/analyze |
| tests/test_poc.py | 22 tests tại snapshot đã kiểm tra trên Mac |
| Makefile | Lệnh kiểm tra; Windows không mặc định có GNU Make |
| infra/mediamtx/ | JSON/YAML mẫu, chỉ có placeholder |
| infra/docker/ | Tuyến Linux/Docker riêng, chưa kiểm tra trên Windows |
| infra/vpn/ | Runbook ER605/VPS, không phải script đổi router tự động |
| docs/m0-device-inventory.md | Kiểm kê thiết bị |
| docs/m0-m2-checklist.md | Cổng CODEC/LAT/NET/HW |
| docs/latency-measurement-procedure.md | Phương pháp đo, sai số, cỡ mẫu |
| docs/implementation-status.md | Bằng chứng cũ và tình trạng sau dọn Mac |

Mã hiện chỉ là POC Python, chưa có frontend/backend production, Node dependency, database hoặc dịch vụ cloud cần chạy.

## 4. Thiết bị và đấu nối

| Thành phần | Giá trị cuối cùng quan sát |
|---|---|
| Camera | DS-2CD2643G2-LIZS2UHUN; V5.7.23 build 260320 |
| Mạng camera | Activated; DHCP; 192.168.0.101/24; gateway 192.168.0.1 |
| Tài khoản | admin; người dùng khẳng định mật khẩu đúng và đăng nhập web trên Windows thành công; mật khẩu không đi theo repo |
| HTTP/HTTPS | Bật 80/443; bắt buộc duyệt HTTPS đang tắt |
| Xác thực HTTP/RTSP | digest, MD5 theo ảnh Windows |
| RTSP | Bật, cổng 554 |
| Bộ lọc IP và MAC toàn cục | Người dùng xác nhận đều tắt |
| Phiên web | Giới hạn 50; ảnh hiện một dòng admin online |
| Switch | DS-3E1505P-EI/M; V3.0.13 build 241120; quản trị 10.20.0.254/24 |
| Router | ER605 UN/2.30; LAN 192.168.0.1; firmware/WireGuard thực tế chưa xác minh |
| Laptop | HP EliteBook Folio 9470m, Windows 10 Pro 64-bit, Intel 82579LM |

Đấu nối:
1. Camera → switch PoE 1.
2. Switch UPLINK 5 → ER605 LAN 4.
3. Windows → ER605 LAN 5.
4. Wi-Fi Windows giữ Internet cho Codex.
5. Mac không tham gia tuyến mới; có thể rút Ethernet và giữ Wi-Fi.

Dò lại IP khi lease/mạng thay đổi; .101 chưa phải reservation cố định. Không đổi WAN/router để thử đoán. Switch chuyển mạch được không chứng minh đã vào được địa chỉ quản trị khác subnet.

NIC Windows từng lỗi Code 10. Disable/Enable riêng Intel 82579LM đã đưa về “working properly” và tìm thấy camera. Không có driver mới nào được Codex cài. Nếu tái diễn, kiểm tra Device Manager/driver OEM đúng model; không mặc định cổng ER605 hỏng.

## 5. Bằng chứng và khoảng trống

**Đã có:**
- Source snapshot 6445724 từng đạt make check: 22 tests, compileall, CLI help trên macOS arm64.
- MediaMTX native v1.21.3 từng mở loopback/API/player và dừng sạch.
- Camera Activated và web Windows đã vào được tại .101, có ảnh cấu hình thật.
- Mac tới đúng phần cứng camera; TCP 80/443/554/8000 mở, HTTP root 200.

**Chưa có:**
- Kết quả Windows HTTP Digest curl.exe: dừng trước khi người dùng báo kết quả.
- RTSP có xác thực trên Windows, frame thật, codec/GOP/B-frame/audio.
- MediaMTX đọc camera, browser giải mã hình thật, số đo glass-to-glass.
- CLI native Windows, Linux/Docker/WSL, VPN, WAN recovery, mobile và 200 peers.

**Lịch sử Mac không nên lặp lại:**
- Web, HTTP Digest Python/curl và RTSP DESCRIBE đều 401.
- Người dùng xác nhận mật khẩu chính xác; nhập lại cục bộ cho cùng giá trị cũ. Không kết luận người dùng nhớ sai.
- Một thử nghiệm riêng được cho phép với IP nguồn .250/32 vẫn 401. Alias đã gỡ, DHCP/route/Internet được kiểm tra lại.
- Chưa xác định nguyên nhân. Không có bằng chứng camera cấm macOS; lỗi cũng không chỉ ở IP .100 hay client Python.
- Không reset, đổi mật khẩu, tắt bảo vệ đăng nhập hoặc đổi thuật toán để thử đoán.
- Smoke cũ không có video: media_decoded=false, camera_connected=false.
- Báo cáo thô/helper/runtime cũ đã xóa theo yêu cầu; chỉ giữ tóm tắt không chứa bí mật.

## 6. W0 — việc lập trình đầu tiên trên Windows

**CLI hiện chưa Windows-native-ready.** Lỗi installer/quyền/process của CLI không được diễn giải thành lỗi camera.

Cần triển khai một thay đổi hẹp, có kiểm tra thật trên Windows:

1. Installer hiện chỉ có hai Darwin tar.gz. Thêm Windows amd64 ZIP chính thức, SHA256 ghim, giải nén an toàn, nhận diện mediamtx.exe. Giữ đường macOS hiện có.
2. Sửa executable/path mặc định, đuôi .exe và đường có khoảng trắng; kiểm tra ffprobe.exe.
3. Private-file code dùng 0600/0700 và os.fchmod. Thực hiện NTFS DACL theo SID thực thi, atomic write và kiểm tra reparse point/symlink; không bỏ guard để chạy qua. Windows chmod không cung cấp POSIX owner-only permissions. [Python os.chmod](https://docs.python.org/3/library/os.html#os.chmod)
4. Runtime đang dùng selectors trên stdout pipe. Windows selectors không hỗ trợ pipe; thay bằng cơ chế phù hợp, giữ deadline, child im lặng, dòng dài và redaction qua đoạn đọc. [Python selectors](https://docs.python.org/3/library/selectors.html)
5. Ctrl+C/timeout phải dừng và chờ đúng child thuộc phiên, không kill tiến trình khác.
6. Giữ codec gate: ≥60 giây frame thật, H.264/1280×720/25fps/no audio/0 B-frame, GOP đo được. Không hạ ngưỡng hoặc dùng metadata thay frame.
7. Thêm regression cho ACL, ZIP/path traversal, executable path, lỗi/timeout/cleanup. Giữ bảo vệ POSIX trên POSIX; không xóa/skip kiểm tra để báo xanh trên Windows.

W0 đạt khi CLI thực sự xử lý Windows path/ACL, chạy MediaMTX loopback có giới hạn và dừng sạch trên Windows, log không lộ bí mật. Đây chưa phải bằng chứng camera hay độ trễ.

### Interpreter và lệnh kiểm tra của phiên Windows sau

Cần Python 3.9+; chọn một bản còn được hỗ trợ từ [Python chính thức](https://www.python.org/downloads/windows/). Chưa giả định laptop đã cài Python hoặc launcher py. Nếu py không có, xác định python.exe đúng bản trước; không tự đổi PATH/cài công cụ để bỏ qua lỗi.

Sau khi port W0, các lệnh sau tương ứng phần kiểm tra của make check; không yêu cầu cài GNU Make chỉ để chạy chúng:

~~~powershell
py -3 --version
py -3 -m compileall -q scripts tests
py -3 scripts/poc.py --help
py -3 -m unittest discover -s tests -v
py -3 scripts/poc.py doctor
py -3 scripts/poc.py smoke --mediamtx-bin .local/tools/mediamtx-1.21.3/mediamtx.exe
~~~

Lệnh smoke giả định W0 đã chọn đường giải nén đó; điều chỉnh theo installer thực tế. doctor báo thiếu prerequisites không có nghĩa test thất bại hay camera sai mật khẩu. Smoke không dùng camera thật. Ghi OS/Python/MediaMTX/FFprobe version và kết quả thực, không ghi PASS trước khi chạy.

### MediaMTX Windows — thông tin phát hành đã đối chiếu

- Version: v1.21.3.
- Asset: mediamtx_v1.21.3_windows_amd64.zip.
- SHA256 công bố: b2f5246b07cb72961df03b8d5e8cad43dc657bcf3f49a87bb031bdf22721af74.
- [Release chính thức](https://github.com/bluenviron/mediamtx/releases/tag/v1.21.3).
- [ZIP Windows](https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/mediamtx_v1.21.3_windows_amd64.zip).
- [Checksum chính thức](https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/checksums.sha256).

Hash đối chiếu metadata asset GitHub ngày 01/11/2026; ZIP Windows chưa được tải/chạy trên Mac. Khi tải phải tính hash lại trước khi giải nén/chạy.

~~~powershell
New-Item -ItemType Directory -Force .local/tools
$archive = ".local/tools/mediamtx_v1.21.3_windows_amd64.zip"
Invoke-WebRequest -Uri "https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/mediamtx_v1.21.3_windows_amd64.zip" -OutFile $archive
$expected = "b2f5246b07cb72961df03b8d5e8cad43dc657bcf3f49a87bb031bdf22721af74"
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA256 mismatch; stop" }
~~~

Lệnh trên dành cho phiên Windows sau, chưa chạy trong lần bàn giao. Chọn FFprobe từ nhà cung cấp Windows được [FFmpeg chính thức](https://ffmpeg.org/download.html#build-windows) dẫn tới; ghi version/hash/provenance trước khi dùng. Không mang binary Darwin hoặc driver cũ sang.

## 7. W1 — mạng và một lần kiểm tra xác thực

Chỉ thực hiện khi người dùng bắt đầu lại trên Windows. Đầu tiên đọc môi trường:

~~~powershell
Get-NetAdapter -Physical | Format-Table Name,InterfaceDescription,Status,LinkSpeed -AutoSize
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias,IPAddress,PrefixLength,AddressState -AutoSize
Get-NetIPInterface -AddressFamily IPv4 | Format-Table InterfaceIndex,InterfaceAlias,AutomaticMetric,InterfaceMetric -AutoSize
Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Format-Table InterfaceIndex,NextHop,RouteMetric -AutoSize
~~~

Camera đi Ethernet, Internet đi Wi-Fi. Nếu ER605 chưa có WAN, default qua Ethernet có thể làm Codex mất Internet.

Nếu cần chỉnh ưu tiên: ghi AutomaticMetric/InterfaceMetric cũ, xác định đúng ifIndex rồi phê duyệt thay đổi mạng. Tổng RouteMetric + InterfaceMetric phải ưu tiên Wi-Fi. Ví dụ 10/500 chỉ là điểm khởi đầu, không áp dụng mù quáng.

~~~powershell
# Thay các số trong <> bằng ifIndex thật trước khi dùng.
Set-NetIPInterface -InterfaceIndex <WIFI_IFINDEX> -AddressFamily IPv4 -AutomaticMetric Disabled -InterfaceMetric 10
Set-NetIPInterface -InterfaceIndex <ETHERNET_IFINDEX> -AddressFamily IPv4 -AutomaticMetric Disabled -InterfaceMetric 500
~~~

Hoàn tác theo giá trị đã ghi, bật AutomaticMetric nếu trước đó bật. Không sửa DNS/gateway hoặc tắt adapter hàng loạt. Route LAN /24 cụ thể vẫn thắng default /0; kiểm tra riêng nếu hai mạng trùng subnet. [Microsoft Set-NetIPInterface](https://learn.microsoft.com/en-us/powershell/module/nettcpip/set-netipinterface), [Get-NetRoute](https://learn.microsoft.com/en-us/powershell/module/nettcpip/get-netroute).

### Đối chiếu cùng giao thức

Web Windows thành công chưa chứng minh HTTP Digest stateless hoặc RTSP. Nếu cần tiếp tục, thử đúng một lần rồi dừng khi 401/khóa:

~~~powershell
curl.exe -q --digest --user admin --retry 0 --max-redirs 1 --connect-timeout 3 --max-time 8 --noproxy "*" --silent --output NUL --write-out "HTTP=%{http_code}\n" http://192.168.0.101/ISAPI/System/deviceInfo
~~~

Nhập mật khẩu ở prompt của curl, không viết sau --user hoặc gửi vào chat. HTTP=200 chỉ chứng minh endpoint này; chưa chứng minh RTSP/video. HTTP=000 hoặc không có curl.exe: xử lý môi trường/mạng, không cài phần mềm tự động. Không bật source tự retry trong MediaMTX trước khi xác minh nguồn.

## 8. W2 — camera, codec và video thật

1. Backup camera/ER605 riêng tư trước thay đổi; không upload backup lên Git/chat.
2. Trong web camera: Cấu hình → Video và âm thanh. Đọc khả năng từng stream; chọn 102 chỉ khi hỗ trợ 720p/25fps, nếu không dùng 101.
3. H.264 thường, 1280×720, 25fps, chỉ video/no audio; tắt H.264+/H.265+/Smart Codec trên stream POC.
4. Bắt đầu GOP 25 và CBR khoảng 1,5 Mbps; đối chứng GOP 12–13 sau baseline. Baseline profile nếu có, nhưng vẫn phải đo 0 B-frame thật.
5. Sau W0, tạo private JSON/YAML với NTFS ACL; không điền credential vào template Git. Dữ liệu thật ở .local.
6. MediaMTX Windows chỉ loopback: RTSP 8554, WebRTC HTTP 8889, ICE UDP 8189, API 9997. Tắt RTMP/HLS/SRT/MoQ/recording và endpoint không dùng.
7. Khi nguồn đã xác minh, chạy có deadline; dừng khi camera từ chối. Không dump raw logs/RTSP URL.
8. FFprobe ≥60 giây frame thật, codec gate, browser giải mã hình chuyển động, rồi mới đo glass-to-glass.
9. Ca chốt M1 ≥60 phút, ≥300 mẫu quang học, có cảnh sáng/tối/chuyển động. Không dùng ping/ICE connected thay độ trễ. Theo docs/latency-measurement-procedure.md.

Schema tham khảo: infra/mediamtx/camera-source.example.json gồm scheme/host/port/channel/username/password/transport. Host dùng IP vừa xác nhận, username admin, channel theo khả năng camera; thay cả hai placeholder ở bản sao riêng, nhập password cục bộ. Không chạy configure trước khi W0 đã thực thi và kiểm tra được ACL riêng tư.

Nếu Defender/sandbox hỏi quyền, chỉ xét đúng dịch vụ/đích; không tắt firewall hoặc mở POC ra LAN/public để “cho chạy”.

## 9. W3 — Singapore và VPN

Sau M1: xác nhận firmware ER605, backup, địa điểm/ISP/upload/CGNAT và quyền VPS. Cấp máy chủ/cost, đổi WAN/firmware/router/firewall cần phê duyệt riêng.

Theo infra/vpn: server chủ động kéo camera qua WireGuard, route hẹp, kiểm tra return path, TCP/UDP thật. Giữ camera/admin/RTSP kín Internet. Chưa có VPS, peer, khóa VPN hoặc benchmark WAN đi theo repo.

M3+ chỉ mở theo kế hoạch: codec/LAN latency, tunnel thật, WAN/reboot recovery, rồi trình duyệt Lào/Việt Nam và production. Mobile, 200 peers, recording chưa nghiệm thu.

## 10. Prompt bắt đầu trong Codex Windows

Dán vào chat mới đã mở repo:

~~~text
Tiếp tục DEV.ONE Secure Live trên Windows. Đọc AGENTS.md, HANDOFF_WINDOWS.md, README.md, PDF, kế hoạch gốc và toàn bộ source/config/tests cần thiết trước khi sửa. Mac đã chấm dứt kiểm thử và được dọn; không yêu cầu khôi phục runtime hoặc lặp lại chẩn đoán trên Mac.

Mục tiêu một camera H.264 720p/25fps không âm thanh, p95 glass-to-glass <=1000ms, hướng tới p50 <=500ms, người xem Lào và Việt Nam, không Edge Agent tại điểm đặt camera. Camera đã Activated; người dùng xác nhận mật khẩu đúng. Không reset/đổi mật khẩu/tắt bảo vệ để thử đoán.

Bắt đầu W0: đọc môi trường Windows, lập project map, rồi triển khai Windows native cho CLI POC: ZIP/hash, .exe/path, NTFS ACL, pipe/subprocess/timeout/cleanup. Giữ bảo vệ POSIX trên POSIX và codec/sample gates. Không tự cài package, đổi mạng/router hoặc tạo hạ tầng trả phí. Tuân thủ workflow/delegation của phiên Windows; không giả định Antigravity/model của Mac đã có trên máy mới.

Khi W0 đạt kiểm tra phần mềm Windows, tiếp tục W1/W2 có giới hạn. Dừng xác thực khi 401/khóa; bí mật chỉ ở file cục bộ. Chưa xây website/API/DB production trước cổng M0-M2. Báo lệnh, kết quả thực và phần chưa xác minh.
~~~

## 11. Dọn Mac và nguyên tắc bàn giao tiếp

Đã xóa runtime .local/.runtime, credential JSON, config sinh, báo cáo/helper, MediaMTX/FFprobe/archive và gói HP chưa cài. Đã dọn worktree/task/log worker cũ sau xác nhận inactive; source hoàn tất giữ ở main.

IP/route thử đã gỡ; Ethernet DHCP, Wi-Fi ưu tiên theo lựa chọn người dùng. Không gỡ Codex/Git/Python/gh có sẵn, không đổi PATH/shell profile hoặc camera/router/firmware/WAN trong lần dọn. Ảnh/PDF/kế hoạch/source/tests giữ nguyên. Bằng chứng test đã nêu là lịch sử; không chạy lại trong lần bàn giao.

Sau mỗi phiên Windows, cập nhật docs/implementation-status.md: commit, OS/runtime, W0/W1/W2, file đổi, lệnh/kết quả thật, process còn chạy, thay đổi mạng và rollback, bước tiếp theo. Không commit .local, media, binary, ảnh tem có key hoặc bí mật.
