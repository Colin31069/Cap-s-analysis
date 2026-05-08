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
  let selectedSampleFileName = "";

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
  let isDark = true;

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
    isDark = activeTheme === "dark";
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
      isDark = activeTheme === "dark";
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

  async function toggleTheme() {
    await chooseTheme(activeTheme === "dark" ? "light" : "dark");
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
    selectedSampleFileName = "";
    if (experimentName) await loadSampleList();
  }

  // ── Sample list & metadata ───────────────────────────────────────────────────

  async function loadSampleList() {
    if (!rootPath || !experimentName) return;
    try {
      sampleListResponse = await listSamplesInFolder(rootPath, experimentName);
      currentMetadata = sampleListResponse.metadata;
      if (!sampleListResponse.samples.some((s) => s.fileName === selectedSampleFileName)) {
        selectedSampleFileName = sampleListResponse.samples[0]?.fileName ?? "";
      }
    } catch (_) {
      sampleListResponse = null;
      selectedSampleFileName = "";
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
      if (sampleListResponse.samples.length < 5) {
        statusTone = "warning";
        statusMessage = `Data count is ${sampleListResponse.samples.length}; at least 5 samples are required before exclusion.`;
        return;
      }
      if (sampleListResponse.currentExclusions >= sampleListResponse.maxExclusions) {
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

  function selectedSampleInfo(): SampleInfo | null {
    if (!sampleListResponse || !selectedSampleFileName) return null;
    return sampleListResponse.samples.find((s) => s.fileName === selectedSampleFileName) ?? null;
  }

  function hasTooFewSamplesForExclusion(): boolean {
    return Boolean(sampleListResponse && sampleListResponse.samples.length < 5);
  }

  function tooFewSamplesMessage(): string {
    const count = sampleListResponse?.samples.length ?? 0;
    return `Data count is ${count}; fewer than 5 samples, so Dixon Q test and data exclusion cannot be used.`;
  }

  function canExcludeSelected(): boolean {
    const info = selectedSampleInfo();
    if (!info || !info.included || busy) return false;
    if (!sampleListResponse) return false;
    if (hasTooFewSamplesForExclusion()) return false;
    return sampleListResponse.currentExclusions < sampleListResponse.maxExclusions;
  }

  function canRestoreSelected(): boolean {
    const info = selectedSampleInfo();
    return Boolean(info && !info.included && !busy);
  }

  async function excludeSelectedSample() {
    const info = selectedSampleInfo();
    if (!info || !info.included) return;
    await toggleExcludeSample(info);
  }

  async function restoreSelectedSample() {
    const info = selectedSampleInfo();
    if (!info || info.included) return;
    await toggleExcludeSample(info);
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

  <!-- ── Sidebar ──────────────────────────────────────────────────── -->
  <aside class="sidebar">
    <div class="sidebar-hd">
      <div class="brand">
        <span class="brand-ico">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </span>
        <div>
          <p class="eyebrow">Tauri · Svelte</p>
          <h1>Skin Analysis</h1>
        </div>
      </div>
      <button class="btn btn-icon theme-btn" on:click={toggleTheme} title={isDark ? "Switch to light mode" : "Switch to dark mode"}>
        {#if isDark}
          <!-- Sun icon: switch to light -->
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/>
            <line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/>
            <line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        {:else}
          <!-- Moon icon: switch to dark -->
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {/if}
      </button>
    </div>

    <div class="sidebar-body">

      <!-- Root path -->
      <div class="panel">
        <label class="panel-lbl" for="root-path">Root Directory</label>
        <div class="path-row">
          <input id="root-path" bind:value={rootPath} disabled={busy} placeholder="/path/to/data" />
          <button class="btn btn-icon" on:click={browseRoot} disabled={busy} title="Browse folder">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </button>
          <button class="btn btn-icon" on:click={refreshLists} disabled={busy} title="Refresh list">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Experiment folder -->
      <div class="panel">
        <label class="panel-lbl" for="exp-sel">Experiment</label>
        <select id="exp-sel" bind:value={experimentName} size="6" on:change={handleExperimentChange} disabled={busy}>
          {#each experimentOptions as opt}<option value={opt}>{opt}</option>{/each}
        </select>
        {#if experimentOptions.length === 0}
          <p class="hint">No experiments found in this directory</p>
        {/if}
      </div>

      <!-- Medicine metadata (collapsible) -->
      <div class="panel">
        <button class="collapse-btn" on:click={() => (showMedicinePanel = !showMedicinePanel)}>
          <svg class="chevron" class:open={showMedicinePanel} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          Medicine Metadata
        </button>
        {#if showMedicinePanel}
          <div class="collapse-body">
            <div class="field-row">
              <label>Count (0–5)</label>
              <input type="number" min="0" max="5" bind:value={currentMetadata.medicineCount} on:change={handleMedicineCountChange} disabled={busy} class="num-in" />
            </div>
            {#each currentMetadata.medicines.slice(0, currentMetadata.medicineCount) as medicine, i}
              <div class="med-row">
                <input placeholder="Name" bind:value={medicine.name} on:blur={handleMedicineFieldChange} disabled={busy} />
                <input placeholder="Dose" bind:value={medicine.dose} on:blur={handleMedicineFieldChange} disabled={busy} />
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Sample exclusion -->
      {#if sampleListResponse && sampleListResponse.samples.length > 0}
        <div class="panel sample-exclusion-panel">
          <div class="panel-lbl">
            Sample Exclusion
            <span class="badge badge-dim">{sampleListResponse.currentExclusions}/{sampleListResponse.maxExclusions}</span>
            {#if hasTooFewSamplesForExclusion()}
              <span class="badge badge-blue">n&lt;5</span>
            {/if}
          </div>
          {#if hasTooFewSamplesForExclusion()}
            <p class="exclusion-warning">{tooFewSamplesMessage()}</p>
          {/if}
          <select
            class="sample-select"
            bind:value={selectedSampleFileName}
            size={Math.min(6, Math.max(3, sampleListResponse.samples.length))}
            disabled={busy}
          >
            {#each sampleListResponse.samples as info}
              <option value={info.fileName}>
                {info.included ? "[IN]" : "[OUT]"} {info.sampleName}{!info.included && info.method === "dixon_q" ? " (DQ)" : ""}
              </option>
            {/each}
          </select>
          <div class="sample-actions">
            <span class="action-tip-zone">
              <button class="btn btn-danger btn-sm" on:click={excludeSelectedSample} disabled={!canExcludeSelected()}>
                Exclude Selected
              </button>
            </span>
            <span class="action-tip-zone">
              <button class="btn btn-restore btn-sm" on:click={restoreSelectedSample} disabled={!canRestoreSelected()}>
                Restore Selected
              </button>
            </span>
          </div>
          <span class="action-tip-zone">
            <button class="btn btn-ghost btn-sm btn-full" on:click={runDixonQ} disabled={busy || busyStats || hasTooFewSamplesForExclusion()}>
              Run Dixon Q Review
            </button>
          </span>
          {#if hasTooFewSamplesForExclusion()}
            <p class="hover-warning">{tooFewSamplesMessage()}</p>
          {/if}
        </div>
      {/if}

      <!-- Display mode -->
      <div class="panel">
        <div class="panel-lbl">Display Mode</div>
        <div class="radio-g">
          <label class="ropt" class:on={displayMode === "Norm"}>
            <input type="radio" bind:group={displayMode} value="Norm" disabled={busy} />
            <span>Normalized <em>(%)</em></span>
          </label>
          <label class="ropt" class:on={displayMode === "Raw"}>
            <input type="radio" bind:group={displayMode} value="Raw" disabled={busy} />
            <span>Raw Data <em>(pF)</em></span>
          </label>
          <label class="ropt" class:on={displayMode === "Base"}>
            <input type="radio" bind:group={displayMode} value="Base" disabled={busy} />
            <span>Baseline Only <em>(20 s)</em></span>
          </label>
        </div>
      </div>

      <!-- Timing parameters (collapsible) -->
      <div class="panel">
        <button class="collapse-btn" on:click={() => (showTimingPanel = !showTimingPanel)}>
          <svg class="chevron" class:open={showTimingPanel} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          Timing Parameters
        </button>
        {#if showTimingPanel}
          <div class="timing-g">
            <label>Baseline (s)</label>
            <input type="number" min="1" step="1" bind:value={baselineDurationSec} disabled={busy} class="num-in" />
            <label>Drug Apply (s)</label>
            <input type="number" min="0" step="1" bind:value={drugApplyTimeSec} disabled={busy} class="num-in" />
            <label>Window ±(s)</label>
            <input type="number" min="0" step="1" bind:value={drugApplyToleranceSec} disabled={busy} class="num-in" />
            <label>Warn Threshold (%)</label>
            <input type="number" min="0" step="0.5" bind:value={baselineWarningThresholdPct} disabled={busy} class="num-in" />
          </div>
        {/if}
      </div>

      <!-- Legend -->
      <div class="panel">
        <div class="panel-lbl">Legend Style</div>
        <div class="radio-g radio-row">
          <label class="ropt" class:on={legendStyle === "Simple"}>
            <input type="radio" bind:group={legendStyle} value="Simple" disabled={busy} />
            <span>Simple</span>
          </label>
          <label class="ropt" class:on={legendStyle === "Detailed"}>
            <input type="radio" bind:group={legendStyle} value="Detailed" disabled={busy} />
            <span>Detailed</span>
          </label>
        </div>
        <div class="check-g">
          <label class="copt">
            <input type="checkbox" bind:checked={showGroup} disabled={busy} />
            <span>Group Name</span>
          </label>
          <label class="copt">
            <input type="checkbox" bind:checked={showBase} disabled={busy} />
            <span>Baseline Avg</span>
          </label>
          <label class="copt">
            <input type="checkbox" bind:checked={showDelta} disabled={busy} />
            <span>Delta (Δ)</span>
          </label>
        </div>
        <input placeholder="Custom title (optional)" bind:value={customTitle} disabled={busy} class="title-in" />
      </div>

      <!-- Visual options -->
      <div class="panel">
        <div class="panel-lbl">Visual Options</div>
        <div class="check-g">
          <label class="copt">
            <input type="checkbox" bind:checked={overlay} disabled={busy} />
            <span>Overlay Mode</span>
          </label>
          <label class="copt">
            <input type="checkbox" bind:checked={useGroupColor} disabled={busy} />
            <span>Group Color</span>
          </label>
          <label class="copt">
            <input type="checkbox" bind:checked={showDropLines} disabled={busy} />
            <span>Drop Lines</span>
          </label>
        </div>
      </div>

    </div><!-- /sidebar-body -->

    <!-- Pinned action footer -->
    <div class="sidebar-ft">
      <button class="btn btn-accent btn-full" on:click={plotData} disabled={busy}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Load &amp; Plot
      </button>
      <div class="ft-row">
        <button class="btn btn-ghost btn-sm" on:click={clearPlot} disabled={busy}>Clear</button>
        <button class="btn btn-ghost btn-sm" on:click={exportPlot} disabled={busy}>Export PNG</button>
        <button class="btn btn-ghost btn-sm" on:click={computeStatistics} disabled={busy || busyStats}>Statistics</button>
      </div>
    </div>
  </aside>

  <!-- ── Workspace ─────────────────────────────────────────────────── -->
  <main class="ws">
    <div class="status-bar">
      <span class="sdot-bar"
        class:sdot-err={statusTone === "error"}
        class:sdot-warn={statusTone === "warning"}
        class:sdot-ok={statusTone === "neutral" && statusMessage !== "Ready"}
      ></span>
      <span class="status-msg"
        class:msg-err={statusTone === "error"}
        class:msg-warn={statusTone === "warning"}
      >{statusMessage}</span>
      {#if busy}<span class="spin"></span>{/if}
    </div>

    <section class="plot-card">
      <div bind:this={plotHost} class="plot-h"></div>
    </section>

    {#if showStatsPanel}
      <section class="stats-card">
        <div class="stats-hd">
          <span class="panel-lbl">Statistical Analysis</span>
          <div class="stats-acts">
            {#if statsCsv}
              <button class="btn btn-ghost btn-sm" on:click={exportStatsCsv} disabled={busy}>Export CSV</button>
            {/if}
            <button class="btn btn-ghost btn-sm" on:click={() => (showStatsPanel = false)}>Close</button>
          </div>
        </div>
        <pre class="stats-body">{busyStats ? "Computing…" : statsText}</pre>
      </section>
    {/if}
  </main>
</div>

<style>
  /* ── Design Tokens ──────────────────────────────────────────────── */
  :global(:root),
  :global(:root[data-theme="dark"]) {
    color-scheme: dark;
    --bg:       #0B1120;
    --sidebar:  #0F172A;
    --srf-1:    #141D2E;
    --srf-2:    #192336;
    --srf-3:    #1E2A3E;
    --bdr:      #253450;
    --bdr-f:    rgba(34, 197, 94, 0.45);
    --tx:       #E2E8F0;
    --tx-m:     #94A3B8;
    --tx-d:     #64748B;
    --acc:      #22C55E;
    --acc-h:    #1DAF53;
    --acc-dim:  rgba(34, 197, 94, 0.11);
    --blue:     #60A5FA;
    --blue-dim: rgba(96, 165, 250, 0.11);
    --amber:    #F59E0B;
    --amb-dim:  rgba(245, 158, 11, 0.11);
    --red:      #EF4444;
    --red-dim:  rgba(239, 68, 68, 0.09);
    --r-xs: 3px;
    --r-sm: 5px;
    --r:    7px;
  }

  :global(:root[data-theme="light"]) {
    color-scheme: light;
    --bg:       #F1F5F9;
    --sidebar:  #E9EFF7;
    --srf-1:    #FFFFFF;
    --srf-2:    #F8FAFC;
    --srf-3:    #EDF2F7;
    --bdr:      #CBD5E1;
    --bdr-f:    rgba(22, 163, 74, 0.55);
    --tx:       #0F172A;
    --tx-m:     #475569;
    --tx-d:     #94A3B8;
    --acc:      #16A34A;
    --acc-h:    #15803D;
    --acc-dim:  rgba(22, 163, 74, 0.10);
    --blue:     #2563EB;
    --blue-dim: rgba(37, 99, 235, 0.10);
    --amber:    #D97706;
    --amb-dim:  rgba(217, 119, 6, 0.10);
    --red:      #DC2626;
    --red-dim:  rgba(220, 38, 38, 0.08);
  }

  :global(*, *::before, *::after) { box-sizing: border-box; margin: 0; padding: 0; }

  :global(body) {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.5;
    background: var(--bg);
    color: var(--tx);
    -webkit-font-smoothing: antialiased;
  }

  :global(::-webkit-scrollbar) { width: 5px; height: 5px; }
  :global(::-webkit-scrollbar-track) { background: transparent; }
  :global(::-webkit-scrollbar-thumb) { background: var(--srf-3); border-radius: 99px; }
  :global(::-webkit-scrollbar-thumb:hover) { background: var(--bdr); }

  /* ── Shell ──────────────────────────────────────────────────────── */
  .shell { display: flex; height: 100vh; overflow: hidden; }

  /* ── Sidebar ────────────────────────────────────────────────────── */
  .sidebar {
    width: 290px;
    min-width: 250px;
    max-width: 340px;
    display: flex;
    flex-direction: column;
    background: var(--sidebar);
    border-right: 1px solid var(--bdr);
    flex-shrink: 0;
    overflow: hidden;
  }

  .sidebar-hd {
    padding: 13px 14px 11px;
    border-bottom: 1px solid var(--bdr);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .theme-btn {
    color: var(--tx-d);
    background: var(--srf-2);
    border: 1px solid var(--bdr);
    transition: color 0.15s, background 0.15s;
  }
  .theme-btn:hover { color: var(--tx-m); background: var(--srf-3); }

  .brand { display: flex; align-items: center; gap: 10px; }

  .brand-ico {
    width: 30px; height: 30px;
    border-radius: var(--r-sm);
    background: var(--acc-dim);
    border: 1px solid rgba(34, 197, 94, 0.22);
    display: flex; align-items: center; justify-content: center;
    color: var(--acc);
    flex-shrink: 0;
  }

  .brand h1 { font-size: 13px; font-weight: 700; color: var(--tx); letter-spacing: -0.01em; }

  .eyebrow {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    color: var(--tx-d);
    margin-bottom: 1px;
  }

  .sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 4px 12px 8px;
    display: flex;
    flex-direction: column;
  }

  .sidebar-ft {
    padding: 10px 12px 13px;
    border-top: 1px solid var(--bdr);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .ft-row { display: flex; gap: 5px; }
  .ft-row .btn { flex: 1; }

  /* ── Panels ─────────────────────────────────────────────────────── */
  .panel {
    padding: 8px 0;
    border-bottom: 1px solid var(--bdr);
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .panel:last-child { border-bottom: none; }

  .panel-lbl {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--tx-d);
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .collapse-btn {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--tx-d);
    transition: color 0.15s;
  }
  .collapse-btn:hover { color: var(--tx-m); }

  .chevron { transition: transform 0.2s ease; flex-shrink: 0; }
  .chevron.open { transform: rotate(90deg); }

  .collapse-body { display: flex; flex-direction: column; gap: 5px; }

  /* ── Path row ───────────────────────────────────────────────────── */
  .path-row { display: flex; gap: 4px; align-items: center; }
  .path-row input { flex: 1; min-width: 0; }

  /* ── Form controls ──────────────────────────────────────────────── */
  input:not([type="radio"]):not([type="checkbox"]),
  select {
    background: var(--srf-2);
    border: 1px solid var(--bdr);
    border-radius: var(--r-xs);
    color: var(--tx);
    font-family: inherit;
    font-size: 12px;
    padding: 5px 8px;
    width: 100%;
    outline: none;
    transition: border-color 0.15s;
  }
  input:not([type="radio"]):not([type="checkbox"]):focus,
  select:focus { border-color: var(--bdr-f); }
  input::placeholder { color: var(--tx-d); }
  input:disabled, select:disabled { opacity: 0.38; cursor: not-allowed; }

  select { min-height: 106px; cursor: pointer; }

  .num-in {
    width: 68px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
    font-size: 11px;
  }

  .title-in { font-size: 11px; }

  /* ── Medicine ───────────────────────────────────────────────────── */
  .med-row { display: flex; gap: 5px; }
  .med-row input { flex: 1; }

  .field-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .field-row label { font-size: 11px; color: var(--tx-m); flex: 1; }

  /* ── Timing grid ────────────────────────────────────────────────── */
  .timing-g {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 5px 8px;
    align-items: center;
    padding-top: 2px;
  }
  .timing-g label { font-size: 11px; color: var(--tx-m); }

  /* ── Radio group ────────────────────────────────────────────────── */
  .radio-g { display: flex; flex-direction: column; gap: 2px; }
  .radio-g.radio-row { flex-direction: row; gap: 5px; flex-wrap: wrap; }

  .ropt {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 7px;
    border-radius: var(--r-xs);
    font-size: 12px;
    cursor: pointer;
    color: var(--tx-m);
    border: 1px solid transparent;
    transition: background 0.12s, color 0.12s;
  }
  .ropt:hover { background: var(--srf-2); color: var(--tx); }
  .ropt.on { background: var(--acc-dim); color: var(--acc); border-color: rgba(34, 197, 94, 0.18); }
  .ropt em { font-style: normal; font-size: 10px; opacity: 0.6; }
  .ropt input { width: auto; background: none; border: none; padding: 0; accent-color: var(--acc); }

  /* ── Checkbox group ─────────────────────────────────────────────── */
  .check-g { display: flex; flex-direction: column; gap: 2px; }

  .copt {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 3px 7px;
    border-radius: var(--r-xs);
    font-size: 12px;
    cursor: pointer;
    color: var(--tx-m);
    transition: background 0.12s, color 0.12s;
  }
  .copt:hover { background: var(--srf-2); color: var(--tx); }
  .copt input { width: auto; background: none; border: none; padding: 0; accent-color: var(--acc); }

  /* ── Sample list ────────────────────────────────────────────────── */
  .sample-select {
    min-height: 118px;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
    font-size: 11px;
  }

  .sample-select option {
    padding: 3px 4px;
    color: var(--tx-m);
  }

  .sample-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px;
  }

  .action-tip-zone {
    display: block;
    width: 100%;
  }
  .action-tip-zone .btn {
    width: 100%;
  }

  .exclusion-warning,
  .hover-warning {
    color: var(--red);
    font-size: 11px;
    font-weight: 800;
    line-height: 1.35;
  }

  .exclusion-warning {
    padding: 3px 0 2px;
  }

  .hover-warning {
    display: none;
    padding: 5px 7px;
    background: var(--red-dim);
    border: 1px solid rgba(239, 68, 68, 0.22);
    border-radius: var(--r-xs);
  }

  .sample-exclusion-panel:has(.action-tip-zone:hover) .hover-warning {
    display: block;
  }

  /* ── Badges ─────────────────────────────────────────────────────── */
  .badge {
    display: inline-flex;
    align-items: center;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 1px 5px;
    border-radius: 3px;
    flex-shrink: 0;
  }
  .badge-dim   { background: var(--srf-3); color: var(--tx-d); }
  .badge-blue  { background: var(--blue-dim); color: var(--blue);  border: 1px solid rgba(96, 165, 250, 0.18); }

  .hint { font-size: 11px; color: var(--tx-d); font-style: italic; }

  /* ── Buttons ────────────────────────────────────────────────────── */
  button { cursor: pointer; font-family: inherit; border: none; transition: background 0.15s, opacity 0.15s; }
  button:disabled { opacity: 0.32; cursor: not-allowed; pointer-events: none; }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    border-radius: var(--r-xs);
    font-size: 12px;
    font-weight: 500;
    padding: 6px 12px;
    white-space: nowrap;
  }

  .btn-accent {
    background: var(--acc);
    color: #051009;
    font-weight: 700;
    font-size: 13px;
    padding: 9px 14px;
    border-radius: var(--r-sm);
    box-shadow: 0 0 16px rgba(34, 197, 94, 0.18);
  }
  :global([data-theme="light"]) .btn-accent { color: #ffffff; }
  .btn-accent:hover:not(:disabled) { background: var(--acc-h); box-shadow: 0 0 22px rgba(34, 197, 94, 0.28); }
  .btn-accent:active:not(:disabled) { transform: scale(0.98); }

  .btn-ghost {
    background: var(--srf-2);
    color: var(--tx-m);
    border: 1px solid var(--bdr);
  }
  .btn-ghost:hover:not(:disabled) { background: var(--srf-3); color: var(--tx); }

  .btn-icon { padding: 5px 6px; flex-shrink: 0; }
  .btn-full { width: 100%; }
  .btn-sm  { font-size: 11px; padding: 4px 8px; }

  .btn-danger  { background: var(--red-dim); color: var(--red);  border: 1px solid rgba(239, 68, 68, 0.2); }
  .btn-danger:hover:not(:disabled)  { background: rgba(239, 68, 68, 0.15); }
  .btn-restore { background: var(--acc-dim); color: var(--acc);  border: 1px solid rgba(34, 197, 94, 0.2); }
  .btn-restore:hover:not(:disabled) { background: rgba(34, 197, 94, 0.18); }

  /* ── Workspace ──────────────────────────────────────────────────── */
  .ws {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    min-width: 0;
  }

  /* ── Status bar ─────────────────────────────────────────────────── */
  .status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    background: var(--srf-1);
    border: 1px solid var(--bdr);
    border-radius: var(--r);
    flex-shrink: 0;
  }

  .sdot-bar {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--tx-d);
    flex-shrink: 0;
    transition: background 0.25s, box-shadow 0.25s;
  }
  .sdot-err  { background: var(--red);   box-shadow: 0 0 6px rgba(239, 68, 68, 0.55); }
  .sdot-warn { background: var(--amber); box-shadow: 0 0 5px rgba(245, 158, 11, 0.45); }
  .sdot-ok   { background: var(--acc);   box-shadow: 0 0 5px rgba(34, 197, 94, 0.45); }

  .status-msg { font-size: 12px; color: var(--tx-m); flex: 1; }
  .msg-err  { color: var(--red); }
  .msg-warn { color: var(--amber); }

  .spin {
    width: 13px; height: 13px;
    border: 2px solid var(--srf-3);
    border-top-color: var(--acc);
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Plot card ──────────────────────────────────────────────────── */
  .plot-card {
    flex: 1;
    background: var(--srf-1);
    border: 1px solid var(--bdr);
    border-radius: var(--r);
    padding: 10px;
    min-height: 420px;
    overflow: hidden;
  }
  .plot-h { width: 100%; height: 100%; min-height: 400px; }

  /* ── Stats card ─────────────────────────────────────────────────── */
  .stats-card {
    background: var(--srf-1);
    border: 1px solid var(--bdr);
    border-radius: var(--r);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .stats-hd  { display: flex; justify-content: space-between; align-items: center; }
  .stats-acts { display: flex; gap: 6px; }

  .stats-body {
    font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", monospace;
    font-size: 11px;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 380px;
    overflow-y: auto;
    background: var(--bg);
    border: 1px solid var(--bdr);
    border-radius: var(--r-xs);
    padding: 10px 12px;
    color: var(--tx-m);
  }

  .theme-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(2, 6, 23, 0.62);
    backdrop-filter: blur(8px);
  }

  .theme-dialog {
    width: min(560px, 100%);
    background: var(--srf-1);
    border: 1px solid var(--bdr);
    border-radius: var(--r);
    box-shadow: 0 24px 70px rgba(2, 6, 23, 0.34);
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
    border: 1px solid var(--bdr);
    background: var(--srf-2);
    color: var(--tx);
    text-align: left;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
  }

  .theme-choice:hover {
    background: var(--srf-3);
    border-color: var(--bdr-f);
  }

  .theme-choice strong {
    font-size: 13px;
  }

  .theme-choice span {
    font-size: 11px;
    color: var(--tx-m);
  }

  @media (max-width: 640px) {
    .theme-choice-row {
      grid-template-columns: 1fr;
    }
  }
</style>
