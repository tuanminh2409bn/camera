"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type {
  Auth,
  User,
  RecordingStatus,
  LiveSession,
  AuditEvent,
} from "@devone/contracts";
import { request, messageOf } from "./api";
import { Icon } from "./icon";
import { Operations } from "./operations";
type Page<T> = { data: T[]; page: number; total: number; pageSize: number };
const MIN_VIEWER_PASSWORD_LENGTH = 6;
const labels = {
  canLive: "Trực tiếp",
  canPlayback: "Xem lại",
  canDownload: "Tải video",
} as const;
const sessionLabels: Record<string, string> = {
  STARTING: "Đang kết nối",
  ACTIVE: "Đang xem",
  REVOKING: "Đang kết thúc",
};
const actionLabels: Record<string, string> = {
  LOGIN: "Đăng nhập",
  LOGOUT: "Đăng xuất",
  USER_CREATE: "Tạo người xem",
  USER_UPDATE_REVOKE: "Cập nhật tài khoản, thu hồi phiên",
  ADMIN_KICK: "Admin ngắt phiên",
  LIVE_CLOSE: "Dừng xem",
  ADMIN_BOOTSTRAP: "Khởi tạo Admin",
  RECORDING_ENABLE: "Yêu cầu bật ghi",
  RECORDING_DISABLE: "Yêu cầu tắt ghi",
  PLAYBACK_START: "Bắt đầu xem lại",
  DOWNLOAD_START: "Tải đoạn video",
};
export function Admin({ auth }: { auth: Auth }) {
  const [tab, setTab] = useState<"users" | "sessions" | "audit">("users"),
    [users, setUsers] = useState<Page<User> | null>(null),
    [sessions, setSessions] = useState<Page<LiveSession> | null>(null),
    [audit, setAudit] = useState<Page<AuditEvent> | null>(null),
    [page, setPage] = useState(1),
    [recording, setRecording] = useState<RecordingStatus | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [createOpen, setCreateOpen] = useState(false),
    [search, setSearch] = useState(""),
    [loading, setLoading] = useState(true);
  const createButton = useRef<HTMLButtonElement>(null),
    createInput = useRef<HTMLInputElement>(null),
    view = useRef(""),
    returnFocus = useRef(false);
  useEffect(() => {
    if (createOpen) createInput.current?.focus();
  }, [createOpen]);
  useEffect(() => {
    if (!createOpen && !busy && returnFocus.current) {
      createButton.current?.focus();
      returnFocus.current = false;
    }
  }, [createOpen, busy]);
  function closeCreate() {
    returnFocus.current = true;
    setCreateOpen(false);
  }
  async function refresh() {
    const currentView = `${tab}/${page}`;
    try {
      const [rec, list] = await Promise.all([
        request<RecordingStatus>("/api/admin/recording", auth),
        request<Page<User> | Page<LiveSession> | Page<AuditEvent>>(
          `/api/admin/${tab}?page=${page}`,
          auth,
        ),
      ]);
      if (view.current !== currentView) return;
      setRecording(rec);
      if (tab === "users") setUsers(list as Page<User>);
      if (tab === "sessions") setSessions(list as Page<LiveSession>);
      if (tab === "audit") setAudit(list as Page<AuditEvent>);
    } catch (cause) {
      if (view.current === currentView) setError(messageOf(cause));
    } finally {
      if (view.current === currentView) setLoading(false);
    }
  }
  useEffect(() => {
    view.current = `${tab}/${page}`;
    setLoading(true);
    void refresh();
    const timer = setInterval(() => void refresh(), 10000);
    return () => {
      clearInterval(timer);
      view.current = "";
    };
  }, [tab, page, auth.csrfToken]);
  async function action(work: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(success);
      await refresh();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget,
      data = new FormData(form);
    await action(async () => {
      await request("/api/admin/users", auth, {
        method: "POST",
        body: JSON.stringify({
          username: data.get("username"),
          password: data.get("password"),
          canLive: data.has("canLive"),
          canPlayback: data.has("canPlayback"),
          canDownload: data.has("canDownload"),
          maxLiveSessions: Number(data.get("maxLiveSessions")),
        }),
      });
      form.reset();
      closeCreate();
    }, "Đã tạo tài khoản người xem.");
  }
  const list = tab === "users" ? users : tab === "sessions" ? sessions : audit;
  const visibleUsers = users?.data.filter((user) =>
    user.username.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <section aria-labelledby="admin-heading">
      <div className="section-heading">
        <div>
          <h1 id="admin-heading">Quản trị</h1>
          <p className="subtitle">Quản lý quyền truy cập camera</p>
        </div>
        <div className="heading-actions">
          <button
            className="icon-button secondary"
            aria-label="Làm mới"
            title="Làm mới"
            disabled={busy || loading}
            onClick={() => void refresh()}
          >
            <Icon name="refresh" />
          </button>
          <button
            ref={createButton}
            aria-expanded={createOpen}
            aria-controls={createOpen ? "create-viewer" : undefined}
            disabled={busy}
            onClick={() => {
              setTab("users");
              setPage(1);
              setCreateOpen(true);
            }}
          >
            <Icon name="plus" />
            Thêm người xem
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="success">
          {notice}
        </p>
      )}
      <Operations auth={auth} />
      <div className="recording-row">
        <div className="recording-info">
          <Icon name="drive" />
          <div>
            <h2>Ghi hình</h2>
            <p>
              <i
                className={
                  recording?.isOnline &&
                  recording.observed &&
                  !recording.isPaused &&
                  !recording.authLatched
                    ? "dot on"
                    : "dot"
                }
              />
              {!recording
                ? "Đang kiểm tra…"
                : !recording.isOnline
                  ? "NUC mất kết nối"
                  : recording.isPaused
                    ? "Tạm dừng an toàn"
                    : recording.authLatched
                      ? "Khóa xác thực"
                      : recording.observed === null
                        ? "Chưa rõ trạng thái"
                        : recording.observed
                          ? "Đang ghi"
                          : "Đang tắt"}
              <span>· Bản ghi lưu trên NUC</span>
            </p>
            <span className="recording-detail">
              Yêu cầu: {recording ? (recording.desired ? "bật" : "tắt") : "…"}
              {recording?.availableBytes != null
                ? ` · SSD còn ${(recording.availableBytes / 1024 ** 3).toFixed(1)} GiB`
                : ""}
              {recording?.authLatched && recording.isPaused
                ? " · Khóa xác thực"
                : ""}
            </span>
          </div>
        </div>
        <button
          className="secondary"
          disabled={busy || !recording}
          onClick={() =>
            void action(
              () =>
                request("/api/admin/recording", auth, {
                  method: "PUT",
                  body: JSON.stringify({ desired: !recording?.desired }),
                }),
              "Đã lưu yêu cầu ghi hình.",
            )
          }
        >
          {recording?.desired ? "Tắt ghi hình" : "Bật ghi hình"}
        </button>
      </div>
      <div className="subnav segmented" aria-label="Mục quản trị">
        {(["users", "sessions", "audit"] as const).map((t) => (
          <button
            key={t}
            className={tab === t ? "selected" : ""}
            aria-pressed={tab === t}
            disabled={busy}
            onClick={() => {
              setTab(t);
              setPage(1);
              setSearch("");
            }}
          >
            {
              {
                users: "Tài khoản",
                sessions: "Phiên đang xem",
                audit: "Nhật ký",
              }[t]
            }
          </button>
        ))}
      </div>
      {tab === "users" && (
        <>
          {createOpen && (
            <form
              id="create-viewer"
              className="create-user"
              onKeyDown={(e) => {
                if (e.key === "Escape" && !busy) closeCreate();
              }}
              onSubmit={(e) => void create(e)}
            >
              <h2>Tạo người xem</h2>
              <p>
                Cấp đúng quyền cần dùng. Mật khẩu người xem có ít nhất{" "}
                {MIN_VIEWER_PASSWORD_LENGTH} ký tự.
              </p>
              <div className="form-grid">
                <label>
                  Tên đăng nhập
                  <input
                    ref={createInput}
                    name="username"
                    required
                    minLength={3}
                    maxLength={64}
                    pattern="[a-zA-Z0-9._-]+"
                    autoComplete="off"
                  />
                </label>
                <label>
                  Mật khẩu
                  <input
                    name="password"
                    type="password"
                    required
                    minLength={MIN_VIEWER_PASSWORD_LENGTH}
                    maxLength={256}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  Số phiên live tối đa
                  <input
                    name="maxLiveSessions"
                    type="number"
                    min={1}
                    max={10}
                    defaultValue={2}
                    required
                  />
                </label>
              </div>
              <fieldset className="create-permissions">
                <legend>Quyền truy cập</legend>
                {Object.entries(labels).map(([key, label]) => (
                  <label className="checkbox" key={key}>
                    <input
                      type="checkbox"
                      name={key}
                      defaultChecked={key === "canLive"}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              <div className="actions">
                <button disabled={busy}>Tạo tài khoản</button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={closeCreate}
                >
                  Hủy
                </button>
              </div>
            </form>
          )}
          <div className="table-toolbar">
            <label className="search-field">
              <span className="sr-only">Tìm tài khoản trên trang này</span>
              <Icon name="search" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm tài khoản trên trang này"
              />
            </label>
            <span>{visibleUsers?.length ?? 0} tài khoản trên trang</span>
          </div>
          <div className="table-wrap user-table">
            <table>
              <caption className="sr-only">Danh sách tài khoản</caption>
              <thead>
                <tr>
                  <th>Tài khoản</th>
                  {Object.entries(labels).map(([key, label]) => (
                    <th className="permission-heading" key={key}>
                      {label}
                    </th>
                  ))}
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {visibleUsers?.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div>
                        <strong id={`user-${user.id}`}>{user.username}</strong>
                        <small>
                          {user.role === "ADMIN"
                            ? "Quản trị viên"
                            : "Người xem"}
                        </small>
                      </div>
                    </td>
                    {Object.entries(labels).map(([key, label]) => (
                      <td
                        className="permissions-cell"
                        data-label={label}
                        key={key}
                      >
                        {user.role === "ADMIN" ? (
                          <span className="permission-check">
                            <Icon name="check" />
                            <span className="sr-only">Được cấp</span>
                          </span>
                        ) : (
                          <label className="checkbox">
                            <input
                              type="checkbox"
                              aria-describedby={`user-${user.id}`}
                              checked={user[key as keyof typeof labels]}
                              disabled={busy}
                              onChange={(e) =>
                                void action(
                                  () =>
                                    request(
                                      "/api/admin/users/" + user.id,
                                      auth,
                                      {
                                        method: "PATCH",
                                        body: JSON.stringify({
                                          [key]: e.target.checked,
                                        }),
                                      },
                                    ),
                                  "Đã cập nhật quyền và thu hồi phiên cũ.",
                                )
                              }
                            />
                            <span className="sr-only">{label}</span>
                          </label>
                        )}
                      </td>
                    ))}
                    <td data-label="Trạng thái">
                      <span className={user.isActive ? "pill" : "pill muted"}>
                        <i className={user.isActive ? "dot on" : "dot"} />
                        {user.isActive ? "Hoạt động" : "Đã khóa"}
                      </span>
                    </td>
                    <td>
                      {user.role === "VIEWER" && (
                        <div className="user-actions">
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() =>
                              void action(
                                () =>
                                  request("/api/admin/users/" + user.id, auth, {
                                    method: "PATCH",
                                    body: JSON.stringify({
                                      isActive: !user.isActive,
                                    }),
                                  }),
                                "Đã cập nhật tài khoản và thu hồi phiên cũ.",
                              )
                            }
                          >
                            {user.isActive ? "Khóa tài khoản" : "Mở khóa"}
                          </button>
                          <details>
                            <summary>Tùy chọn tài khoản</summary>
                            <div className="user-options">
                              <label>
                                Số phiên live tối đa
                                <input
                                  className="small-input"
                                  aria-label={`Giới hạn live của ${user.username}`}
                                  type="number"
                                  min={1}
                                  max={10}
                                  defaultValue={user.maxLiveSessions}
                                  disabled={busy}
                                  onBlur={(e) => {
                                    const n = Number(e.target.value);
                                    if (
                                      !Number.isInteger(n) ||
                                      n < 1 ||
                                      n > 10
                                    ) {
                                      e.currentTarget.value = String(
                                        user.maxLiveSessions,
                                      );
                                      setError(
                                        "Giới hạn phiên phải là số nguyên từ 1 đến 10.",
                                      );
                                      return;
                                    }
                                    if (n !== user.maxLiveSessions)
                                      void action(
                                        () =>
                                          request(
                                            "/api/admin/users/" + user.id,
                                            auth,
                                            {
                                              method: "PATCH",
                                              body: JSON.stringify({
                                                maxLiveSessions: n,
                                              }),
                                            },
                                          ),
                                        "Đã cập nhật giới hạn.",
                                      );
                                  }}
                                />
                              </label>
                              <form
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  const form = e.currentTarget;
                                  const value = new FormData(form).get(
                                    "password",
                                  );
                                  void action(async () => {
                                    await request(
                                      "/api/admin/users/" + user.id,
                                      auth,
                                      {
                                        method: "PATCH",
                                        body: JSON.stringify({
                                          password: value,
                                        }),
                                      },
                                    );
                                    form.reset();
                                  }, "Đã đổi mật khẩu và thu hồi phiên cũ.");
                                }}
                              >
                                <label>
                                  Mật khẩu mới
                                  <input
                                    name="password"
                                    type="password"
                                    required
                                    minLength={MIN_VIEWER_PASSWORD_LENGTH}
                                    maxLength={256}
                                    autoComplete="new-password"
                                  />
                                </label>
                                <button disabled={busy}>Đổi mật khẩu</button>
                              </form>
                            </div>
                          </details>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && visibleUsers?.length === 0 && (
            <p className="empty">
              {search
                ? "Không có tài khoản phù hợp trên trang này."
                : "Chưa có tài khoản."}
            </p>
          )}
          <p className="table-note">
            Thay đổi quyền, mật khẩu hoặc trạng thái sẽ thu hồi các phiên đang
            mở của tài khoản.
          </p>
        </>
      )}
      {tab === "sessions" && (
        <div className="table-wrap compact-table">
          <table>
            <caption>
              {sessions?.total ?? 0} / 200 phiên live được giữ chỗ
            </caption>
            <thead>
              <tr>
                <th>Người xem</th>
                <th>Trạng thái</th>
                <th>Bắt đầu</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {sessions?.data.map((session) => (
                <tr key={session.id}>
                  <td data-label="Người xem">{session.username}</td>
                  <td data-label="Trạng thái">
                    {sessionLabels[session.state] ?? session.state}
                  </td>
                  <td data-label="Bắt đầu">
                    {new Date(session.createdAt).toLocaleString("vi-VN")}
                  </td>
                  <td>
                    <button
                      className="text-button"
                      disabled={busy || session.state === "REVOKING"}
                      onClick={() =>
                        void action(
                          () =>
                            request("/api/admin/sessions/" + session.id, auth, {
                              method: "DELETE",
                            }),
                          "Đã yêu cầu kết thúc phiên.",
                        )
                      }
                    >
                      Ngắt phiên
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sessions?.total === 0 && (
            <p className="empty">Chưa có người xem trực tiếp.</p>
          )}
        </div>
      )}
      {tab === "audit" && (
        <div className="table-wrap compact-table">
          <table>
            <caption className="sr-only">Nhật ký quản trị</caption>
            <thead>
              <tr>
                <th>Thời điểm</th>
                <th>Hành động</th>
                <th>Người thực hiện</th>
              </tr>
            </thead>
            <tbody>
              {audit?.data.map((item) => (
                <tr key={item.id}>
                  <td data-label="Thời điểm">
                    {new Date(item.createdAt).toLocaleString("vi-VN")}
                  </td>
                  <td data-label="Hành động">
                    {actionLabels[item.action] ?? item.action}
                  </td>
                  <td data-label="Người thực hiện">
                    {item.actorUsername ?? "Hệ thống"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {audit?.total === 0 && <p className="empty">Chưa có sự kiện.</p>}
        </div>
      )}
      {loading && (
        <p className="table-note" role="status">
          Đang tải dữ liệu…
        </p>
      )}
      <div className="pagination">
        <button
          className="secondary"
          disabled={busy || loading || page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Trang trước
        </button>
        <span>
          Trang {page} · {list?.total ?? 0} kết quả
        </span>
        <button
          className="secondary"
          disabled={
            busy || loading || !list || page * list.pageSize >= list.total
          }
          onClick={() => setPage((p) => p + 1)}
        >
          Trang sau
        </button>
      </div>
    </section>
  );
}
