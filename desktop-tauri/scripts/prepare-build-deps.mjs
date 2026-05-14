import { execFileSync, spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tauriRoot = resolve(projectRoot, "src-tauri");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const cargoCommand = process.platform === "win32" ? "cargo.exe" : "cargo";
const rustcCommand = process.platform === "win32" ? "rustc.exe" : "rustc";

function run(command, args, cwd) {
  return new Promise((resolveRun, reject) => {
    const child =
      process.platform === "win32" && command.endsWith(".cmd")
        ? spawn("cmd.exe", ["/d", "/s", "/c", [command, ...args].join(" ")], {
            cwd,
            stdio: "inherit",
            shell: false,
          })
        : spawn(command, args, { cwd, stdio: "inherit", shell: false });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolveRun();
      } else {
        reject(new Error(`${command} ${args.join(" ")} exited with code ${code}`));
      }
    });
  });
}

function rustHostTarget() {
  try {
    const output = execFileSync(rustcCommand, ["-vV"], { encoding: "utf8" });
    return output.match(/^host:\s*(.+)$/m)?.[1]?.trim() ?? null;
  } catch {
    return null;
  }
}

console.log("[deps] Installing npm packages from package-lock.json/cache...");
await run(npmCommand, ["install", "--prefer-offline", "--no-audit", "--fund=false"], projectRoot);

console.log("[deps] Syncing frontend vendor assets...");
await run(process.execPath, ["scripts/sync-plotly-vendor.mjs"], projectRoot);

console.log("[deps] Fetching Cargo crates into the local Cargo cache...");
await run(cargoCommand, ["fetch", "--locked"], tauriRoot);

const hostTarget = rustHostTarget();
if (hostTarget) {
  console.log(`[deps] Fetching Cargo crates for ${hostTarget}...`);
  await run(cargoCommand, ["fetch", "--locked", "--target", hostTarget], tauriRoot);
}

console.log("[deps] Build dependencies are available locally.");
