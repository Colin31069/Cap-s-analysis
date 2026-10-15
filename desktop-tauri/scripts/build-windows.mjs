import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { access, copyFile, mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { constants, createReadStream, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(projectRoot, "..");
const target = "x86_64-pc-windows-msvc";
const packageJson = JSON.parse(await readFile(join(projectRoot, "package.json"), "utf8"));
const windowsConfig = JSON.parse(await readFile(join(projectRoot, "src-tauri", "tauri.windows.conf.json"), "utf8"));
const tauriConfig = JSON.parse(await readFile(join(projectRoot, "src-tauri", "tauri.conf.json"), "utf8"));
const cached = process.argv.slice(2).includes("--cached");
const version = packageJson.version;
const packagingRoot = process.env.CAP_S_PACKAGING_ROOT ?? join(tmpdir(), "cap-s-packaging");
const targetDir = process.env.CARGO_TARGET_DIR ?? join(packagingRoot, "target-windows");
const xwinCache = process.env.XWIN_CACHE_DIR ?? join(packagingRoot, "xwin");
const outputDir = join(repositoryRoot, "releases", version, "windows");
const tauriEntry = join(projectRoot, "node_modules", "@tauri-apps", "cli", "tauri.js");
const minimumOfflineInstallerBytes = 100 * 1024 * 1024;

function run(command, args, options = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      stdio: "inherit",
      shell: false,
      ...options,
    });
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

async function requireExecutable(command, args, installHint) {
  try {
    await run(command, args, { stdio: "ignore" });
  } catch {
    throw new Error(`${command} is required. ${installHint}`);
  }
}

function assertWindowsX64Pe(path, label) {
  const bytes = readFileSync(path);
  if (bytes.length < 0x40 || bytes.toString("ascii", 0, 2) !== "MZ") {
    throw new Error(`${label} is not a Windows PE executable: ${path}`);
  }

  const peOffset = bytes.readUInt32LE(0x3c);
  if (peOffset + 6 > bytes.length || bytes.toString("ascii", peOffset, peOffset + 4) !== "PE\0\0") {
    throw new Error(`${label} has an invalid PE header: ${path}`);
  }

  const machine = bytes.readUInt16LE(peOffset + 4);
  if (machine !== 0x8664) {
    throw new Error(`${label} must target Windows x64; found PE machine 0x${machine.toString(16)}.`);
  }
}

function sha256File(path) {
  return new Promise((resolveHash, reject) => {
    const hash = createHash("sha256");
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolveHash(hash.digest("hex")));
  });
}

if (!new Set(["darwin", "win32"]).has(process.platform)) {
  throw new Error("Windows packaging must run on macOS (cross-build) or Windows (native build).");
}
if (version !== tauriConfig.version) {
  throw new Error(`package.json version (${version}) and tauri.conf.json version (${tauriConfig.version}) must match.`);
}

await access(tauriEntry, constants.R_OK).catch(() => {
  throw new Error("Tauri CLI is missing. Run `npm ci` in desktop-tauri first.");
});

await requireExecutable("rustup", ["--version"], "Install Rust using rustup first.");
if (process.platform === "darwin") {
  await requireExecutable("cargo-xwin", ["--version"], "Install cargo-xwin into the task-local Cargo bin directory.");
  await requireExecutable("llvm-rc", ["/?"], "Add LLVM's bin directory to PATH (llvm-rc is required for the Windows app icon).");
  await requireExecutable("lld-link", ["--version"], "Add LLVM's bin directory to PATH (lld-link is required for MSVC cross-linking).");
  await requireExecutable("makensis", ["-VERSION"], "Install NSIS and add makensis to PATH.");
}

const installedTargets = await new Promise((resolveTarget, reject) => {
  const child = spawn("rustup", ["target", "list", "--installed"], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "inherit"],
    shell: false,
  });
  let stdout = "";
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => (stdout += chunk));
  child.on("error", reject);
  child.on("exit", (code) => (code === 0 ? resolveTarget(stdout) : reject(new Error("rustup target query failed"))));
});
if (!installedTargets.split(/\s+/).includes(target)) {
  throw new Error(`Rust target ${target} is not installed. Run: rustup target add ${target}`);
}
if (cached) {
  await access(join(projectRoot, "dist", "index.html")).catch(() => {
    throw new Error("--cached requires an existing frontend build. Run `npm run build` first.");
  });
  windowsConfig.build = { beforeBuildCommand: null };
}

await mkdir(targetDir, { recursive: true });
await mkdir(xwinCache, { recursive: true });

console.log(
  `[windows-build] Building ${process.platform === "darwin" ? "cross-compiled" : "native"} unsigned Windows x64 NSIS installer with offline WebView2 runtime (${version})...`,
);
const tauriArgs = ["build", "--bundles", "nsis", "--target", target];
if (process.platform === "darwin") tauriArgs.push("--runner", "cargo-xwin");
tauriArgs.push("--config", JSON.stringify(windowsConfig));
await run(process.execPath, [tauriEntry, ...tauriArgs], {
  env: {
    ...process.env,
    CARGO_TARGET_DIR: targetDir,
    ...(process.platform === "darwin" ? { XWIN_CACHE_DIR: xwinCache } : {}),
  },
});

const targetRelease = join(targetDir, target, "release");
const appBinary = join(targetRelease, "skin-analysis-desktop.exe");
const bundleDir = join(targetRelease, "bundle", "nsis");
const bundleNames = await readdir(bundleDir);
const installerNames = bundleNames.filter((name) => name.toLowerCase().endsWith(".exe"));
if (installerNames.length !== 1) {
  throw new Error(`Expected one NSIS installer in ${bundleDir}, found ${installerNames.length}.`);
}

assertWindowsX64Pe(appBinary, "Application executable");
const nsisScriptPath = join(targetRelease, "nsis", "x64", "installer.nsi");
const nsisScript = (await readFile(nsisScriptPath, "utf8").catch(() => {
  throw new Error(`Tauri did not leave the generated NSIS script at ${nsisScriptPath}.`);
})).replace(/\r\n/g, "\n");
if (!/^!define INSTALLWEBVIEW2MODE "offlineInstaller"$/m.test(nsisScript)) {
  throw new Error("Generated NSIS script does not select the offline WebView2 installer.");
}
const webviewPath = nsisScript.match(/^!define WEBVIEW2INSTALLERPATH "(.+)"$/m)?.[1];
if (!webviewPath) throw new Error("Generated NSIS script has no embedded WebView2 installer path.");
const webviewStat = await stat(webviewPath).catch(() => {
  throw new Error(`The WebView2 offline installer referenced by NSIS is missing: ${webviewPath}`);
});
if (webviewStat.size < minimumOfflineInstallerBytes) {
  throw new Error(`The referenced WebView2 offline installer is only ${(webviewStat.size / (1024 * 1024)).toFixed(1)} MiB.`);
}

const installerPath = join(bundleDir, installerNames[0]);
const installerStat = await stat(installerPath);
if (!/File[^\n]*\$\{WEBVIEW2INSTALLERPATH\}/.test(nsisScript)) {
  throw new Error("Generated NSIS script does not embed the referenced WebView2 offline payload.");
}
if (installerStat.size < minimumOfflineInstallerBytes) {
  throw new Error("NSIS installer is too small to contain the WebView2 offline payload.");
}

await mkdir(outputDir, { recursive: true });
const releaseInstallerName = `Skin Analysis Desktop_${version}_x64-setup.exe`;
const releaseInstaller = join(outputDir, releaseInstallerName);
await copyFile(installerPath, releaseInstaller);

const checksum = await sha256File(releaseInstaller);
await writeFile(join(outputDir, "SHA256SUMS.txt"), `${checksum}  ${releaseInstallerName}\n`, "utf8");
await writeFile(
  join(outputDir, "README.txt"),
  [
    "Skin Analysis Desktop for Windows x64",
    "",
    "安裝方式：雙擊 Skin Analysis Desktop_" + version + "_x64-setup.exe，依畫面指示完成安裝。",
    "此安裝程式已包含 WebView2 離線安裝程式；一般使用不需要另外安裝 Python、Node.js、Rust 或 WebView2。",
    "支援 Windows 10/11 x64。",
    "啟動後選取自己的實驗根目錄；每個直接子資料夾是一組實驗，Excel 檔需包含 pF - Plot 0 欄位。",
    "此安裝包不包含實驗資料。",
    "本版尚未配置公開發行憑證，Windows 可能顯示 SmartScreen 發行者提示。",
    process.platform === "darwin"
      ? "在 macOS 上跨平台編譯；尚未於 Windows 實機驗證安裝與執行。"
      : "在 Windows 上原生編譯；發行前請確認安裝與主要操作流程。",
    "SHA-256 請查看 SHA256SUMS.txt。",
    "",
  ].join("\n"),
  "utf8",
);

console.log(`[windows-build] Verified application architecture: x86_64-pc-windows-msvc`);
console.log(`[windows-build] Verified NSIS offline WebView2 payload: ${(webviewStat.size / (1024 * 1024)).toFixed(1)} MiB`);
console.log(`[windows-build] Installer size: ${(installerStat.size / (1024 * 1024)).toFixed(1)} MiB`);
console.log(`[windows-build] Wrote ${releaseInstaller}`);
console.log(`[windows-build] SHA-256 ${checksum}`);
