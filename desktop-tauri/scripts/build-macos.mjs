import { spawn } from "node:child_process";

const args = new Set(process.argv.slice(2));
const cached = args.has("--cached");
const universal = args.has("--universal");

function run(command, commandArgs, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, commandArgs, {
      stdio: "inherit",
      shell: false,
      ...options,
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${commandArgs.join(" ")} exited with code ${code}`));
      }
    });
  });
}

if (process.platform !== "darwin") {
  console.error("[macos-build] macOS app/dmg bundles must be built on a macOS host.");
  console.error("[macos-build] Run this command on the Mac that will produce the .app/.dmg.");
  process.exit(1);
}

const npmCommand = "npm";
const tauriCommand = "tauri";

if (!cached) {
  await run(npmCommand, ["run", "deps:prepare"]);
}

const buildArgs = ["build", "--bundles", "app,dmg"];

if (universal) {
  buildArgs.push("--target", "universal-apple-darwin");
}

if (cached) {
  buildArgs.push("--config", "{\"build\":{\"beforeBuildCommand\":null}}");
}

await run(tauriCommand, buildArgs);
