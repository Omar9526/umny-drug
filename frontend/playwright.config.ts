import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against the running dev servers (backend :8000 in DEV_FALLBACK + demo AI, frontend :3000).
 * Uses the Chrome already installed on the machine (`channel: "chrome"`), so no browser download.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // The local dev stack runs on SQLite (DEV_FALLBACK): parallel workers hit «database is locked».
  workers: process.env.CI ? 2 : 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    channel: "chrome",
    headless: true,
    locale: "ru-RU",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "mobile-chrome", use: { ...devices["Pixel 7"], channel: "chrome", headless: true } }],
});
