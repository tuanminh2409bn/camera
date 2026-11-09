"use client";
import { useEffect, useState } from "react";
import type { Auth, OperationCode, ServiceStatus } from "@devone/contracts";
import { request } from "./api";

const labels: Record<OperationCode, string> = {
  API: "Đăng nhập và phân quyền",
  WEB_TLS: "Website và chứng chỉ HTTPS",
  MEDIA: "Hình trực tiếp",
  AUDIO: "Âm thanh trực tiếp",
  MEDIA_PROGRESS: "Luồng video đang cập nhật",
  AIR: "Kết nối với NUC",
  AIR_AUTH: "Xác thực camera",
  AIR_DISK: "Dung lượng và bảo vệ ổ NUC",
  RECORDING: "Ghi hình đúng yêu cầu",
  SERVER_DISK: "Dung lượng máy chủ",
  BACKUP: "Bản sao lưu hằng ngày",
  BACKUP_TIMER: "Lịch sao lưu tự động",
};
const states = {
  ok: "Bình thường",
  pending: "Đang xác minh",
  firing: "Cần kiểm tra",
  recovering: "Đang xác nhận phục hồi",
} as const;
const time = (value: string) => new Date(value).toLocaleString("vi-VN");
export function Operations({ auth }: { auth: Auth }) {
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false,
      busy = false;
    let controller: AbortController | null = null;
    async function refresh() {
      if (busy) return;
      busy = true;
      const active = new AbortController();
      controller = active;
      const deadline = setTimeout(() => active.abort(), 8000);
      try {
        const result = await request<ServiceStatus>(
          "/api/admin/service-status",
          auth,
          { signal: active.signal },
        );
        if (!cancelled) {
          setStatus(result);
          setFailed(false);
        }
      } catch {
        if (!cancelled) {
          setStatus(null);
          setFailed(true);
        }
      } finally {
        clearTimeout(deadline);
        if (controller === active) controller = null;
        busy = false;
      }
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 10000);
    return () => {
      cancelled = true;
      controller?.abort();
      clearInterval(timer);
    };
  }, [auth.csrfToken]);
  const operations = status?.operations;
  const liveUnavailable =
    status && (!status.mediaHealthy || !status.airHealthy);
  const alerts = operations?.available
    ? operations.checks.filter(
        (x) => x.status === "firing" || x.status === "recovering",
      )
    : [];
  const pending = operations?.available
    ? operations.checks.filter((x) => x.status === "pending")
    : [];
  return (
    <section className="operations-panel" aria-labelledby="operations-heading">
      <h2 id="operations-heading">Tình trạng hệ thống</h2>
      {failed ? (
        <p className="error" role="alert">
          Không lấy được trạng thái hệ thống. Hãy kiểm tra kết nối và thử lại.
        </p>
      ) : !operations ? (
        <p role="status">Đang kiểm tra…</p>
      ) : !operations.available ? (
        <p className="error" role="alert">
          {operations.reason === "stale"
            ? "Dữ liệu giám sát đã cũ. Chưa thể xác nhận hệ thống bình thường."
            : "Bộ giám sát chưa cung cấp trạng thái. Cần kiểm tra dịch vụ giám sát."}
        </p>
      ) : (
        <>
          <p
            className={
              alerts.length || liveUnavailable
                ? "error"
                : pending.length
                  ? "operations-pending"
                  : "success"
            }
            role={alerts.length || liveUnavailable ? "alert" : "status"}
          >
            {alerts.length
              ? `${alerts.length} cảnh báo đang mở`
              : liveUnavailable
                ? "Live hoặc kết nối NUC đang bất thường. Bộ giám sát đang cập nhật."
                : pending.length
                  ? `Đang xác minh ${pending.length} dấu hiệu bất thường`
                  : "Các kiểm tra hiện tại đều bình thường"}
          </p>
          <p className="operations-note">
            Cập nhật: {time(operations.updatedAt)} · Kiểm tra mỗi phút
          </p>
          {alerts.length > 0 && (
            <ul className="operations-alerts">
              {alerts.map((item) => (
                <li key={item.code}>
                  <strong>{labels[item.code]}</strong> — {states[item.status]}
                  {item.since ? `, từ ${time(item.since)}` : ""}
                </li>
              ))}
            </ul>
          )}
          <details>
            <summary>Chi tiết {operations.checks.length} kiểm tra</summary>
            <dl className="operations-checks">
              {operations.checks.map((item) => (
                <div key={item.code}>
                  <dt>{labels[item.code]}</dt>
                  <dd
                    className={
                      item.status === "ok"
                        ? "operations-ok"
                        : item.status === "pending"
                          ? "operations-pending"
                          : "operations-warning"
                    }
                  >
                    {states[item.status]}
                    {item.value !== null &&
                    (item.code === "AIR_DISK" || item.code === "SERVER_DISK")
                      ? ` · ${(item.value / 1024 ** 3).toFixed(1)} GiB trống`
                      : item.value !== null && item.code === "WEB_TLS"
                        ? ` · ${item.value} ngày`
                        : ""}
                  </dd>
                </div>
              ))}
            </dl>
          </details>
          {operations.traffic && (
            <p className="operations-note">
              Traffic gửi ra đã đo:{" "}
              <strong>
                {(operations.traffic.bytes / 1024 ** 3).toFixed(2)} GiB
              </strong>{" "}
              từ {time(operations.traffic.since)}. Số này không phải traffic
              tính phí hoặc quota còn lại của DigitalOcean.
            </p>
          )}
          {operations.events.length > 0 && (
            <details>
              <summary>Diễn biến gần đây</summary>
              <ul className="operations-events">
                {operations.events
                  .slice(-10)
                  .reverse()
                  .map((event, index) => (
                    <li key={`${event.code}/${event.at}/${index}`}>
                      {time(event.at)} · {labels[event.code]}:{" "}
                      {event.kind === "firing"
                        ? "phát hiện sự cố"
                        : "đã phục hồi"}
                    </li>
                  ))}
              </ul>
            </details>
          )}
        </>
      )}
      <p className="operations-note">
        Cảnh báo hiện chỉ hiển thị tại đây khi mở trang Admin.
      </p>
    </section>
  );
}
