"use client";
import { useEffect, useRef, useState } from "react";
import type { Auth } from "@devone/contracts";
import { request, messageOf } from "./api";
import { Icon } from "./icon";
type Interval = { start: string; duration: number };
function recordingStartMilliseconds(value: string) {
  const milliseconds = Date.parse(value);
  const fraction =
    value.match(/T\d{2}:\d{2}:\d{2}\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/i)?.[1] ?? "";
  // Date truncates finer precision, so round up to stay inside the recording interval.
  return milliseconds + (/[1-9]/.test(fraction.slice(3)) ? 1 : 0);
}
const time = (value: number) =>
  new Date(value).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
function localDateTime(value: number) {
  const date = new Date(value),
    pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
export function Playback({ auth }: { auth: Auth }) {
  const [intervals, setIntervals] = useState<Interval[]>([]),
    [selected, setSelected] = useState(""),
    [offset, setOffset] = useState(0),
    [duration, setDuration] = useState(60),
    [url, setUrl] = useState(""),
    [playingRange, setPlayingRange] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const resource = useRef<string | null>(null),
    generation = useRef(0),
    requesting = useRef(false);
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const data = await request<{ data: Interval[] }>("/api/recordings", auth);
      setIntervals(data.data.filter((item) => item.duration >= 1));
      setSelected((current) =>
        data.data.some((i) => i.start === current && i.duration >= 1)
          ? current
          : (data.data.find((i) => i.duration >= 1)?.start ?? ""),
      );
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    return () => {
      generation.current++;
      if (resource.current)
        void fetch(resource.current, {
          method: "DELETE",
          keepalive: true,
          headers: { "X-CSRF-Token": auth.csrfToken },
        });
    };
  }, [auth.csrfToken]);
  const interval = intervals.find((i) => i.start === selected),
    maxOffset = Math.max(0, Math.floor((interval?.duration ?? 1) - 1)),
    safeOffset = Math.min(offset, maxOffset),
    start = interval
      ? recordingStartMilliseconds(interval.start) + safeOffset * 1000
      : 0,
    clipDuration = interval
      ? Math.min(duration, Math.floor(interval.duration - safeOffset))
      : 0;
  async function play(download = false) {
    if (!interval || requesting.current) return;
    requesting.current = true;
    const current = generation.current;
    setBusy(true);
    setError("");
    try {
      setUrl("");
      setPlayingRange("");
      if (resource.current)
        await request(resource.current, auth, { method: "DELETE" });
      resource.current = null;
      if (current !== generation.current) return;
      const result = await request<{ id: string; url: string }>(
        "/api/playback/sessions",
        auth,
        {
          method: "POST",
          body: JSON.stringify({
            start: new Date(start).toISOString(),
            duration: clipDuration,
            download,
          }),
        },
      );
      const path = `/api/playback/sessions/${result.id}`;
      if (current !== generation.current) {
        void fetch(path, {
          method: "DELETE",
          keepalive: true,
          headers: { "X-CSRF-Token": auth.csrfToken },
        });
        return;
      }
      resource.current = path;
      if (download) {
        const anchor = document.createElement("a");
        anchor.href = result.url;
        anchor.download = "";
        anchor.click();
      } else {
        setUrl(result.url);
        setPlayingRange(
          `${time(start)} – ${time(start + clipDuration * 1000)}`,
        );
      }
    } catch (cause) {
      if (current === generation.current) setError(messageOf(cause));
    } finally {
      requesting.current = false;
      if (current === generation.current) setBusy(false);
    }
  }
  return (
    <section aria-labelledby="playback-heading">
      <div className="section-heading">
        <div>
          <h1 id="playback-heading">Xem lại</h1>
          <p className="subtitle">Camera 01</p>
        </div>
        <button
          className="secondary refresh-button"
          disabled={loading || busy}
          onClick={() => void refresh()}
        >
          <Icon name="refresh" />
          <span>Làm mới</span>
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <div className="empty" role="status">
          <span className="spinner" />
          Đang tải danh sách bản ghi…
        </div>
      ) : intervals.length === 0 ? (
        <div className="empty">
          <Icon name="clock" />
          <h2>Chưa có bản ghi khả dụng</h2>
          <p>NUC cần trực tuyến để truy cập bản ghi. Hãy thử làm mới sau.</p>
        </div>
      ) : (
        <div className="playback-layout">
          <label className="interval-field">
            Khoảng ghi
            <select
              value={selected}
              disabled={busy}
              onChange={(e) => {
                setSelected(e.target.value);
                setOffset(0);
              }}
            >
              {intervals.map((i) => (
                <option key={i.start} value={i.start}>
                  {new Date(i.start).toLocaleString("vi-VN")} ·{" "}
                  {Math.floor(i.duration / 60)} phút{" "}
                  {Math.floor(i.duration % 60)} giây
                </option>
              ))}
            </select>
          </label>
          <div className="playback-player">
            <div className={`video-stage ${url ? "is-active" : ""}`}>
              {url ? (
                <video
                  src={url}
                  controls
                  autoPlay
                  playsInline
                  onError={() =>
                    setError(
                      "Không đọc được đoạn video. Hãy làm mới danh sách và chọn lại thời điểm.",
                    )
                  }
                  aria-label="Video xem lại"
                />
              ) : (
                <div className="video-empty">
                  <div className="empty-icon">
                    <Icon name="clock" />
                  </div>
                  <h2>
                    {busy ? "Đang chuẩn bị video…" : "Chọn khoảnh khắc cần xem"}
                  </h2>
                  <p>
                    {auth.user.canPlayback
                      ? "Chọn thời điểm rồi nhấn Phát đoạn."
                      : "Chọn thời điểm để tải đoạn video."}
                  </p>
                </div>
              )}
            </div>
            {playingRange && (
              <p className="player-caption">Đoạn đang phát · {playingRange}</p>
            )}
          </div>
          <div className="playback-controls">
            <label>
              Bắt đầu
              <input
                type="datetime-local"
                step={1}
                value={localDateTime(start)}
                min={
                  interval
                    ? localDateTime(Date.parse(interval.start))
                    : undefined
                }
                max={
                  interval
                    ? localDateTime(
                        Date.parse(interval.start) + maxOffset * 1000,
                      )
                    : undefined
                }
                disabled={busy}
                onChange={(e) => {
                  const value = Date.parse(e.target.value);
                  if (Number.isFinite(value) && interval)
                    setOffset(
                      Math.min(
                        maxOffset,
                        Math.max(
                          0,
                          Math.floor(
                            (value - Date.parse(interval.start)) / 1000,
                          ),
                        ),
                      ),
                    );
                }}
              />
            </label>
            <div className="timeline">
              <div className="timeline-control">
                <button
                  className="icon-button secondary"
                  title="Lùi 1 phút"
                  aria-label="Lùi 1 phút"
                  disabled={busy || safeOffset === 0}
                  onClick={() => setOffset(Math.max(0, safeOffset - 60))}
                >
                  <Icon name="left" />
                </button>
                <input
                  aria-label="Mốc bắt đầu trong khoảng ghi"
                  type="range"
                  min={0}
                  max={maxOffset}
                  step={1}
                  value={safeOffset}
                  disabled={busy || maxOffset === 0}
                  onChange={(e) => setOffset(Number(e.target.value))}
                />
                <button
                  className="icon-button secondary"
                  title="Tiến 1 phút"
                  aria-label="Tiến 1 phút"
                  disabled={busy || safeOffset === maxOffset}
                  onClick={() =>
                    setOffset(Math.min(maxOffset, safeOffset + 60))
                  }
                >
                  <Icon name="right" />
                </button>
              </div>
              <div className="timeline-labels">
                <span>{interval ? time(Date.parse(interval.start)) : ""}</span>
                <span>
                  {interval
                    ? time(
                        Date.parse(interval.start) + interval.duration * 1000,
                      )
                    : ""}
                </span>
              </div>
            </div>
            <fieldset className="duration-field">
              <legend>Độ dài đoạn</legend>
              <div className="segmented">
                {[60, 180, 300].map((seconds) => (
                  <button
                    key={seconds}
                    type="button"
                    disabled={busy}
                    className={duration === seconds ? "selected" : ""}
                    aria-pressed={duration === seconds}
                    onClick={() => setDuration(seconds)}
                  >
                    {seconds / 60} phút
                  </button>
                ))}
              </div>
            </fieldset>
            <p className="clip-summary">
              {time(start)} – {time(start + clipDuration * 1000)}
              <span>{clipDuration} giây khả dụng trong đoạn đã chọn</span>
            </p>
            <div className="playback-actions">
              {auth.user.canPlayback && (
                <button
                  disabled={busy || !interval}
                  onClick={() => void play()}
                >
                  <Icon name="play" />
                  {busy ? "Đang chuẩn bị…" : "Phát đoạn"}
                </button>
              )}
              {auth.user.canDownload && (
                <button
                  className="secondary"
                  disabled={busy || !interval}
                  onClick={() => void play(true)}
                >
                  <Icon name="download" />
                  Tải video
                </button>
              )}
            </div>
            <p className="storage-note">
              <Icon name="drive" />
              <span>
                Bản ghi lưu trên NUC khoảng 24 giờ.
                <br />
                NUC cần trực tuyến để xem hoặc tải video.
              </span>
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
