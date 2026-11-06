"use client";
import { useEffect, useState, type FormEvent } from "react";
import type { Auth } from "@devone/contracts";
import { request, messageOf, RequestError } from "./api";
import { Live } from "./live";
import { Playback } from "./playback";
import { Admin } from "./admin";
import { Icon } from "./icon";

type Tab = "live" | "playback" | "admin" | "none";
const firstTab = ({ user }: Auth): Tab =>
  user.canLive
    ? "live"
    : user.canPlayback || user.canDownload
      ? "playback"
      : user.role === "ADMIN"
        ? "admin"
        : "none";

export function Console() {
  const [auth, setAuth] = useState<Auth | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [tab, setTab] = useState<Tab>("live");
  useEffect(() => {
    void request<Auth>("/api/auth/session")
      .then((value) => {
        setAuth(value);
        setTab(firstTab(value));
      })
      .catch((cause) => {
        if (!(cause instanceof RequestError && cause.status === 401))
          setError(messageOf(cause));
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!auth) return;
    const timer = setInterval(() => {
      void request<Auth>("/api/auth/session")
        .then((value) =>
          setAuth((current) =>
            current?.csrfToken === value.csrfToken ? current : value,
          ),
        )
        .catch((cause) => {
          if (cause instanceof RequestError && cause.status === 401) {
            setAuth(null);
            setError(
              "Phiên đã hết hạn hoặc quyền truy cập đã thay đổi. Vui lòng đăng nhập lại.",
            );
          }
        });
    }, 15000);
    return () => clearInterval(timer);
  }, [auth?.csrfToken]);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const otp = String(form.get("otp") ?? "");
      const result = await request<Auth>("/api/auth/login", null, {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
          ...(otp ? { otp } : {}),
        }),
      });
      setAuth(result);
      setTab(firstTab(result));
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    if (!auth || busy) return;
    setBusy(true);
    try {
      await request("/api/auth/logout", auth, { method: "POST" });
      setAuth(null);
      setError("");
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <main className="loading" role="status">
        <Icon name="camera" />
        Đang mở camera…
      </main>
    );
  if (!auth)
    return (
      <main className="login-page">
        <div className="login-story">
          <a className="brand" href="/">
            Camera<span>Không gian riêng tư</span>
          </a>
          <div className="login-intro">
            <div className="intro-icon">
              <Icon name="camera" />
            </div>
            <h1>
              An tâm quan sát.
              <br />
              Dễ dàng kiểm soát.
            </h1>
            <p>
              Xem trực tiếp, tìm lại khoảnh khắc và quản lý quyền truy cập trong
              một không gian.
            </p>
          </div>
          <p className="login-note">
            <Icon name="shield" />
            Chỉ dành cho người dùng được cấp quyền
          </p>
        </div>
        <div className="login-panel">
          <form onSubmit={(e) => void login(e)}>
            <div className="login-title">
              <div className="login-lock">
                <Icon name="lock" />
              </div>
              <h2>Đăng nhập</h2>
              <p className="muted">Sử dụng tài khoản do quản trị viên cấp.</p>
            </div>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <label>
              Tên đăng nhập
              <input
                name="username"
                autoComplete="username"
                required
                autoFocus
                minLength={3}
                maxLength={64}
              />
            </label>
            <label>
              Mật khẩu
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={256}
              />
            </label>
            <label>
              Mã xác thực Admin{" "}
              <span className="label-hint">
                Chỉ nhập nếu tài khoản yêu cầu xác thực hai bước.
              </span>
              <input
                name="otp"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                placeholder="6 chữ số · không bắt buộc với người xem"
              />
            </label>
            <button className="full" disabled={busy}>
              {busy ? "Đang xác thực…" : "Đăng nhập"}
              <Icon name="arrow" />
            </button>
            <p className="login-help">
              Cần cấp quyền hoặc quên mật khẩu?
              <br />
              Liên hệ quản trị viên hệ thống.
            </p>
          </form>
        </div>
      </main>
    );
  const navigation = [
    {
      id: "live" as const,
      label: "Trực tiếp",
      icon: "camera",
      allowed: auth.user.canLive,
    },
    {
      id: "playback" as const,
      label: "Xem lại",
      icon: "clock",
      allowed: auth.user.canPlayback || auth.user.canDownload,
    },
    {
      id: "admin" as const,
      label: "Quản trị",
      icon: "shield",
      allowed: auth.user.role === "ADMIN",
    },
  ];
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Đến nội dung chính
      </a>
      <aside className="sidebar">
        <a className="brand desktop-brand" href="/">
          Camera<span>Không gian riêng tư</span>
        </a>
        <nav aria-label="Điều hướng chính">
          {navigation
            .filter((item) => item.allowed)
            .map((item) => (
              <button
                key={item.id}
                className={tab === item.id ? "nav-active" : ""}
                aria-current={tab === item.id ? "page" : undefined}
                onClick={() => setTab(item.id)}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </button>
            ))}
        </nav>
        <div className="sidebar-account">
          <div className="account-info">
            <div className="avatar">
              <Icon name="user" />
            </div>
            <div>
              <strong>{auth.user.username}</strong>
              <span>
                {auth.user.role === "ADMIN" ? "Quản trị viên" : "Người xem"}
              </span>
            </div>
          </div>
          <button
            className="logout-button"
            disabled={busy}
            onClick={() => void logout()}
          >
            <Icon name="logout" />
            Đăng xuất
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="mobile-header">
          <a className="brand" href="/">
            Camera
          </a>
          <div className="mobile-account">
            <span title={auth.user.username}>{auth.user.username}</span>
            <button
              className="icon-button secondary"
              title="Đăng xuất"
              aria-label="Đăng xuất"
              disabled={busy}
              onClick={() => void logout()}
            >
              <Icon name="logout" />
            </button>
          </div>
        </header>
        <main className="content" id="main-content" tabIndex={-1}>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {tab === "live" && auth.user.canLive ? (
            <Live
              auth={auth}
              onPlayback={
                auth.user.canPlayback || auth.user.canDownload
                  ? () => setTab("playback")
                  : undefined
              }
            />
          ) : tab === "playback" &&
            (auth.user.canPlayback || auth.user.canDownload) ? (
            <Playback auth={auth} />
          ) : tab === "admin" && auth.user.role === "ADMIN" ? (
            <Admin auth={auth} />
          ) : (
            <div className="empty">
              <Icon name="shield" />
              <h2>Chưa có quyền xem camera</h2>
              <p>Liên hệ quản trị viên để được cấp quyền truy cập.</p>
            </div>
          )}
          <footer>
            <span>Camera tại nơi làm việc</span>
            <span>
              <Icon name="shield" />
              Truy cập được phân quyền
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
