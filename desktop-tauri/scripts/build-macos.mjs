import { createHash } from "node:crypto";
import { spawn, execFileSync } from "node:child_process";
import { createReadStream } from "node:fs";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tauriRoot = join(projectRoot, "src-tauri");
const args = new Set(process.argv.slice(2));
const cached = args.has("--cached");
const universal = args.has("--universal");

function run(command, commandArgs, options = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, commandArgs, {
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
        reject(new Error(`${command} ${commandArgs.join(" ")} exited with code ${code}`));
      }
    });
  });
}

function readDeveloperIdIdentity() {
  try {
    const output = execFileSync("security", ["find-identity", "-v", "-p", "codesigning"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return output.match(/^\s*\d+\)\s*([A-F0-9]{40})\s+"Developer ID Application:/m)?.[1] ?? null;
  } catch {
    return null;
  }
}

function sha256(path) {
  return new Promise((resolveHash, reject) => {
    const hash = createHash("sha256");
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolveHash(hash.digest("hex")));
  });
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

if (process.platform !== "darwin") {
  console.error("[macos-build] macOS app/dmg bundles must be built on a macOS host.");
  process.exit(1);
}

const appConfig = JSON.parse(await readFile(join(tauriRoot, "tauri.conf.json"), "utf8"));
const productName = appConfig.productName;
const version = appConfig.version;
const targetName = universal ? "universal" : process.arch === "arm64" ? "arm64" : "x64";
const signingIdentity = process.env.APPLE_SIGNING_IDENTITY || readDeveloperIdIdentity() || "-";
const signingMode = signingIdentity === "-" ? "ad-hoc" : "Developer ID Application";
const cacheRoot = process.env.CAP_S_BUILD_CACHE || join(tmpdir(), "cap-s-packaging");
const cargoTargetDir = resolve(process.env.CARGO_TARGET_DIR || join(cacheRoot, "target-macos"));
const targetBuildDir = universal
  ? join(cargoTargetDir, "universal-apple-darwin", "release")
  : join(cargoTargetDir, "release");
const bundleDir = join(targetBuildDir, "bundle");
const releaseDir = resolve(projectRoot, "..", "releases", version, "macos");
const bundleConfigPath = join(tauriRoot, "tauri.macos.conf.json");
const tempConfigDir = await mkdtemp(join(tmpdir(), "cap-s-tauri-macos-"));
const tempConfigPath = join(tempConfigDir, "tauri-macos-build.conf.json");

await mkdir(cargoTargetDir, { recursive: true });
const buildEnvironment = { ...process.env, CARGO_TARGET_DIR: cargoTargetDir };

if (!cached) {
  await run("npm", ["run", "deps:prepare"], { env: buildEnvironment });
}

const macConfig = JSON.parse(await readFile(bundleConfigPath, "utf8"));
macConfig.bundle ??= {};
macConfig.bundle.macOS ??= {};
macConfig.bundle.macOS.signingIdentity = signingIdentity;
if (cached) {
  macConfig.build ??= {};
  macConfig.build.beforeBuildCommand = null;
}
await writeFile(tempConfigPath, `${JSON.stringify(macConfig, null, 2)}\n`);

const buildArgs = ["build", "--bundles", "app,dmg", "--config", tempConfigPath, "--ci"];
if (universal) {
  buildArgs.push("--target", "universal-apple-darwin");
}

console.log(`[macos-build] target: ${targetName}`);
console.log(`[macos-build] signing mode: ${signingMode}`);
console.log(`[macos-build] CARGO_TARGET_DIR: ${cargoTargetDir}`);

try {
  await run("tauri", buildArgs, { env: buildEnvironment });

  const builtApp = join(bundleDir, "macos", `${productName}.app`);
  if (!(await exists(builtApp))) {
    throw new Error(`Tauri build completed but app bundle is missing: ${builtApp}`);
  }

  const dmgDir = join(bundleDir, "dmg");
  const dmgCandidates = (await readdir(dmgDir))
    .filter((name) => name.endsWith(".dmg") && name.startsWith(productName))
    .map((name) => join(dmgDir, name));
  if (dmgCandidates.length !== 1) {
    throw new Error(`Expected one ${productName} DMG under ${dmgDir}; found ${dmgCandidates.length}.`);
  }

  const builtDmg = dmgCandidates[0];
  const appZipName = `${productName}_${version}_${targetName}.app.zip`;
  const appZip = join(releaseDir, appZipName);
  // File Provider folders can add FinderInfo attributes that invalidate app signatures.
  const stagedApp = join(tempConfigDir, `${productName}.app`);
  const stagedDmg = join(releaseDir, basename(builtDmg));

  await mkdir(releaseDir, { recursive: true });
  await rm(join(releaseDir, `${productName}.app`), { recursive: true, force: true });
  await rm(stagedApp, { recursive: true, force: true });
  await rm(appZip, { force: true });
  await rm(stagedDmg, { force: true });
  await rm(join(releaseDir, "SHA256SUMS.txt"), { force: true });

  await run("ditto", ["--norsrc", "--noextattr", builtApp, stagedApp], { env: buildEnvironment });
  for (const attribute of ["com.apple.FinderInfo", "com.apple.ResourceFork"]) {
    await run("xattr", ["-dr", attribute, stagedApp], { env: buildEnvironment });
  }
  await run("codesign", ["--verify", "--deep", "--strict", stagedApp], { env: buildEnvironment });
  await run("ditto", ["-c", "-k", "--norsrc", "--noextattr", "--keepParent", builtApp, appZip], {
    env: buildEnvironment,
  });
  await run("ditto", [builtDmg, stagedDmg], { env: buildEnvironment });

  const appHash = await sha256(appZip);
  const dmgHash = await sha256(stagedDmg);
  const checksums = `${appHash}  ${appZipName}\n${dmgHash}  ${basename(stagedDmg)}\n`;
  await writeFile(join(releaseDir, "SHA256SUMS.txt"), checksums, "utf8");

  const minimumVersion = macConfig.bundle.macOS.minimumSystemVersion;
  const architectureText = universal ? "Apple Silicon 與 Intel（Universal 2）" : targetName === "arm64" ? "Apple Silicon" : "Intel";
  const signatureText = signingMode === "ad-hoc"
    ? "本版採 ad-hoc 簽名，未使用 Developer ID，也未經 Apple notarization。Gatekeeper 在其他 Mac 上可能拒絕開啟。要廣泛提供下載，需使用 Developer ID 簽名並完成 notarization。"
    : "本版使用現有 Developer ID 簽名，但未經 Apple notarization；Gatekeeper 在其他 Mac 上仍可能顯示安全提示。要廣泛提供下載，需完成 notarization。";
  const readme = [
    `${productName} ${version}｜macOS 安裝說明`,
    "",
    `架構：${architectureText}`,
    `最低版本：Intel Mac 需要 macOS ${minimumVersion} Catalina 或更新版本；Apple Silicon 需要 macOS 11 Big Sur 或更新版本。`,
    "本程式已包含前端、Plotly 與分析執行檔，使用者不需要安裝 Python、Node.js 或 Rust。",
    "",
    "安裝方式",
    `1. 開啟「${basename(stagedDmg)}」。`,
    `2. 將「${productName}.app」拖到 Applications 資料夾。`,
    "3. 從 Applications 啟動程式。",
    "也可以解壓縮 .app.zip，將解出的 App 拖到 Applications。",
    "",
    "安全性與簽名",
    signatureText,
    "此發行包不包含實驗資料；請在程式內選取自己的資料夾。",
    "每個直接子資料夾是一組實驗，Excel 檔需包含 pF - Plot 0 欄位。",
    "",
    "完整性檢查",
    "請以 SHA256SUMS.txt 中的 SHA-256 值核對下載的 DMG 或 .app.zip。",
  ].join("\n");
  await writeFile(join(releaseDir, "README.txt"), `${readme}\n`, "utf8");

  console.log(`[macos-build] app included in DMG and app archive`);
  console.log(`[macos-build] staged DMG: ${stagedDmg}`);
  console.log(`[macos-build] staged app archive: ${appZip}`);
  console.log(`[macos-build] checksums: ${join(releaseDir, "SHA256SUMS.txt")}`);
} finally {
  await rm(tempConfigDir, { recursive: true, force: true });
}
