<script lang="ts">
  import { onMount } from "svelte";
  import { open } from "@tauri-apps/plugin-dialog";
  import { writeFile, writeTextFile } from "@tauri-apps/plugin-fs";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import Plotly from "plotly.js-dist-min";

  import {
    buildPlotPayload,
    chooseCsvExportPath,
    chooseExportPath,
    listExperimentFolders,
    listSamplesInFolder,
    runStatistics,
    saveMetadata,
  } from "./lib/api";
  import { buildPlotlyFigure, COLOR_PALETTE, dataUrlToBytes, emptyFigure } from "./lib/plot";
  import type { AppTheme } from "./lib/plot";
  import type {
    AppError,
    DisplayMode,
    ExperimentMetadata,
    LegendStyle,
    ListSamplesResponse,
    PlotRequest,
    PlotResponse,
    SampleInfo,
    StatisticsRequest,
  } from "./lib/types";

  const DEFAULT_ROOT_PATH = "/Users/k/Downloads/20260303";
  const THEME_PREFERENCE_KEY = "skin-analysis.theme-preference";
  type ThemePreference = "light" | "dark" | "system";

  // ── Path & folder selection ──────────────────────────────────────────────────
  let rootPath = DEFAULT_ROOT_PATH;
  let experimentName = "";
  let experimentOptions: string[] = [];

  // ── Display options ──────────────────────────────────────────────────────────
  let displayMode: DisplayMode = "Norm";
  let overlay = false;
  let useGroupColor = true;
  let showDropLines = true;
  let legendStyle: LegendStyle = "Detailed";
  let showGroup = true;
  let showBase = true;
  let showDelta = false;
  let customTitle = "";

  // ── Timing parameters ────────────────────────────────────────────────────────
  let showTimingPanel = false;
  let baselineDurationSec = 20.0;
  let drugApplyTimeSec = 25.0;
  let drugApplyToleranceSec = 5.0;
  let baselineWarningThresholdPct = 2.0;

  // ── Medicine metadata ────────────────────────────────────────────────────────
  let showMedicinePanel = false;
  let currentMetadata: ExperimentMetadata = {
    medicineCount: 1,
    medicines: [{ name: "", dose: "" }],
    excludedSamples: [],
  };

  // ── Sample exclusion list ────────────────────────────────────────────────────
  let sampleListResponse: ListSamplesResponse | null = null;

  // ── Statistics ───────────────────────────────────────────────────────────────
  let showStatsPanel = false;
  let statsText = "";
  let statsCsv = "";
  let busyStats = false;

  // ── Plot state ───────────────────────────────────────────────────────────────
  let busy = false;
  let statusMessage = "Ready";
  let statusTone: "neutral" | "error" | "warning" = "neutral";
  let payloads: PlotResponse[] = [];
  let overlayColorIndex = 0;
  let plotHost: HTMLDivElement;

  // Theme
  let themePreference: ThemePreference | null = null;
  let activeTheme: AppTheme = "light";
  let showThemePrompt = false;
  let systemThemeQuery: MediaQueryList | null = null;

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function selectOrFirst(current: string, options: string[]): string {
    if (options.length === 0) return "";
    return options.includes(current) ? current : options[0];
  }

  function folderPath(): string {
    if (!rootPath || !experimentName) return "";
    return [rootPath, experimentName].join("/");
  }

  function resolveTheme(preference: ThemePreference): AppTheme {
    if (preference === "system") return systemThemeQuery?.matches ? "dark" : "light";
    return preference;
  }

  async function applyTheme(preference: ThemePreference) {
    activeTheme = resolveTheme(preference);
    document.documentElement.dataset.theme = activeTheme;
    document.documentElement.style.colorScheme = activeTheme;

    try {
      await getCurrentWindow().setTheme(preference === "system" ? null : activeTheme);
    } catch (e) {
      console.warn("Unable to apply native window theme:", e);
    }

    await renderPlot();
  }

  function initializeTheme(): () => void {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    systemThemeQuery = mediaQuery;
    const savedPreference = localStorage.getItem(THEME_PREFERENCE_KEY) as ThemePreference | null;
    if (savedPreference === "light" || savedPreference === "dark" || savedPreference === "system") {
      themePreference = savedPreference;
      void applyTheme(savedPreference);
    } else {
      themePreference = null;
      showThemePrompt = true;
      activeTheme = mediaQuery.matches ? "dark" : "light";
      document.documentElement.dataset.theme = activeTheme;
      document.documentElement.style.colorScheme = activeTheme;
    }

    const handleSystemThemeChange = () => {
      if (themePreference === "system" || themePreference === null) {
        void applyTheme("system");
      }
    };
    mediaQuery.addEventListener("change", handleSystemThemeChange);
    return () => mediaQuery.removeEventListener("change", handleSystemThemeChange);
  }

  async function chooseTheme(preference: ThemePreference) {
    themePreference = preference;
    showThemePrompt = false;
    localStorage.setItem(THEME_PREFERENCE_KEY, preference);
    await applyTheme(preference);
  }

  async function renderPlot() {
    if (!plotHost) return;
    const figure = payloads.length > 0 ? buildPlotlyFigure(payloads, activeTheme) : emptyFigure(activeTheme);
    await Plotly.react(plotHost, figure.data, figure.layout, { responsive: true, displaylogo: false });
  }

  // ── Folder navigation ────────────────────────────────────────────────────────

  async function refreshSelections() {
    if (!rootPath.trim()) {
      experimentOptions = [];
      experimentName = "";
      sampleListResponse = null;
      return;
    }
    const response = await listExperimentFolders({ rootPath });
    experimentOptions = response.experimentOptions;
    experimentName = selectOrFirst(experimentName, experimentOptions);
    if (experimentName) {
      await loadSampleList();
    } else {
      sampleListResponse = null;
      currentMetadata = { medicineCount: 1, medicines: [{ name: "", dose: "" }], excludedSamples: [] };
    }
  }

  async function handleExperimentChange() {
    if (experimentName) await loadSampleList();
  }

  // ── Sample list & metadata ───────────────────────────────────────────────────

  async function loadSampleList() {
    if (!rootPath || !experimentName) return;
    try {
      sampleListResponse = await listSamplesInFolder(rootPath, experimentName);
      currentMetadata = sampleListResponse.metadata;
    } catch (_) {
      sampleListResponse = null;
    }
  }

  async function persistMetadata() {
    const fp = folderPath();
    if (!fp) return;
    try {
      await saveMetadata({ folderPath: fp, metadata: currentMetadata });
    } catch (e) {
      console.error("Failed to save metadata:", e);
    }
  }

  async function handleMedicineCountChange() {
    const count = Math.max(0, Math.min(5, currentMetadata.medicineCount));
    currentMetadata.medicineCount = count;
    while (currentMetadata.medicines.length < count) currentMetadata.medicines.push({ name: "", dose: "" });
    currentMetadata = { ...currentMetadata };
    await persistMetadata();
  }

  async function handleMedicineFieldChange() {
    currentMetadata = { ...currentMetadata };
    await persistMetadata();
  }

  async function toggleExcludeSample(info: SampleInfo) {
    if (!sampleListResponse) return;
    const fp = folderPath();
    if (!fp) return;

    let excluded = [...currentMetadata.excludedSamples];
    if (!info.included) {
      // restore: remove from excluded list
      excluded = excluded.filter((e) => e.fileName.toLowerCase() !== info.fileName.toLowerCase());
    } else {
      // exclude: add to excluded list
      if (excluded.length >= sampleListResponse.maxExclusions && !sampleListResponse.dixonExceptionAvailable) {
        statusTone = "error";
        statusMessage = `Cannot exclude: max ${sampleListResponse.maxExclusions} exclusion(s) allowed for n=${sampleListResponse.samples.length}.`;
        return;
      }
      excluded.push({ fileName: info.fileName, reason: "", method: "" });
    }
    currentMetadata = { ...currentMetadata, excludedSamples: excluded };
    await persistMetadata();
    await loadSampleList();
  }

  function isSampleToggleDisabled(info: SampleInfo): boolean {
    if (busy) return true;
    if (!sampleListResponse) return true;
    return (
      info.included &&
      sampleListResponse.currentExclusions >= sampleListResponse.maxExclusions &&
      !sampleListResponse.dixonExceptionAvailable
    );
  }

  async function runDixonQ() {
    if (!sampleListResponse) return;
    statusTone = "neutral";
    statusMessage = "Running Dixon Q review...";
    busyStats = true;
    try {
      const req: StatisticsRequest = {
        rootPath,
        baselineDurationSec,
        drugApplyTimeSec,
        drugApplyToleranceSec,
        baselineWarningThresholdPct,
      };
      const result = await runStatistics(req);
      const lines = result.text.split("\n");
      const dixonStart = lines.findIndex((l) => l.startsWith("Dixon Q Review"));
      const dixonEnd = lines.findIndex((l, i) => i > dixonStart && l.trim() === "");
      const dixonSection = dixonStart >= 0 ? lines.slice(dixonStart, dixonEnd > 0 ? dixonEnd : undefined).join("\n") : result.text;
      showStatsPanel = true;
      statsText = dixonSection;
      statsCsv = result.csv;
      statusTone = "neutral";
      statusMessage = "Dixon Q review complete.";
    } catch (e) {
      statusTone = "error";
      statusMessage = (e as AppError).message ?? "Dixon Q review failed.";
    } finally {
      busyStats = false;
    }
  }

  // ── Plot ─────────────────────────────────────────────────────────────────────

  function nextGroupColor(): string | null {
    if (!useGroupColor) return null;
    if (!overlay) return COLOR_PALETTE[0];
    return COLOR_PALETTE[overlayColorIndex % COLOR_PALETTE.length];
  }

  function buildRequest(): PlotRequest {
    return {
      rootPath, experimentName, displayMode, overlay, useGroupColor, showDropLines,
      legendStyle, showGroup, showBase, showDelta,
      groupColor: nextGroupColor(),
      baselineDurationSec,
      drugApplyTimeSec,
      drugApplyToleranceSec,
      baselineWarningThresholdPct,
      customTitle,
    };
  }

  async function plotData() {
    if (!experimentName) {
      statusTone = "error";
      statusMessage = "Please select an experiment folder.";
      return;
    }
    busy = true;
    statusTone = "neutral";
    statusMessage = "Loading and plotting data...";
    try {
      const payload = await buildPlotPayload(buildRequest());
      if (!overlay) {
        payloads = [payload];
        overlayColorIndex = 0;
      } else {
        payloads = [...payloads, payload];
        if (useGroupColor && payload.series.length > 0) overlayColorIndex += 1;
      }
      await renderPlot();
      const count = payload.series.filter((s) => s.sampleName !== "__group_legend__").length;
      let msg = count > 0 ? `Loaded ${count} trace(s) from ${payload.title}` : "No plottable traces found.";
      if (payload.baselineWarningCount > 0)
        msg += ` ⚠ ${payload.baselineWarningCount} baseline warning(s).`;
      if (payload.timingWarningCount > 0)
        msg += ` ⚠ ${payload.timingWarningCount} timing warning(s).`;
      statusTone = payload.baselineWarningCount > 0 || payload.timingWarningCount > 0 ? "warning" : "neutral";
      statusMessage = msg;
    } catch (e) {
      statusTone = "error";
      statusMessage = (e as AppError).message ?? "Failed to load or plot data.";
    } finally {
      busy = false;
    }
  }

  async function clearPlot() {
    payloads = [];
    overlayColorIndex = 0;
    statusTone = "neutral";
    statusMessage = "Ready";
    await renderPlot();
  }

  async function refreshLists() {
    busy = true;
    try {
      await refreshSelections();
      statusTone = "neutral";
      statusMessage = `Folder list refreshed.`;
    } catch (e) {
      statusTone = "error";
      statusMessage = (e as AppError).message ?? "Failed to refresh folder lists.";
    } finally {
      busy = false;
    }
  }

  async function browseRoot() {
    const selected = await open({ directory: true, multiple: false, defaultPath: rootPath || DEFAULT_ROOT_PATH });
    if (typeof selected === "string") {
      rootPath = selected;
      await refreshLists();
    }
  }

  async function exportPlot() {
    if (!plotHost || payloads.length === 0) {
      statusTone = "error";
      statusMessage = "Plot something before exporting.";
      return;
    }
    busy = true;
    try {
      const suggestedName = `${experimentName || "plot"}.png`.replace(/\s+/g, "-").toLowerCase();
      const exportPath = await chooseExportPath(suggestedName);
      if (!exportPath) { statusMessage = "Export cancelled."; return; }
      const dataUrl = await Plotly.toImage(plotHost, { format: "png", width: 1800, height: 1000, scale: 2 });
      await writeFile(exportPath, dataUrlToBytes(dataUrl));
      statusTone = "neutral";
      statusMessage = `Saved plot to ${exportPath}`;
    } catch (e) {
      statusTone = "error";
      statusMessage = (e as AppError).message ?? "Failed to export plot.";
    } finally {
      busy = false;
    }
  }

  // ── Statistics ───────────────────────────────────────────────────────────────

  async function computeStatistics() {
    if (!rootPath.trim()) {
      statusTone = "error";
      statusMessage = "Please choose a root folder to run statistics.";
      return;
    }
    busyStats = true;
    showStatsPanel = true;
    statsText = "Computing statistics...";
    statsCsv = "";
    statusTone = "neutral";
    statusMessage = "Running statistical analysis...";
    try {
      const req: StatisticsRequest = {
        rootPath,
        baselineDurationSec, drugApplyTimeSec, drugApplyToleranceSec, baselineWarningThresholdPct,
      };
      const result = await runStatistics(req);
      statsText = result.text;
      statsCsv = result.csv;
      statusTone = "neutral";
      statusMessage = "Statistics complete.";
    } catch (e) {
      statsText = (e as AppError).message ?? "Statistics failed.";
      statusTone = "error";
      statusMessage = "Statistics failed.";
    } finally {
      busyStats = false;
    }
  }

  async function exportStatsCsv() {
    if (!statsCsv) return;
    busy = true;
    try {
      const suggestedName = `${experimentName || "root"}-statistics.csv`.replace(/\s+/g, "-").toLowerCase();
      const exportPath = await chooseCsvExportPath(suggestedName);
      if (!exportPath) { statusMessage = "CSV export cancelled."; return; }
      await writeTextFile(exportPath, statsCsv);
      statusTone = "neutral";
      statusMessage = `Saved CSV to ${exportPath}`;
    } catch (e) {
      statusTone = "error";
      statusMessage = (e as AppError).message ?? "Failed to export CSV.";
    } finally {
      busy = false;
    }
  }

  onMount(() => {
    const cleanupTheme = initializeTheme();
    void (async () => {
      await refreshSelections();
      await renderPlot();
    })();
    return cleanupTheme;
  });
</script>

<svelte:head>
  <title>Skin Analysis Desktop</title>
</svelte:head>

<div class="shell">
  {#if showThemePrompt}
    <div class="theme-backdrop" role="presentation">
      <section class="theme-dialog" role="dialog" aria-modal="true" aria-labelledby="theme-title">
        <p class="eyebrow">Appearance</p>
        <h2 id="theme-title">Choose theme</h2>
        <div class="theme-choice-row">
          <button class="theme-choice" on:click={() => chooseTheme("light")}>
            <strong>Light</strong>
            <span>Bright interface</span>
          </button>
          <button class="theme-choice" on:click={() => chooseTheme("dark")}>
            <strong>Dark</strong>
            <span>Low-light interface</span>
          </button>
          <button class="theme-choice" on:click={() => chooseTheme("system")}>
            <strong>Follow OS</strong>
            <span>Match system</span>
          </button>
        </div>
      </section>
    </div>
  {/if}

  <aside class="controls">
    <div class="control-header">
      <p class="eyebrow">Tauri / Svelte</p>
      <h1>Skin Analysis Desktop</h1>
    </div>

    <!-- Root path -->
    <section class="card path-card">
      <label for="root-path">Root path</label>
      <div class="path-row">
        <input id="root-path" bind:value={rootPath} disabled={busy} />
        <button class="secondary" on:click={browseRoot} disabled={busy}>Browse</button>
      </div>
      <button class="secondary" on:click={refreshLists} disabled={busy}>Refresh List</button>
    </section>

    <!-- Folder selection -->
    <section class="card">
      <label for="experiment-select">Experiment Folder</label>
      <select id="experiment-select" bind:value={experimentName} size="8" on:change={handleExperimentChange} disabled={busy}>
        {#each experimentOptions as option}<option value={option}>{option}</option>{/each}
      </select>
    </section>

    <!-- Medicine metadata (collapsible) -->
    <section class="card">
      <button class="collapsible-toggle" on:click={() => (showMedicinePanel = !showMedicinePanel)}>
        {showMedicinePanel ? "[-]" : "[+]"} Medicine Metadata
      </button>
      {#if showMedicinePanel}
        <div class="med-section">
          <label>Medicine count (0–5)</label>
          <input
            type="number"
            min="0"
            max="5"
            bind:value={currentMetadata.medicineCount}
            on:change={handleMedicineCountChange}
            disabled={busy}
            class="number-input"
          />
          {#each currentMetadata.medicines.slice(0, currentMetadata.medicineCount) as medicine, i}
            <div class="med-row">
              <input
                placeholder="Name"
                bind:value={medicine.name}
                on:blur={handleMedicineFieldChange}
                disabled={busy}
                class="med-field"
              />
              <input
                placeholder="Dose"
                bind:value={medicine.dose}
                on:blur={handleMedicineFieldChange}
                disabled={busy}
                class="med-field"
              />
            </div>
          {/each}
        </div>
      {/if}
    </section>

    <!-- Sample exclusion list -->
    {#if sampleListResponse && sampleListResponse.samples.length > 0}
      <section class="card">
        <h2>Sample Exclusion</h2>
        <p class="subtle">
          Max exclusions: {sampleListResponse.maxExclusions} / n={sampleListResponse.samples.length}
          {#if sampleListResponse.dixonExceptionAvailable}· Dixon Q exception available{/if}
        </p>
        <div class="sample-list">
          {#each sampleListResponse.samples as info}
            <div class="sample-row" class:excluded={!info.included}>
              <span class="sample-status">{info.included ? "[IN]" : "[OUT]"}</span>
              <span class="sample-name">{info.sampleName}</span>
              {#if !info.included}
                {#if info.method === "dixon_q"}<span class="badge badge-dixon">Dixon Q</span>{/if}
                {#if info.reason}<span class="sample-reason">{info.reason}</span>{/if}
              {/if}
              <button
                class="tiny-btn"
                on:click={() => toggleExcludeSample(info)}
                disabled={isSampleToggleDisabled(info)}
              >
                {info.included ? "Exclude" : "Restore"}
              </button>
            </div>
          {/each}
        </div>
        <button class="secondary small-btn" on:click={runDixonQ} disabled={busy || busyStats}>
          Run Dixon Q Review
        </button>
      </section>
    {/if}

    <!-- Display unit -->
    <section class="card">
      <h2>Display Unit</h2>
      <label class="inline-option">
        <input type="radio" bind:group={displayMode} value="Norm" disabled={busy} />
        <span>Normalized (%)</span>
      </label>
      <label class="inline-option">
        <input type="radio" bind:group={displayMode} value="Raw" disabled={busy} />
        <span>Raw Data (pF)</span>
      </label>
      <label class="inline-option">
        <input type="radio" bind:group={displayMode} value="Base" disabled={busy} />
        <span>Baseline Only (Raw 20s)</span>
      </label>
    </section>

    <!-- Timing parameters (collapsible) -->
    <section class="card">
      <button class="collapsible-toggle" on:click={() => (showTimingPanel = !showTimingPanel)}>
        {showTimingPanel ? "[-]" : "[+]"} Timing Parameters
      </button>
      {#if showTimingPanel}
        <div class="timing-grid">
          <label>Baseline Duration (s)</label>
          <input type="number" min="1" step="1" bind:value={baselineDurationSec} disabled={busy} class="number-input" />
          <label>Drug Apply Time (s)</label>
          <input type="number" min="0" step="1" bind:value={drugApplyTimeSec} disabled={busy} class="number-input" />
          <label>Apply Window +/- (s)</label>
          <input type="number" min="0" step="1" bind:value={drugApplyToleranceSec} disabled={busy} class="number-input" />
          <label>Baseline Warning Threshold (%)</label>
          <input type="number" min="0" step="0.5" bind:value={baselineWarningThresholdPct} disabled={busy} class="number-input" />
        </div>
      {/if}
    </section>

    <!-- Legend -->
    <section class="card">
      <h2>Legend</h2>
      <label class="inline-option">
        <input type="radio" bind:group={legendStyle} value="Simple" disabled={busy} />
        <span>Simple</span>
      </label>
      <label class="inline-option">
        <input type="radio" bind:group={legendStyle} value="Detailed" disabled={busy} />
        <span>Detailed</span>
      </label>
      <div class="toggle-grid">
        <label class="inline-option">
          <input type="checkbox" bind:checked={showGroup} disabled={busy} />
          <span>Group Name</span>
        </label>
        <label class="inline-option">
          <input type="checkbox" bind:checked={showBase} disabled={busy} />
          <span>Baseline (Avg)</span>
        </label>
        <label class="inline-option">
          <input type="checkbox" bind:checked={showDelta} disabled={busy} />
          <span>Delta (Δ)</span>
        </label>
      </div>
      <label class="block-label">Custom title (optional)</label>
      <input placeholder="Leave blank for auto title" bind:value={customTitle} disabled={busy} />
    </section>

    <!-- Visual options -->
    <section class="card">
      <h2>Visual Options</h2>
      <div class="toggle-grid">
        <label class="inline-option">
          <input type="checkbox" bind:checked={overlay} disabled={busy} />
          <span>Overlay Mode</span>
        </label>
        <label class="inline-option">
          <input type="checkbox" bind:checked={useGroupColor} disabled={busy} />
          <span>Group Color</span>
        </label>
        <label class="inline-option">
          <input type="checkbox" bind:checked={showDropLines} disabled={busy} />
          <span>Show Drop Lines</span>
        </label>
      </div>
    </section>

    <!-- Actions -->
    <section class="card actions">
      <button class="primary" on:click={plotData} disabled={busy}>Load &amp; Plot</button>
      <button class="secondary" on:click={clearPlot} disabled={busy}>Clear Plot</button>
      <button class="secondary" on:click={exportPlot} disabled={busy}>Export Plot</button>
      <button class="secondary" on:click={computeStatistics} disabled={busy || busyStats}>Statistics</button>
    </section>
  </aside>

  <main class="workspace">
    <div class="workspace-top">
      <div>
        <p class="eyebrow">Status</p>
        <p
          class:status-error={statusTone === "error"}
          class:status-warning={statusTone === "warning"}
          class="status"
        >{statusMessage}</p>
      </div>
    </div>

    <section class="plot-card">
      <div bind:this={plotHost} class="plot-host"></div>
    </section>

    <!-- Statistics panel -->
    {#if showStatsPanel}
      <section class="card stats-panel">
        <div class="stats-header">
          <h2>Statistical Analysis</h2>
          <div class="stats-actions">
            {#if statsCsv}
              <button class="secondary small-btn" on:click={exportStatsCsv} disabled={busy}>
                Export CSV
              </button>
            {/if}
            <button class="secondary small-btn" on:click={() => (showStatsPanel = false)}>Close</button>
          </div>
        </div>
        <pre class="stats-text">{busyStats ? "Computing..." : statsText}</pre>
      </section>
    {/if}
  </main>
</div>

<style>
  :global(*, *::before, *::after) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    font-size: 13px;
    background: #f5f1ea;
    color: #30271c;
  }

  .shell { display: flex; height: 100vh; overflow: hidden; }

  .controls {
    width: 280px;
    min-width: 240px;
    max-width: 320px;
    overflow-y: auto;
    background: #ede7db;
    border-right: 1px solid #d7cfc0;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }

  .workspace {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    min-width: 0;
  }

  .control-header { padding-bottom: 4px; }
  .control-header h1 { font-size: 15px; font-weight: 700; }

  .card {
    background: #fffdf8;
    border: 1px solid #dfd6c6;
    border-radius: 6px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .path-card { gap: 6px; }
  .path-row { display: flex; gap: 6px; }
  .path-row input { flex: 1; min-width: 0; }

  label { font-size: 11px; font-weight: 600; color: #6b5c47; }
  .block-label { margin-top: 4px; }
  .eyebrow { font-size: 10px; color: #9c8c7a; text-transform: uppercase; letter-spacing: 0.05em; }
  .subtle { font-size: 11px; color: #9c8c7a; }

  select {
    border: 1px solid #c9bfb0;
    border-radius: 4px;
    padding: 3px 6px;
    background: #fff;
    font-size: 12px;
    width: 100%;
  }

  input[type="text"],
  input:not([type="radio"]):not([type="checkbox"]):not([type="number"]) {
    border: 1px solid #c9bfb0;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    width: 100%;
    background: #fff;
  }

  input[type="number"].number-input {
    border: 1px solid #c9bfb0;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 12px;
    width: 80px;
    background: #fff;
  }

  button {
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  button.primary { background: #5a7a3a; color: #fff; font-weight: 600; }
  button.primary:hover:not(:disabled) { background: #4a6630; }
  button.secondary { background: #e0d8cc; color: #30271c; }
  button.secondary:hover:not(:disabled) { background: #cfc6b8; }
  button.small-btn { padding: 4px 8px; font-size: 11px; }
  button.tiny-btn { padding: 2px 6px; font-size: 10px; margin-left: auto; flex-shrink: 0; }

  .collapsible-toggle {
    background: none;
    padding: 2px 0;
    font-size: 12px;
    font-weight: 600;
    color: #5a4a38;
    text-align: left;
  }

  h2 { font-size: 12px; font-weight: 700; color: #5a4a38; }

  .inline-option { display: flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; }
  .toggle-grid { display: flex; flex-direction: column; gap: 4px; }

  .actions { gap: 6px; }

  /* Medicine */
  .med-section { display: flex; flex-direction: column; gap: 6px; }
  .med-row { display: flex; gap: 6px; }
  .med-field { flex: 1; min-width: 0; border: 1px solid #c9bfb0; border-radius: 4px; padding: 3px 6px; font-size: 12px; }

  /* Timing grid */
  .timing-grid { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; align-items: center; }

  /* Sample list */
  .sample-list { display: flex; flex-direction: column; gap: 3px; max-height: 180px; overflow-y: auto; }
  .sample-row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 6px;
    background: #f5f0e8;
    border-radius: 3px;
    font-size: 11px;
  }
  .sample-row.excluded { background: #f5e8e8; opacity: 0.85; }
  .sample-status { font-weight: 700; font-size: 10px; color: #5a7a3a; min-width: 32px; }
  .sample-row.excluded .sample-status { color: #c0392b; }
  .sample-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sample-reason { font-size: 10px; color: #9c8c7a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60px; }
  .badge { font-size: 9px; padding: 1px 4px; border-radius: 3px; font-weight: 700; }
  .badge-dixon { background: #f0e6cc; color: #7a5a1a; }

  /* Status */
  .workspace-top { display: flex; justify-content: space-between; align-items: flex-start; }
  .status { font-size: 12px; max-width: 600px; }
  .status-error { color: #c0392b; }
  .status-warning { color: #c0a020; }

  /* Plot */
  .plot-card { flex: 1; background: #fffdf8; border: 1px solid #dfd6c6; border-radius: 6px; padding: 8px; min-height: 400px; }
  .plot-host { width: 100%; height: 100%; min-height: 380px; }

  /* Stats panel */
  .stats-panel { background: #fffdf8; }
  .stats-header { display: flex; justify-content: space-between; align-items: center; }
  .stats-actions { display: flex; gap: 6px; }
  .stats-text {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 11px;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 400px;
    overflow-y: auto;
    background: #f8f4ee;
    padding: 8px;
    border-radius: 4px;
    border: 1px solid #dfd6c6;
    color: #30271c;
    line-height: 1.5;
  }

  .theme-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(38, 31, 22, 0.42);
  }

  .theme-dialog {
    width: min(560px, 100%);
    background: #fffdf8;
    border: 1px solid #dfd6c6;
    border-radius: 8px;
    box-shadow: 0 24px 70px rgba(34, 26, 16, 0.26);
    padding: 18px;
  }

  .theme-dialog h2 {
    font-size: 18px;
    margin-bottom: 14px;
  }

  .theme-choice-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .theme-choice {
    min-height: 84px;
    border: 1px solid #d7cfc0;
    background: #f8f4ee;
    color: #30271c;
    text-align: left;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
  }

  .theme-choice:hover {
    background: #efe6d8;
  }

  .theme-choice strong {
    font-size: 13px;
  }

  .theme-choice span {
    font-size: 11px;
    color: #6b5c47;
  }

  :global(html[data-theme="dark"] body) {
    background: #191713;
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) .controls {
    background: #201d18;
    border-right-color: #3d372f;
  }

  :global(html[data-theme="dark"]) .card,
  :global(html[data-theme="dark"]) .plot-card,
  :global(html[data-theme="dark"]) .stats-panel,
  :global(html[data-theme="dark"]) .theme-dialog {
    background: #24211c;
    border-color: #4b4338;
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) label,
  :global(html[data-theme="dark"]) h2,
  :global(html[data-theme="dark"]) .collapsible-toggle,
  :global(html[data-theme="dark"]) .control-header h1 {
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) .eyebrow,
  :global(html[data-theme="dark"]) .subtle,
  :global(html[data-theme="dark"]) .sample-reason,
  :global(html[data-theme="dark"]) .theme-choice span {
    color: #b8aa98;
  }

  :global(html[data-theme="dark"]) input[type="text"],
  :global(html[data-theme="dark"]) input:not([type="radio"]):not([type="checkbox"]):not([type="number"]),
  :global(html[data-theme="dark"]) input[type="number"].number-input,
  :global(html[data-theme="dark"]) select,
  :global(html[data-theme="dark"]) .med-field {
    background: #191713;
    border-color: #5a5145;
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) button.secondary,
  :global(html[data-theme="dark"]) .theme-choice {
    background: #383127;
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) button.secondary:hover:not(:disabled),
  :global(html[data-theme="dark"]) .theme-choice:hover {
    background: #483f33;
  }

  :global(html[data-theme="dark"]) .sample-row,
  :global(html[data-theme="dark"]) .stats-text {
    background: #191713;
    border-color: #4b4338;
    color: #f1e9dc;
  }

  :global(html[data-theme="dark"]) .sample-row.excluded {
    background: #382524;
  }

  @media (max-width: 640px) {
    .theme-choice-row {
      grid-template-columns: 1fr;
    }
  }
</style>
