import { defineConfig } from "@playwright/test";
import path from "node:path";

const DATA_DIR = path.resolve(__dirname, ".e2e-data");

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/global-setup.ts",
  use: { baseURL: "http://localhost:3100" },
  webServer: [
    {
      command: "uv run uvicorn intel.api:app --port 8100",
      cwd: path.resolve(__dirname, "../intel"),
      url: "http://127.0.0.1:8100/health",
      env: { DATA_DIR, RUN_MODE: "inline" },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://localhost:3100",
      env: { INTEL_URL: "http://127.0.0.1:8100" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
