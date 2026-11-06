"use client";
import { useEffect, useRef, useState } from "react";
import type { Auth } from "@devone/contracts";
import { request, messageOf } from "./api";
import { Icon } from "./icon";

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
    generation = useRef(0),
    starting = useRef(false);
  const [state, setState] = useState("Chưa kết nối"),
    [active, setActive] = useState(false),
    [hasAudio, setHasAudio] = useState(false),
    [muted, setMuted] = useState(true),
    [error, setError] = useState("");
  async function stop() {
    generation.current++;
    peer.current?.close();
    peer.current = null;
    const path = resource.current;
    resource.current = null;
    if (path)
      await request<void>(path, auth, { method: "DELETE" }).catch(() => {});
    if (video.current) video.current.srcObject = null;
    setHasAudio(false);
    setMuted(true);
    setActive(false);
    setState("Đã dừng");
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
  async function start() {
    if (starting.current) return;
    starting.current = true;
    const stopGeneration = generation.current + 1;
    await stop();
    if (generation.current !== stopGeneration) {
      starting.current = false;
      return;
    }
    const current = ++generation.current;
    setActive(true);
    setState("Đang kết nối");
    setError("");
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
        incoming.getAudioTracks().some((track) => track.readyState === "live"),
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
        void video.current.play().catch(() => {
          if (current === generation.current) setState("Nhấn phát để xem");
        });
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
    try {
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
        await stop();
        setError(messageOf(cause));
      }
    } finally {
      starting.current = false;
    }
  }
  const connected = state === "Đang phát trực tiếp";
  async function fullscreen() {
    try {
      if (!video.current?.requestFullscreen)
        throw new Error(
          "Trình duyệt chưa hỗ trợ toàn màn hình. Bạn có thể dùng nút trong trình phát video.",
        );
      await video.current.requestFullscreen();
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
      <div className={`video-stage ${active ? "is-active" : ""}`}>
        <video
          ref={video}
          autoPlay
          muted={muted}
          onVolumeChange={(event) => setMuted(event.currentTarget.muted)}
          playsInline
          controls
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
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="player-footer">
        <div>
          <strong>Camera 01</strong>
          <span>720p · Trực tiếp</span>
        </div>
        <div className="actions">
          {active && (
            <>
              <button
                className="secondary"
                disabled={!hasAudio}
                aria-pressed={!muted}
                onClick={() => {
                  if (!video.current) return;
                  video.current.muted = !video.current.muted;
                  setMuted(video.current.muted);
                }}
              >
                <Icon name={muted ? "volume-off" : "volume"} />
                {!hasAudio
                  ? "Chưa có âm thanh"
                  : muted
                    ? "Bật âm thanh"
                    : "Tắt âm thanh"}
              </button>
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
