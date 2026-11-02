# Dịch vụ giám sát ghi hình cục bộ trên MacBook Air (`air_recording_supervisor.pl`)

Tài liệu này mô tả trình giám sát ghi hình nền cục bộ (`scripts/air_recording_supervisor.pl`) và mẫu cấu hình `launchd` phiên người dùng (`infra/macos/recording-agent.plist.example`) cho luồng camera RTSP qua MediaMTX `v1.21.3` trên macOS.

Đã bật trên Air ngày02/11/2026 lúc16:32+07, workspace thực tế `/Users/macbook/Developer/camera`. Xem [checkpoint commissioning](implementation-status.md) để biết các kiểm tra đã đạt và giới hạn. Các lệnh bên dưới chạy **trên Air**, không chạy trên Mac mini.

## 1. Phạm vi và ranh giới triển khai

- **Chỉ chạy trong phiên đăng nhập hiện tại (Session-only LaunchAgent):** Mẫu `infra/macos/recording-agent.plist.example` dùng placeholder `__WORKSPACE__` và được render/bootstrap trực tiếp từ thư mục dự án cục bộ (ví dụ `.local/recording-service/recording-agent.plist`), **không** cài đặt vào `/Library/LaunchDaemons`, `/Library/LaunchAgents` hay `~/Library/LaunchAgents`.
- **Không tự phục hồi qua đăng xuất/khởi động lại hoặc gập máy:** `KeepAlive` được đặt `false`. Dịch vụ chỉ chạy khi người dùng đang đăng nhập, máy mở nắp (lid-open) và cắm nguồn AC (sử dụng `/usr/bin/caffeinate -i -s` để ngăn idle/system sleep khi đang cắm sạc). Không thay đổi cấu hình FileVault, tự động đăng nhập, cài đặt sleep toàn hệ thống hay cấu hình mạng/WAN/router.
- **Chưa xác nhận độ bền 24 giờ:** Trình giám sát cung cấp cơ chế kiểm soát tiến trình con, khóa phiên, chốt dừng khi sai mật khẩu camera và tạm dừng ghi khi đầy ổ đĩa, nhưng chưa có bằng chứng chạy bền liên tục 24 giờ thực tế hay số đo độ trễ quang học p95 glass-to-glass.
- **Không bao gồm Admin website/RBAC/Internet exposure:** Mọi listener của MediaMTX chỉ gắn với loopback `127.0.0.1` (`8554` RTSP, `8889`/`8189` WebRTC, `9997` Control API, `9996` Playback). Không mở cổng ra LAN/Internet, không có cơ sở dữ liệu hay máy chủ xác thực đa người dùng.

## 2. Cấu trúc tệp riêng tư và bảo mật thông tin xác thực

Mọi cấu hình nhạy cảm, tệp khóa, nhật ký và trạng thái đều nằm trong thư mục riêng tư bị `.gitignore` chặn:

- `<WORKSPACE>/.local` (bắt buộc quyền `0700`, không nhận symlink):
  - `.local/camera-source.json` (`0600`): thông tin kết nối RTSP camera.
  - `.local/recording-admin.json` (`0600`): tài khoản/mật khẩu riêng cho cổng phát lại (`playback` trên `127.0.0.1:9996`).
  - `.local/mediamtx.recording.poc.yml` (`0600`): cấu hình MediaMTX cục bộ.
  - `.local/tools/mediamtx-1.21.3/mediamtx` (`0755`/`0700`): thực thi MediaMTX `v1.21.3` đã ghim mã băm SHA256 (`2d21dd021fa7d0e667b24f8850555f29d718424c19d5ce9e18163a8b893034fd`). Trình giám sát kiểm tra SHA256 trước khi khởi chạy và không gọi binary tùy ý từ `PATH`.
- `<WORKSPACE>/.local/recording-service` (quyền `0700`, không nhận symlink hoặc tệp quyền lỏng):
  - `supervisor.lock` (`0600`): khóa độc quyền `flock` (`LOCK_EX | LOCK_NB`) ngăn chạy trùng phiên thứ hai.
  - `status.json` (`0600`): trạng thái hiện tại được ghi nguyên tử (atomic write), không chứa mật khẩu.
  - `supervisor.log`, `supervisor.log.1`, `supervisor.log.2` (`0600`): nhật ký đã ẩn mật khẩu (redacted), giới hạn 5 MiB mỗi tệp và giữ tối đa 2 bản xoay vòng.
  - `auth-stop.latch` (`0600`, chỉ xuất hiện khi bị từ chối xác thực camera): chốt khóa yêu cầu người vận hành kiểm tra trước khi chạy lại.
  - `launchd.stdout.log`, `launchd.stderr.log` (`0600`): đầu ra chuẩn khi chạy qua `launchd`.

Trình giám sát không bao giờ truyền mật khẩu qua `argv`, không in biến môi trường hay toàn bộ tệp cấu hình, tự động ẩn thông tin xác thực trong URL RTSP và cả dạng chuỗi gốc lẫn percent-encoded trước khi ghi nhật ký, đồng thời hủy an toàn các dòng log quá dài bị cắt dở để tránh rò rỉ một phần mật khẩu.

## 3. Khởi chạy, kiểm tra trạng thái và dừng sạch

### Chạy trực tiếp ở foreground (hoặc chạy thử có thời hạn)

```sh
# Chạy thử có giới hạn thời gian (ví dụ 30 giây) để kiểm tra:
/usr/bin/perl scripts/air_recording_supervisor.pl --workspace /path/to/workspace --duration 30

# Chạy liên tục ở foreground:
/usr/bin/perl scripts/air_recording_supervisor.pl --workspace /path/to/workspace
```

### Chạy trong phiên đăng nhập qua `launchd` (từ thư mục dự án)

1. Tạo tệp plist riêng tư trong `.local/recording-service/recording-agent.plist` bằng cách thay `__WORKSPACE__` bằng đường dẫn tuyệt đối của workspace và đặt quyền `0600`.
2. Bootstrap vào domain `gui/$(id -u)` của phiên hiện tại:

```sh
launchctl bootstrap "gui/$(id -u)" /path/to/workspace/.local/recording-service/recording-agent.plist
```

### Kiểm tra trạng thái (`status.json` và nhật ký)

```sh
cat /path/to/workspace/.local/recording-service/status.json
tail -n 50 /path/to/workspace/.local/recording-service/supervisor.log
```

Các trường chính trong `status.json`:
- `state`: `"starting"` khi đang chờ nguồn, `"running"`, `"degraded"`, `"paused"`, `"stopped"`, hoặc `"failed"`. Trạng thái/dung lượng được cập nhật lại mỗi 10 giây; `running` chỉ được ghi sau thông báo nguồn sẵn sàng của MediaMTX.
- `reason`: `"ok"`, `"source-not-ready"`, `"disk_low"`, `"disk_unknown"`, `"disk_low_pause_failed"`, `"camera_auth_failed"`, `"auth_latch_present"`, `"duration_elapsed"`, `"signal_received"`, hoặc `"unexpected_child_exit"`.
- `PID` / `pid` / `supervisorPid`: PID của trình giám sát.
- `mediamtxPid`: PID của tiến trình con MediaMTX đang thuộc quyền quản lý (hoặc `null` khi đã dừng).
- `recordingPaused`: `true` nếu đã tạm dừng ghi hình do dung lượng đĩa thấp.
- `authLatchActive`: `true` nếu chốt dừng do lỗi xác thực camera đang kích hoạt.

### Dừng sạch (Clean stop)

- Nếu đang chạy ở foreground: nhấn `Ctrl-C` (`SIGINT`) hoặc gửi `SIGTERM`/`SIGHUP` tới PID của `air_recording_supervisor.pl`.
- Nếu đang chạy qua `launchd`:

```sh
launchctl bootout "gui/$(id -u)/com.devone.camera.air-recording-supervisor"
```

Trình giám sát chỉ gửi `SIGTERM` (và `SIGKILL` có thời hạn nếu cần) tới đúng nhóm tiến trình con MediaMTX do chính nó tạo ra, không dùng `pkill`/`pgrep`.

## 4. Xử lý của người vận hành khi gặp sự cố

### 4.1. Chốt dừng xác thực camera (`auth-stop.latch`)

- **Cơ chế:** Khi nguồn RTSP camera trả về lỗi xác thực (`401`, `403`, `Unauthorized`, `Forbidden`, `authentication failure`), trình giám sát lập tức dừng tiến trình MediaMTX trước chu kỳ thử lại 5 giây của native binary để tránh khóa tài khoản camera. Trình giám sát tạo tệp `.local/recording-service/auth-stop.latch` (`0600`), cập nhật `status.json` (`reason: "camera_auth_failed"`, `authLatchActive: true`) và thoát sạch.
- **Phân biệt với Playback HTTP 401:** Các phản hồi `401` trên cổng phát lại cục bộ (`127.0.0.1:9996`, `[playback]`) là bước thử thách xác thực HTTP bình thường của trình duyệt/client và **không** kích hoạt chốt dừng camera.
- **Phân biệt với mất kết nối mạng tạm thời:** Khi mất LAN hoặc timeout nguồn RTSP không phải lỗi xác thực, trình giám sát để MediaMTX tự kết nối lại và ghi nhận `state: "degraded"`, `reason: "source-not-ready"`.
- **Cách khôi phục của người vận hành:**
  1. Kiểm tra `.local/recording-service/supervisor.log` và `status.json`.
  2. Đối chiếu lại thông tin trong `.local/camera-source.json` và `.local/mediamtx.recording.poc.yml`.
  3. Sau khi đã xác nhận mật khẩu đúng, xóa thủ công tệp chốt:
     ```sh
     rm /path/to/workspace/.local/recording-service/auth-stop.latch
     ```
  4. Khởi động lại trình giám sát. Mọi lần gọi trước khi xóa `auth-stop.latch` đều bị từ chối ngay từ đầu.

### 4.2. Tạm dừng ghi hình khi dung lượng ổ đĩa thấp (`disk_low`)

- **Trước khi chạy:** Trình giám sát kiểm tra dung lượng trống qua `/bin/df -k -P`. Nếu không xác định được hoặc thấp hơn ngưỡng dự phòng **15 GiB** (`16,106,127,360` byte), trình giám sát từ chối khởi động.
- **Trong khi chạy:** Định kỳ mỗi 10 giây, nếu dung lượng trống xuống dưới **15 GiB**, trình giám sát gọi duy nhất API loopback:
  `PATCH http://127.0.0.1:9997/v3/config/paths/patch/live` với body `{"record":false}`.
  - Nếu API trả về `200`, MediaMTX ngừng ghi tệp mới lên SSD nhưng vẫn giữ nguyên luồng xem trực tiếp (`live`) và cổng phát lại (`playback`), đồng thời `status.json` chuyển sang `state: "paused"`, `reason: "disk_low"`, `recordingPaused: true`. Trình giám sát **không tự động bật lại** ghi hình trong cùng phiên chạy đó.
  - Nếu yêu cầu tạm dừng không xác nhận được (`!= 200` hoặc quá thời gian chờ), trình giám sát dừng an toàn tiến trình con MediaMTX để bảo vệ ổ đĩa.
- **Cách khôi phục:** Giải phóng dung lượng SSD để vượt trên mức dự phòng 15 GiB, dừng trình giám sát hiện tại và khởi động lại phiên mới.

## 5. Cơ chế lưu giữ 1 ngày (`deleteAfter: 1d`) và ranh giới đoạn ghi

- Trình giám sát **không** tự xóa tệp video; việc dọn dẹp thuộc về cơ chế `recordDeleteAfter: 1d` của MediaMTX `v1.21.3`.
- Với cấu hình `part: 1s`, `maxPartSize: 10M`, `segmentDuration: 1m`, `deleteAfter: 1d` (fMP4 trong `.local/recordings/live/`):
  - MediaMTX chỉ đóng và xoay vòng từng đoạn (segment) theo ranh giới khoảng 1 phút (`segmentDuration: 1m`) hoặc khi luồng khởi tạo lại.
  - Bộ dọn dẹp định kỳ (cleaner interval) của MediaMTX `v1.21.3` chạy theo chu kỳ tối đa bằng một nửa `deleteAfter` nhưng giới hạn trần ở mức **tối đa 30 phút một lần**. Do đó, các đoạn ghi quá 24 giờ sẽ được xóa trong vòng tối đa khoảng 30 phút sau khi hết hạn, không phải xóa chính xác từng giây ngay tại mốc 24 giờ 00 giây.

## 6. Xem lại cục bộ bằng tài khoản playback

Tài khoản riêng đã lưu trong `.local/recording-admin.json`; cURL đọc thông tin từ file0600 `.local/recording-admin.curl`, không đặt mật khẩu trong câu lệnh. Playback này chỉ dùng trên Air, chưa có giao diện Admin trên Internet.

Liệt kê các khoảng đã ghi:

```sh
cd /Users/macbook/Developer/camera
/usr/bin/curl -q --config .local/recording-admin.curl --fail 'http://127.0.0.1:9996/list?path=live'
```

Chọn giá trị `start` từ kết quả trên, thay `START_TU_LIST` trong lệnh sau để xuất10giây rồi mở VLC. File xuất thủ công không nằm trong thư mục tự dọn24h; xóa khi không còn cần.

```sh
/usr/bin/curl -q --config .local/recording-admin.curl --fail --get \
  --data-urlencode 'path=live' \
  --data-urlencode 'start=START_TU_LIST' \
  --data-urlencode 'duration=10' \
  --data-urlencode 'format=mp4' \
  --output .local/playback-admin-selected.mp4 'http://127.0.0.1:9996/get'
/usr/bin/open -a VLC .local/playback-admin-selected.mp4
```

Nguồn cơ chế native: [MediaMTX recording](https://mediamtx.org/docs/features/record), [playback](https://mediamtx.org/docs/features/playback), [cleaner tại tagv1.21.3](https://github.com/bluenviron/mediamtx/blob/v1.21.3/internal/recordcleaner/cleaner.go).
