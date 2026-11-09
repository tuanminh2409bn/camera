"use client";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { Auth } from "@devone/contracts";
import { request, messageOf } from "./api";
import { Icon } from "./icon";

type TouchPoint = { x: number; y: number };
type FullscreenVideo = HTMLVideoElement & {
  webkitEnterFullscreen?: () => void;
};
function touchDistance(points: ReadonlyMap<number, TouchPoint>) {
  const [first, second] = points.values();
  return first && second
    ? Math.hypot(first.x - second.x, first.y - second.y)
    : 0;
}

export function Live({
  auth,
  onPlayback,
}: {
  auth: Auth;
  onPlayback?: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null),
    peer = useRef<RTCPeerConnection | null>(null),
    resource = useRef<string | null>(null),
    closing = useRef<Promise<void> | null>(null),
    generation = useRef(0),
    starting = useRef(false),
    touches = useRef(new Map<number, TouchPoint>()),
    pinch = useRef<{ distance: number; zoom: number } | null>(null);
  const [state, setState] = useState("Chưa kết nối"),
    [active, setActive] = useState(false),
    [hasAudio, setHasAudio] = useState(false),
    [playbackBlocked, setPlaybackBlocked] = useState(false),
    [zoom, setZoom] = useState(1),
    [resolution, setResolution] = useState(""),
    [error, setError] = useState("");
  function beginTouch(event: PointerEvent<HTMLDivElement>) {
    if (
      !resolution ||
      event.pointerType !== "touch" ||
      touches.current.size >= 2
    )
      return;
    touches.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    const distance = touchDistance(touches.current);
    if (distance > 0) pinch.current = { distance, zoom };
  }
  function moveTouch(event: PointerEvent<HTMLDivElement>) {
    if (!touches.current.has(event.pointerId)) return;
    touches.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    const start = pinch.current;
    if (!start) return;
    const scaled =
      (start.zoom * touchDistance(touches.current)) / start.distance;
    setZoom(Math.max(1, Math.min(3, Math.round(scaled * 2) / 2)));
  }
  function endTouch(event: PointerEvent<HTMLDivElement>) {
    if (touches.current.delete(event.pointerId)) pinch.current = null;
  }
  async function closeSession() {
    generation.current++;
    peer.current?.close();
    peer.current = null;
    const path = resource.current;
    resource.current = null;
    touches.current.clear();
    pinch.current = null;
    if (video.current) video.current.srcObject = null;
    setHasAudio(false);
    setPlaybackBlocked(false);
    setResolution("");
    if (path)
      closing.current = request<void>(path, auth, { method: "DELETE" }).catch(
        () => {},
      );
    await closing.current;
  }
  async function stop() {
    setZoom(1);
    setActive(false);
    setState("Đã dừng");
    await closeSession();
  }
  useEffect(
    () => () => {
      generation.current++;
      peer.current?.close();
      const path = resource.current;
      if (path)
        void fetch(path, {
          method: "DELETE",
          keepalive: true,
          headers: { "X-CSRF-Token": auth.csrfToken },
        });
    },
    [auth.csrfToken],
  );
  async function playWithSound(current = generation.current) {
    const element = video.current;
    if (current !== generation.current || !element?.srcObject) return;
    element.muted = false;
    element.volume = 1;
    try {
      await element.play();
      if (current === generation.current) setPlaybackBlocked(false);
    } catch (cause) {
      if (current !== generation.current) return;
      if (cause instanceof DOMException && cause.name === "NotAllowedError")
        setPlaybackBlocked(true);
      else if (!(cause instanceof DOMException && cause.name === "AbortError"))
        setError(messageOf(cause));
    }
  }
  async function start() {
    if (starting.current) return;
    starting.current = true;
    setActive(true);
    setState("Đang kết nối");
    setError("");
    const current = generation.current + 1;
    try {
      await closeSession();
      if (current !== generation.current) return;
      const connection = new RTCPeerConnection();
      const incoming = new MediaStream();
      peer.current = connection;
      connection.addTransceiver("video", { direction: "recvonly" });
      connection.addTransceiver("audio", { direction: "recvonly" });
      connection.ontrack = (event) => {
        if (current !== generation.current) return;
        if (!incoming.getTrackById(event.track.id))
          incoming.addTrack(event.track);
        setHasAudio(
          incoming
            .getAudioTracks()
            .some((track) => track.readyState === "live"),
        );
        event.track.onended = () => {
          if (current === generation.current)
            setHasAudio(
              incoming
                .getAudioTracks()
                .some((track) => track.readyState === "live"),
            );
        };
        if (video.current) {
          if (video.current.srcObject !== incoming)
            video.current.srcObject = incoming;
          void playWithSound(current);
        }
      };
      connection.onconnectionstatechange = () => {
        if (current !== generation.current) {
          connection.close();
          return;
        }
        if (connection.connectionState === "connected")
          setState("Đang phát trực tiếp");
        if (["failed", "disconnected"].includes(connection.connectionState))
          setState("Mất kết nối — kết nối lại để tiếp tục");
      };
      await connection.setLocalDescription(await connection.createOffer());
      if (connection.iceGatheringState !== "complete")
        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            connection.removeEventListener("icegatheringstatechange", changed);
            reject(
              new Error("Không thu thập được kết nối mạng. Vui lòng thử lại."),
            );
          }, 10000);
          const changed = () => {
            if (connection.iceGatheringState === "complete") {
              clearTimeout(timeout);
              connection.removeEventListener(
                "icegatheringstatechange",
                changed,
              );
              resolve();
            }
          };
          connection.addEventListener("icegatheringstatechange", changed);
        });
      if (current !== generation.current) {
        connection.close();
        return;
      }
      const response = await fetch("/api/live/sessions", {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "X-CSRF-Token": auth.csrfToken,
        },
        body: connection.localDescription?.sdp,
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error?.message ?? "Không thể kết nối camera.");
      }
      const location = response.headers.get("location");
      if (!location || !/^\/api\/live\/sessions\/[a-f0-9-]{36}$/.test(location))
        throw new Error("Phản hồi kết nối không hợp lệ.");
      if (current !== generation.current) {
        connection.close();
        await request(location, auth, { method: "DELETE" });
        return;
      }
      resource.current = location;
      await connection.setRemoteDescription({
        type: "answer",
        sdp: await response.text(),
      });
    } catch (cause) {
      if (current === generation.current) {
        setError(messageOf(cause));
        await stop();
      }
    } finally {
      starting.current = false;
    }
  }
  const connected = state === "Đang phát trực tiếp";
  async function fullscreen() {
    const element: FullscreenVideo | null = video.current;
    try {
      if (element?.requestFullscreen && document.fullscreenEnabled) {
        await element.requestFullscreen();
      } else if (element?.webkitEnterFullscreen) {
        element.webkitEnterFullscreen();
      } else {
        throw new Error("Trình duyệt chưa hỗ trợ mở video toàn màn hình.");
      }
    } catch (cause) {
      setError(messageOf(cause));
    }
  }
  return (
    <section aria-labelledby="live-heading">
      <div className="section-heading">
        <div>
          <h1 id="live-heading">Trực tiếp</h1>
          <p className="subtitle">Camera tại nơi làm việc</p>
        </div>
        <span className="status" role="status">
          <i className={connected ? "dot on" : "dot"} />
          {connected ? "Trực tuyến" : state}
        </span>
      </div>
      <div
        className={`video-stage ${active ? "is-active" : ""}${resolution ? " can-pinch" : ""}`}
        onPointerDown={beginTouch}
        onPointerMove={moveTouch}
        onPointerUp={endTouch}
        onPointerCancel={endTouch}
        onPointerLeave={endTouch}
      >
        <video
          ref={video}
          autoPlay
          muted={false}
          playsInline
          data-zoom={zoom}
          onResize={({ currentTarget: { videoWidth, videoHeight } }) => {
            if (videoWidth && videoHeight)
              setResolution(`${videoWidth} × ${videoHeight}`);
          }}
          aria-label="Video trực tiếp camera 01"
        />
        {connected && (
          <div className="video-labels">
            <span>Camera 01</span>
            <span className="live-badge">
              <i className="dot" />
              TRỰC TIẾP
            </span>
          </div>
        )}
        {!active && (
          <div className="video-empty">
            <div className="empty-icon">
              <Icon name="camera" />
            </div>
            <h2>Camera tại nơi làm việc</h2>
            <p>Kết nối để bắt đầu xem trực tiếp.</p>
            <button onClick={() => void start()}>
              <Icon name="play" />
              Kết nối camera
            </button>
          </div>
        )}
        {active && state === "Đang kết nối" && (
          <div className="connecting" aria-hidden="true">
            <span className="spinner" />
            Đang kết nối camera…
          </div>
        )}
        {active && playbackBlocked && (
          <div className="video-empty">
            <p>Trình duyệt cần bạn chạm để phát trực tiếp có tiếng.</p>
            <button onClick={() => void playWithSound()}>
              <Icon name="volume" />
              Phát hình và tiếng
            </button>
          </div>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="player-footer">
        <div>
          <strong>Camera 01</strong>
          <span>{resolution ? `${resolution} · Trực tiếp` : "Trực tiếp"}</span>
        </div>
        <div className="live-quality">
          <span>Chất lượng hình ảnh</span>
          <strong>Nét nhất</strong>
        </div>
        {active && (
          <div
            className="live-zoom"
            role="group"
            aria-label="Thu phóng hình ảnh"
          >
            <button
              className="secondary icon-button"
              type="button"
              aria-label="Thu nhỏ"
              disabled={zoom === 1 || !resolution}
              onClick={() => setZoom((value) => Math.max(1, value - 0.5))}
            >
              −
            </button>
            <button
              className="secondary icon-button"
              type="button"
              aria-label="Phóng to"
              disabled={zoom === 3 || !resolution}
              onClick={() => setZoom((value) => Math.min(3, value + 0.5))}
            >
              +
            </button>
            <button
              className="secondary"
              type="button"
              aria-label="Đặt lại thu phóng"
              disabled={zoom === 1}
              onClick={() => setZoom(1)}
            >
              Đặt lại ({zoom}×)
            </button>
          </div>
        )}
        <div className="actions">
          {active && (
            <>
              <span className="subtitle" aria-live="polite">
                {hasAudio
                  ? playbackBlocked
                    ? "Chờ phát âm thanh"
                    : "Âm thanh đang bật"
                  : "Chưa có âm thanh"}
              </span>
              <button className="secondary" onClick={() => void stop()}>
                <Icon name="stop" />
                Dừng xem
              </button>
              <button className="secondary" onClick={() => void fullscreen()}>
                <Icon name="expand" />
                Toàn màn hình
              </button>
            </>
          )}
          {onPlayback && (
            <button onClick={onPlayback}>
              <Icon name="clock" />
              Xem lại<span className="sr-only"> camera</span>
            </button>
          )}
        </div>
      </div>
      {active && !connected && state !== "Đang kết nối" && (
        <button className="secondary" onClick={() => void start()}>
          <Icon name="refresh" />
          Kết nối lại
        </button>
      )}
    </section>
  );
}
