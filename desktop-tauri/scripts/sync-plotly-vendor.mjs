import { createRequire } from "node:module";
import { copyFile, mkdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const packageJsonPath = require.resolve("plotly.js-dist-min/package.json");
const sourcePath = join(dirname(packageJsonPath), "plotly.min.js");
const targetPath = fileURLToPath(new URL("../public/vendor/plotly.min.js", import.meta.url));

async function shouldCopy() {
  try {
    const [sourceInfo, targetInfo] = await Promise.all([stat(sourcePath), stat(targetPath)]);
    return sourceInfo.size !== targetInfo.size || sourceInfo.mtimeMs > targetInfo.mtimeMs;
  } catch {
    return true;
  }
}

await mkdir(dirname(targetPath), { recursive: true });

if (await shouldCopy()) {
  await copyFile(sourcePath, targetPath);
  console.log("[vendor] synced Plotly to public/vendor/plotly.min.js");
} else {
  console.log("[vendor] Plotly asset is up to date");
}
