import { execSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

export default function globalSetup() {
  const dataDir = path.resolve(__dirname, "../.e2e-data");
  rmSync(dataDir, { recursive: true, force: true });
  execSync("uv run python -m intel.seed tests/fixtures/netchex_snapshot.json", {
    cwd: path.resolve(__dirname, "../../intel"),
    env: { ...process.env, DATA_DIR: dataDir },
    stdio: "inherit",
  });
}
