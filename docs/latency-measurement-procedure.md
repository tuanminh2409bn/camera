# Quy trình đo độ trễ Glass-to-Glass và Mẫu báo cáo đã làm sạch (M1–M3)

Tài liệu này chuẩn hóa phương pháp đo độ trễ thực tế và mẫu báo cáo theo Mục 2 và Mục 9 của [`KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md`](../KE_HOACH_TRIEN_KHAI_LIVESTREAM_05_1_GIAY.md).
**Lưu ý:** Tài liệu này không chứa số liệu đo giả lập. Mọi phép đo thực tế chỉ được ghi nhận khi có camera và thiết bị thật.

## 1. Nguyên tắc bắt buộc khi đo độ trễ

1. **Định nghĩa Glass-to-Glass:**
   - Là khoảng thời gian từ lúc sự kiện vật lý/quang học xuất hiện trước ống kính camera đến lúc hình ảnh của sự kiện đó hiển thị trên màn hình thiết bị xem.
   - **Không dùng** ICMP ping, thời gian phản hồi HTTP/API, thời điểm `ICE connected` hoặc `jitterBufferDelay` từ `RTCPeerConnection.getStats()` để thay thế cho độ trễ glass-to-glass.
2. **Sai số phép đo mục tiêu (≤ 50 ms):**
   - Phải lượng hóa được sai số của công cụ đo (tốc độ khung hình máy quay đối chứng, tần số quét màn hình, độ lệch đồng hồ).
   - Khi xét ngưỡng nghiệm thu **p95 ≤ 1.000 ms** (hướng tới **p50 ≤ 500 ms** và sàn LAN **p95 ≤ 400 ms** ở M1), phải tính cả sai số phép đo. Nếu chưa định lượng được sai số, kết quả chỉ được ghi là ước lượng sơ bộ.
3. **Không dùng Timestamp OSD của Camera nếu chưa xác minh:**
   - Không lấy đồng hồ chồng lên hình (OSD timestamp) của camera làm mốc thời gian gốc trừ khi đã đo và chứng minh được độ trễ từ lúc cảm biến thu sáng đến lúc gắn timestamp.
   - Không dùng thời gian của server MediaMTX khi nhận gói RTSP làm thời điểm sự kiện.

## 2. Phương pháp thiết lập bài đo

### 2.1. Đo trong phòng Lab / Cùng địa điểm (`LAT-01`)

1. Đặt một màn hình tần số quét cao (60/120 Hz) hiển thị đồng hồ bấm giờ mili-giây kèm bộ đếm mã khung hình (frame counter / QR / vạch màu thay đổi mỗi khung) ngay trước ống kính camera Hikvision.
2. Đặt màn hình thiết bị xem (trình duyệt mở luồng WebRTC) cạnh màn hình nguồn sao cho cả hai nằm trong cùng một khung hình.
3. Dùng một máy quay độc lập ở chế độ **120 fps hoặc 240 fps** (ví dụ điện thoại quay slow-motion 240 fps, tương ứng bước thời gian ~4,17 ms/frame) ghi hình đồng thời cả màn hình nguồn và màn hình người xem.
4. Công thức tính cho từng mẫu thứ $i$:
   $$\text{Latency}_i = T_{\text{hiển thị nguồn tại khung ảnh chụp}} - T_{\text{hiển thị trên trình duyệt tại cùng khung ảnh chụp}}$$
5. Sai số đo tối đa ước tính trong chế độ một máy quay chung khung hình:
   $$\epsilon \approx \frac{1000}{f_{\text{màn hình nguồn}}} + \frac{1000}{f_{\text{màn hình xem}}} + \frac{1000}{f_{\text{máy quay slow-mo}}}$$

### 2.2. Đo giữa hai địa điểm độc lập (`LAT-02` - Lào ↔ Singapore ↔ Việt Nam/Lào)

1. Sử dụng hai nguồn đồng hồ tham chiếu đã được đồng bộ và **đo kiểm độ lệch (clock offset)** trước và sau ca đo. Chỉ bật NTP mặc định của hệ điều hành là chưa đủ nếu chưa ghi nhận offset/dispersion thực tế.
2. Đặt đồng hồ tham chiếu 1 (hiển thị mili-giây + mã frame) trước ống kính camera tại điểm phát.
3. Đặt đồng hồ tham chiếu 2 cạnh màn hình trình duyệt tại điểm xem và dùng máy quay 120/240 fps chụp đồng thời cả màn hình trình duyệt lẫn đồng hồ tham chiếu 2.
4. Ghi lại độ lệch đồng hồ trước và sau bài thử ($\Delta_{\text{clock, before}}, \Delta_{\text{clock, after}}$) và cộng biên độ lệch vào sai số phép đo $\epsilon$.

## 3. Cỡ mẫu và điều kiện bài thử

- **Số lượng mẫu tối thiểu:** Mỗi cấu hình ứng viên cuối phải thu tối thiểu **300 mẫu quang học glass-to-glass** rải đều trong ít nhất **30 phút** (và chạy liên tục **60 phút** đối với bài chốt profile ở M1), bao gồm cả khung giờ bình thường và giờ cao điểm.
- **Điều kiện ánh sáng & chuyển động:** Phải đo cả cảnh **ban ngày (đủ sáng)** và **ban đêm (hồng ngoại/thiếu sáng)** có chuyển động thực tế trong khung hình (không đo cảnh tĩnh nhìn vào tường trắng).
- **Báo cáo tách biệt:**
  - Không gộp chung số liệu của Việt Nam và Lào thành một con số p95 tổng hợp.
  - Không gộp chung đường UDP trực tiếp với đường qua TURN relay.
  - Báo riêng **thời gian có khung hình đầu tiên (startup time, mục tiêu p95 ≤ 2 giây)** và **tỷ lệ thời gian đứng hình (freeze ≤ 1% thời gian quan sát)**.
- **Số liệu chẩn đoán song song (`getStats()` mỗi 2 giây):**
  - Thu thập `currentRoundTripTime`, `packetsLost`, `jitter`, `framesDecoded`, `framesDropped`, `freezeCount`, `totalFreezesDuration`, `bytesReceived` và sai phân $\Delta\text{jitterBufferDelay} / \Delta\text{jitterBufferEmittedCount}$ để định vị điểm nghẽn khi độ trễ vượt ngân sách.

## 4. Mẫu báo cáo đo độ trễ đã làm sạch (Sanitized Latency Report Template)

Sao chép mẫu dưới đây khi thực hiện bài đo thực tế (lưu file dữ liệu thô trong `evidence/` đã được `.gitignore`, và chỉ đưa bản báo cáo đã ẩn thông tin nhạy cảm vào tài liệu chia sẻ):

```markdown
# Báo cáo kiểm thử độ trễ Glass-to-Glass (Sanitized)

- **Mã lần chạy (Run ID):** `PENDING` (ví dụ: `M1-LAN-202611XX-01`)
- **Ngày / Giờ thực hiện (UTC & Giờ địa phương):** `PENDING`
- **Người thực hiện & Xác minh:** `PENDING`
- **Git Commit / Config Hash (SHA256):** `PENDING`
- **Phiên bản phần mềm:** MediaMTX `v1.21.3` (native / container digest: `PENDING`)

## 1. Thông tin thiết bị và Cấu hình (Đã ẩn thông tin mật)

- **Camera Model & Firmware:** `PENDING`
- **Router Model & Firmware:** `PENDING`
- **Kênh RTSP & Vận chuyển:** Kênh `102` (hoặc `101`), `rtspTransport: tcp | udp`
- **Cấu hình Codec xác nhận bởi `poc.py probe`:**
  - Codec / Profile: `PENDING` (yêu cầu: `h264`)
  - Độ phân giải / FPS: `PENDING` (yêu cầu: `1280x720 @ 25 fps`)
  - B-frames quan sát được (trong ≥ 60s): `PENDING` (yêu cầu: `0`)
  - GOP đo được (frames) / Bitrate / Rate Control: `PENDING`
  - Audio stream: `PENDING` (yêu cầu: `0`)
- **Điều kiện cảnh quay:** `[Sáng / Tối / Có chuyển động]` — `PENDING`
- **Vị trí nguồn & Vị trí người xem / ISP:** `PENDING`
- **Thiết bị & Trình duyệt người xem:** `PENDING` (ví dụ: Chrome macOS / Safari iOS / Chrome Android)
- **Đường truyền ICE được chọn:** `[Direct UDP / TURN Relay]` — `PENDING`
- **Số phiên đồng thời trên MediaMTX:** `PENDING`

## 2. Phương pháp đo và Sai số

- **Chế độ đo:** `[Một máy quay 240fps chung khung hình (Lab) / Hai đồng hồ đồng bộ (2 địa điểm)]`
- **Tần số quét màn hình nguồn / màn hình xem / tốc độ máy quay:** `PENDING`
- **Độ lệch đồng hồ trước & sau bài đo (nếu 2 địa điểm):** `PENDING`
- **Tổng sai số phép đo ước tính ($\pm \epsilon$ ms):** `PENDING` (mục tiêu: `≤ 50 ms`)
- **Tổng thời gian quan sát & Tổng số mẫu quang học ($N$):** `PENDING` (yêu cầu: `≥ 30 phút`, `N ≥ 300`)

## 3. Kết quả thống kê

| Chỉ số | Toàn bài thử | Cửa sổ 5 phút tệ nhất | Ngưỡng mục tiêu | Đánh giá |
|---|---:|---:|---:|---|
| Độ trễ Glass-to-Glass `p50` (ms) | `PENDING` | `PENDING` | Hướng tới ≤ 500 ms | `PENDING` |
| Độ trễ Glass-to-Glass `p95` (ms) | `PENDING` | `PENDING` | ≤ 1.000 ms (M1 LAN hướng tới ≤ 400 ms) | `PENDING` |
| Độ trễ Glass-to-Glass `p99` (ms) | `PENDING` | `PENDING` | Ghi nhận thực tế | `PENDING` |
| Độ trễ Glass-to-Glass `max` (ms) | `PENDING` | `PENDING` | Ghi nhận thực tế | `PENDING` |
| Thời gian lên hình đầu tiên `p95` (s) | `PENDING` | N/A | ≤ 2,0 giây | `PENDING` |
| Tỷ lệ thời gian đứng hình / mất hình (%) | `PENDING` | `PENDING` | ≤ 1,0% | `PENDING` |

## 4. Chỉ số chẩn đoán WebRTC (`getStats()`) và Lệnh đã chạy

- **RTT trung bình / p95 (ms):** `PENDING`
- **Packet loss (%) / Jitter (ms):** `PENDING`
- **Jitter buffer delay trung bình / p95 (ms):** `PENDING`
- **Lệnh kiểm chứng đã chạy (đã che RTSP URL/credentials):**
  - `python3 scripts/poc.py probe --source-file .local/camera-source.json --duration 60`
  - `python3 scripts/poc.py run --config .local/mediamtx.poc.yml`
- **Kết luận cổng kiểm soát:** `PENDING` (`PASS` / `FAIL` / `PENDING`)
```
