import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "chrome",
    headless: true,
    launchOptions: { args: ["--disable-gpu"] },
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node --import tsx tests/browser/server.ts",
      url: "http://127.0.0.1:3001/api/health",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
      timeout: 30000,
    },
    {
      command:
        "node node_modules/next/dist/bin/next start apps/web --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 10000 },
      timeout: 30000,
    },
  ],
});
