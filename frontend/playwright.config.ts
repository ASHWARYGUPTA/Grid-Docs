import { defineConfig } from "@playwright/test";

// Runs against a production build — Turbopack dev mode's HMR websocket can
// interfere with hydration in constrained/sandboxed environments, so E2E
// always targets `next build && next start`, never `next dev`.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
});
