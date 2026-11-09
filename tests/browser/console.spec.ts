import { test, expect, type Page } from "@playwright/test";
import { TOTP, Secret } from "otpauth";
import { readFile } from "node:fs/promises";
import { operationCodes } from "@devone/contracts";
async function nativeCount() {
  const access = JSON.parse(
    await readFile(".local/browser-tests/native-access.json", "utf8"),
  );
  const response = await fetch(
    "http://127.0.0.1:19997/v3/webrtcsessions/list",
    {
      headers: {
        Authorization:
          "Basic " +
          Buffer.from(access.user + ":" + access.password).toString("base64"),
      },
    },
  );
  expect(response.ok).toBe(true);
  return (await response.json()).itemCount as number;
}
async function login(
  page: Page,
  admin = false,
  credentials?: { username: string; password: string },
) {
  await page.goto("/");
  await page
    .getByLabel("Tên đăng nhập", { exact: true })
    .fill(
      credentials?.username ?? (admin ? "fixture-admin" : "fixture-viewer"),
    );
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill(credentials?.password ?? "Browser-fixture-only-123!");
  if (admin)
    await page.getByLabel("Mã xác thực Admin", { exact: false }).fill(
      new TOTP({
        secret: Secret.fromBase32("JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"),
      }).generate(),
    );
  await page.getByRole("button", { name: "Đăng nhập", exact: false }).click();
  await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      document.documentElement.dataset.cspErrors = `${document.documentElement.dataset.cspErrors ?? ""}${event.violatedDirective};`;
    });
  });
});
test.afterEach(async ({ page }) => {
  expect(
    await page.evaluate(() => document.documentElement.dataset.cspErrors ?? ""),
  ).toBe("");
  await expect(page.locator("body")).not.toContainText(
    /dev[.\s]*one|secure live/i,
  );
});
test("login layout desktop/mobile, CSP and no browser errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const response = await page.goto("/");
  await expect(page.getByRole("heading", { name: "Đăng nhập" })).toBeVisible();
  await expect(page).toHaveTitle("Camera — Giám sát riêng tư");
  await expect(page.locator("body")).not.toContainText(
    /dev[.\s]*one|secure live/i,
  );
  expect(response?.headers()["content-security-policy"]).toContain(
    "'strict-dynamic'",
  );
  const password = page.getByLabel("Mật khẩu", { exact: true });
  await expect(password).toHaveAttribute("type", "password");
  await password.fill("123456");
  await password.press("Tab");
  await expect(
    page.getByRole("button", { name: "Hiện mật khẩu" }),
  ).toBeFocused();
  await page.keyboard.press("Space");
  await expect(password).toHaveAttribute("type", "text");
  await expect(password).toHaveValue("123456");
  await page.getByRole("button", { name: "Ẩn mật khẩu" }).click();
  await expect(password).toHaveAttribute("type", "password");
  await expect(password).toHaveValue("123456");
  await password.clear();
  await page.screenshot({
    path: ".local/browser-tests/login-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 700 });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.screenshot({
    path: ".local/browser-tests/login-mobile.png",
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("live opens with sound and keeps sound on after restarting", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("button", { name: "Kết nối camera", exact: true })
    .click();
  const video = page.getByLabel("Video trực tiếp camera 01", { exact: true });
  await expect
    .poll(() =>
      video.evaluate((element) => {
        if (
          !(element instanceof HTMLVideoElement) ||
          !(element.srcObject instanceof MediaStream)
        )
          return [];
        return element.srcObject
          .getTracks()
          .map((track) => track.kind)
          .sort();
      }),
    )
    .toEqual(["audio", "video"]);
  await expect(video).toHaveJSProperty("muted", false);
  await expect(video).toHaveJSProperty("volume", 1);
  await expect(video).toHaveJSProperty("controls", false);
  await expect(
    page.getByText("Âm thanh đang bật", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Tắt âm thanh", exact: true }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 700 });
  await page.screenshot({
    path: ".local/browser-tests/live-audio-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect.poll(nativeCount).toBe(0);
  await page
    .getByRole("button", { name: "Kết nối camera", exact: true })
    .click();
  await expect(video).toHaveJSProperty("muted", false);
  await expect(
    page.getByText("Âm thanh đang bật", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect.poll(nativeCount).toBe(0);
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
});
test("viewer always receives source quality and can zoom or reset without reopening", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await login(page);
  await expect(page.getByText("Nét nhất", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Chất lượng hình ảnh" }),
  ).toHaveCount(0);
  const sessionRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/live/sessions")
    )
      sessionRequests.push(request.url());
  });
  const start = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/live/sessions") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Kết nối camera", exact: true })
    .click();
  expect((await start).status()).toBe(201);
  const video = page.getByLabel("Video trực tiếp camera 01", { exact: true });
  const zoom = page.getByRole("button", { name: "Phóng to", exact: true });
  const reset = page.getByRole("button", {
    name: "Đặt lại thu phóng",
    exact: true,
  });
  await expect(zoom).toBeEnabled();
  await zoom.click();
  await expect(video).toHaveAttribute("data-zoom", "1.5");
  await expect(video).toHaveCSS("transform", "matrix(1.5, 0, 0, 1.5, 0, 0)");
  await reset.click();
  await expect(video).toHaveCSS("transform", "none");
  const bounds = await video.boundingBox();
  if (!bounds) throw new Error("Video must be visible for pinch gestures");
  const x = Math.round(bounds.x + bounds.width / 2);
  const y = Math.round(bounds.y + bounds.height / 2);
  const touch = await page.context().newCDPSession(page);
  await touch.send("Emulation.setTouchEmulationEnabled", {
    enabled: true,
    maxTouchPoints: 2,
  });
  const points = (offset: number) => [
    { id: 1, x: x - offset, y },
    { id: 2, x: x + offset, y },
  ];
  await touch.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: points(30),
  });
  await touch.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: points(60),
  });
  await expect(video).toHaveAttribute("data-zoom", "2");
  expect(await page.evaluate(() => visualViewport?.scale)).toBe(1);
  await touch.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: points(15),
  });
  await expect(video).toHaveCSS("transform", "none");
  await touch.send("Input.dispatchTouchEvent", {
    type: "touchEnd",
    touchPoints: [],
  });
  await touch.detach();
  expect(await nativeCount()).toBe(1);
  expect(sessionRequests).toEqual(["http://127.0.0.1:3000/api/live/sessions"]);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect.poll(nativeCount).toBe(0);
});
test("blocked sound playback can be started with one tap on the existing session", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      if (
        this.getAttribute("aria-label") === "Video trực tiếp camera 01" &&
        this.srcObject instanceof MediaStream &&
        !this.dataset.allowAudioPlay
      )
        return Promise.reject(
          new DOMException("User gesture required", "NotAllowedError"),
        );
      return play.call(this);
    };
  });
  await login(page);
  await page
    .getByRole("button", { name: "Kết nối camera", exact: true })
    .click();
  const video = page.getByLabel("Video trực tiếp camera 01", { exact: true });
  const play = page.getByRole("button", {
    name: "Phát hình và tiếng",
    exact: true,
  });
  await expect(play).toBeVisible();
  await expect(video).toHaveJSProperty("muted", false);
  await expect.poll(nativeCount).toBe(1);
  await video.evaluate((element) => {
    (element as HTMLVideoElement).dataset.allowAudioPlay = "true";
  });
  await play.click();
  await expect(play).toHaveCount(0);
  await expect(video).toHaveJSProperty("paused", false);
  await expect(video).toHaveJSProperty("muted", false);
  await expect.poll(nativeCount).toBe(1);
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect.poll(nativeCount).toBe(0);
});
test("live uses native video fullscreen when the standard API is unavailable", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(document, "fullscreenEnabled", { value: false });
    Object.defineProperty(Element.prototype, "requestFullscreen", {
      value: undefined,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "webkitEnterFullscreen", {
      value(this: HTMLVideoElement) {
        this.dataset.nativeFullscreen = String(
          navigator.userActivation.isActive,
        );
      },
    });
  });
  await login(page);
  await page.getByRole("button", { name: "Kết nối camera" }).click();
  const video = page.locator("video");
  await expect
    .poll(() => video.evaluate((el: HTMLVideoElement) => el.videoWidth))
    .toBeGreaterThan(0);
  await page
    .getByRole("button", { name: "Toàn màn hình", exact: true })
    .click();
  await expect(video).toHaveAttribute("data-native-fullscreen", "true", {
    timeout: 2000,
  });
  await expect.poll(nativeCount).toBe(1);
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect.poll(nativeCount).toBe(0);
});
test("native H264 WebRTC decodes frames and DELETE closes the native session", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await page.getByRole("button", { name: "Kết nối camera" }).click();
  await expect(page.getByRole("status")).toContainText("Trực tuyến", {
    timeout: 20000,
  });
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate(
          (video: HTMLVideoElement) =>
            video.getVideoPlaybackQuality().totalVideoFrames,
        ),
    )
    .toBeGreaterThan(5);
  await expect.poll(nativeCount).toBe(1);
  await page.screenshot({
    path: ".local/browser-tests/live-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Toàn màn hình", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement?.tagName))
    .toBe("VIDEO");
  await page.evaluate(() => document.exitFullscreen());
  await page.getByRole("button", { name: "Dừng xem", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Đã dừng");
  await expect.poll(nativeCount).toBe(0);
  await page.screenshot({
    path: ".local/browser-tests/apple-white-live-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 700 });
  await page.screenshot({
    path: ".local/browser-tests/apple-white-live-mobile.png",
    fullPage: false,
  });
  await page.route("**/api/recordings", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: { code: "UPSTREAM_OFFLINE", message: "NUC đang ngoại tuyến." },
      },
    }),
  );
  await page.getByRole("button", { name: "Xem lại", exact: true }).click();
  await expect(page.getByRole("region").getByRole("alert")).toHaveText(
    "NUC đang ngoại tuyến.",
  );
  await expect(page.locator("video")).toHaveCount(0);
  await page.unroute("**/api/recordings");
  await page.getByRole("button", { name: "Làm mới", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: /Khoảng ghi/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Tải video", exact: true }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 700 });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.screenshot({
    path: ".local/browser-tests/apple-white-playback-mobile.png",
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "3 phút", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "3 phút", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const timeline = page.getByRole("slider", {
    name: "Mốc bắt đầu trong khoảng ghi",
  });
  await page.getByRole("button", { name: "Tiến 1 phút", exact: true }).click();
  await expect(timeline).toHaveValue("60");
  await timeline.focus();
  await page.keyboard.press("End");
  await expect(timeline).toHaveValue("3599");
  const playbackRequest = page.waitForRequest(
    (req) =>
      req.url().endsWith("/api/playback/sessions") && req.method() === "POST",
  );
  await page.getByRole("button", { name: "Phát đoạn", exact: true }).click();
  const payload = (await playbackRequest).postDataJSON();
  expect(payload).toEqual({
    start: "2026-11-02T00:59:59.000Z",
    duration: 1,
    download: false,
  });
  await expect(page.getByRole("region").getByRole("alert")).toContainText(
    "Không đọc được đoạn video",
  );
  expect(errors).toEqual([]);
  await page.getByRole("button", { name: "Đăng xuất" }).click();
});
test("playback does not seek before a sub-millisecond recording boundary", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/recordings", (route) =>
    route.fulfill({
      json: {
        data: [
          { start: "2026-11-02T00:00:00.000001Z", duration: 120 },
          { start: "2026-11-02T01:00:00.123000000+01:00", duration: 120 },
          { start: "2026-11-02T00:59:59.999999Z", duration: 120 },
        ],
      },
    }),
  );
  await page.getByRole("button", { name: "Xem lại", exact: true }).click();
  const intervals = page.getByRole("combobox", { name: /Khoảng ghi/ });
  await expect(intervals).toBeVisible();
  for (const [index, start] of [
    "2026-11-02T00:00:00.001Z",
    "2026-11-02T00:00:00.123Z",
    "2026-11-02T01:00:00.000Z",
  ].entries()) {
    await intervals.selectOption({ index });
    const playbackRequest = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/playback/sessions") &&
        request.method() === "POST",
    );
    await page.getByRole("button", { name: "Phát đoạn", exact: true }).click();
    expect((await playbackRequest).postDataJSON()).toEqual({
      start,
      duration: 60,
      download: false,
    });
  }
  await page.getByRole("button", { name: "Đăng xuất" }).click();
});
test("admin operational alerts show incidents, recovery and stale state on mobile", async ({
  page,
}) => {
  let mode: "incident" | "recovery" | "stale" | "timeout" = "incident";
  await page.route("**/api/admin/service-status", async (route) => {
    if (mode === "timeout") return; // Keep the request pending until the browser aborts it.
    const date = new Date().toISOString();
    await route.fulfill({
      json: {
        mediaHealthy: true,
        airHealthy: true,
        operations:
          mode === "stale"
            ? { available: false, reason: "stale" }
            : {
                available: true,
                updatedAt: date,
                checks: operationCodes.map((code) => ({
                  code,
                  status:
                    mode === "incident" && code === "AIR" ? "firing" : "ok",
                  since: code === "AIR" ? date : null,
                  value: code === "AIR_DISK" ? 80 * 1024 ** 3 : null,
                })),
                events: [
                  {
                    code: "AIR",
                    at: date,
                    kind: mode === "incident" ? "firing" : "resolved",
                  },
                ],
                traffic: { month: "2026-11", since: date, bytes: 1024 ** 3 },
              },
      },
    });
  });
  await login(page, true, {
    username: "fixture-monitor-admin",
    password: "Browser-fixture-only-123!",
  });
  await page.getByRole("button", { name: "Quản trị", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Tình trạng hệ thống",
    exact: true,
  });
  await expect(panel.getByRole("alert")).toHaveText("1 cảnh báo đang mở");
  await expect(
    panel.getByRole("listitem").filter({ hasText: "Kết nối với NUC" }),
  ).toBeVisible();
  await panel.getByText("Chi tiết 12 kiểm tra", { exact: true }).click();
  await expect(
    panel.getByText("80.0 GiB trống", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: ".local/browser-tests/admin-operations-mobile.png",
    fullPage: true,
  });
  mode = "recovery";
  await page.getByRole("button", { name: "Trực tiếp", exact: true }).click();
  await page.getByRole("button", { name: "Quản trị", exact: true }).click();
  await expect(panel.getByRole("status")).toHaveText(
    "Các kiểm tra hiện tại đều bình thường",
  );
  await panel.getByText("Diễn biến gần đây", { exact: true }).click();
  await expect(panel.getByText(/đã phục hồi/)).toBeVisible();
  mode = "stale";
  await page.getByRole("button", { name: "Trực tiếp", exact: true }).click();
  await page.getByRole("button", { name: "Quản trị", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText(
    "Dữ liệu giám sát đã cũ",
  );
  await expect(
    panel.getByText("Các kiểm tra hiện tại đều bình thường"),
  ).toHaveCount(0);
  mode = "timeout";
  await page.getByRole("button", { name: "Trực tiếp", exact: true }).click();
  await page.getByRole("button", { name: "Quản trị", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText(
    "Không lấy được trạng thái hệ thống",
    { timeout: 10000 },
  );
  await page.getByRole("button", { name: "Đăng xuất", exact: true }).click();
});

test("admin creates viewer, changes rights, disables account and audits mutation", async ({
  page,
  browser,
}) => {
  await login(page, true);
  await page.getByRole("button", { name: "Quản trị", exact: true }).click();
  const addViewer = page.getByRole("button", {
    name: "Thêm người xem",
    exact: true,
  });
  await addViewer.click();
  await expect(page.getByLabel("Tên đăng nhập", { exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(addViewer).toBeFocused();
  await addViewer.click();
  await page
    .getByLabel("Tên đăng nhập", { exact: true })
    .fill("new-browser-viewer");
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill("New-viewer-password-123!");
  await page
    .getByRole("button", { name: "Tạo tài khoản", exact: true })
    .click();
  const row = page
    .getByRole("row")
    .filter({ has: page.getByText("new-browser-viewer", { exact: true }) });
  await expect(row).toBeVisible();
  await row.getByLabel("Xem lại", { exact: true }).click();
  await expect(row.getByLabel("Xem lại", { exact: true })).toBeChecked();
  await row.getByText("Tùy chọn tài khoản", { exact: true }).click();
  const limit = row.getByLabel("Giới hạn live của new-browser-viewer", {
    exact: true,
  });
  await limit.fill("2.5");
  await limit.press("Tab");
  await expect(limit).toHaveValue("2");
  await expect(page.getByRole("region").getByRole("alert")).toHaveText(
    "Giới hạn phiên phải là số nguyên từ 1 đến 10.",
  );
  await limit.fill("3");
  await limit.press("Tab");
  await expect(
    page.getByText("Đã cập nhật giới hạn.", { exact: true }),
  ).toBeVisible();
  await row.getByText("Tùy chọn tài khoản", { exact: true }).click();
  await row
    .getByRole("button", { name: "Khóa tài khoản", exact: true })
    .click();
  await expect(row.getByText("Đã khóa", { exact: true })).toBeVisible();
  await page.screenshot({
    path: ".local/browser-tests/apple-white-admin-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 700 });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.screenshot({
    path: ".local/browser-tests/apple-white-admin-mobile.png",
    fullPage: false,
  });
  expect(await page.locator("header").count()).toBe(1);
  await page.getByRole("table").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: ".local/browser-tests/apple-white-admin-mobile-table.png",
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const search = page.getByLabel("Tìm tài khoản trên trang này");
  await search.fill("no-matching-user");
  await expect(
    page.getByText("Không có tài khoản phù hợp trên trang này."),
  ).toBeVisible();
  await search.fill("new-browser-viewer");
  await expect(row).toBeVisible();
  await expect(page.locator(".user-table tbody tr")).toHaveCount(1);
  await search.fill("");
  await addViewer.click();
  await page.getByLabel("Tên đăng nhập", { exact: true }).fill("playback-only");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("123456");
  const createForm = page.locator("#create-viewer");
  await createForm.getByLabel("Trực tiếp", { exact: true }).uncheck();
  await createForm.getByLabel("Xem lại", { exact: true }).check();
  await page
    .getByRole("button", { name: "Tạo tài khoản", exact: true })
    .click();
  await expect(createForm).toHaveCount(0);
  const playbackContext = await browser.newContext();
  try {
    const playbackPage = await playbackContext.newPage();
    await login(playbackPage, false, {
      username: "playback-only",
      password: "123456",
    });
    await expect(
      playbackPage.getByRole("heading", { name: "Xem lại", exact: true }),
    ).toBeVisible();
    await expect(
      playbackPage.getByRole("button", { name: "Trực tiếp", exact: true }),
    ).toHaveCount(0);
    await expect(
      playbackPage.getByRole("button", { name: "Quản trị", exact: true }),
    ).toHaveCount(0);
    await playbackPage.reload();
    await expect(
      playbackPage.getByRole("heading", { name: "Xem lại", exact: true }),
    ).toBeVisible();
    await expect(playbackPage.locator("body")).not.toContainText(
      /dev[.\s]*one|secure live/i,
    );
    const playbackRow = page.getByRole("row").filter({
      has: page.getByText("playback-only", { exact: true }),
    });
    await playbackRow.getByText("Tùy chọn tài khoản", { exact: true }).click();
    await playbackRow.getByLabel("Mật khẩu mới").fill("654321");
    await playbackRow.getByRole("button", { name: "Đổi mật khẩu" }).click();
    await expect(
      page.getByText("Đã đổi mật khẩu và thu hồi phiên cũ.", { exact: true }),
    ).toBeVisible();
    await playbackPage.reload();
    await expect(
      playbackPage.getByRole("heading", { name: "Đăng nhập" }),
    ).toBeVisible();
    await login(playbackPage, false, {
      username: "playback-only",
      password: "654321",
    });
    await playbackPage.getByRole("button", { name: "Đăng xuất" }).click();
  } finally {
    await playbackContext.close();
  }
  await page.getByRole("button", { name: "Nhật ký", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Hành động Tạo người xem", exact: true }),
  ).toHaveCount(2);
  const viewerContext = await browser.newContext();
  try {
    const viewerPage = await viewerContext.newPage();
    await login(viewerPage);
    await viewerPage.getByRole("button", { name: "Kết nối camera" }).click();
    await expect(viewerPage.getByRole("status")).toContainText("Trực tuyến");
    await expect.poll(nativeCount).toBe(1);
    await page
      .getByRole("button", { name: "Phiên đang xem", exact: true })
      .click();
    const sessionRow = page
      .getByRole("row")
      .filter({
        has: page.getByRole("cell", {
          name: "Người xem fixture-viewer",
          exact: true,
        }),
      })
      .filter({
        has: page.getByRole("cell", {
          name: "Trạng thái Đang xem",
          exact: true,
        }),
      });
    await sessionRow
      .getByRole("button", { name: "Ngắt phiên", exact: true })
      .click();
    await expect.poll(nativeCount).toBe(0);
  } finally {
    await viewerContext.close();
  }
});
