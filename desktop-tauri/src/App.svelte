<script lang="ts">
  import { onMount } from "svelte";
  import { open } from "@tauri-apps/plugin-dialog";
  import { writeFile } from "@tauri-apps/plugin-fs";
  import Plotly from "plotly.js-dist-min";

  import { buildPlotPayload, chooseExportPath, listFolderLevels } from "./lib/api";
  import { buildPlotlyFigure, COLOR_PALETTE, dataUrlToBytes, emptyFigure } from "./lib/plot";
  import type { AppError, DisplayMode, LegendStyle, PlotRequest, PlotResponse } from "./lib/types";

  const DEFAULT_ROOT_PATH = "/Users/k/Downloads/20260303";

  let rootPath = DEFAULT_ROOT_PATH;
  let l1 = "";
  let l2 = "";
  let l3 = "";
  let l1Options: string[] = [];
  let l2Options: string[] = [];
  let l3Options: string[] = [];

  let displayMode: DisplayMode = "Norm";
  let overlay = false;
  let useGroupColor = true;
  let showDropLines = true;
  let legendStyle: LegendStyle = "Detailed";
  let showGroup = true;
  let showBase = true;
  let showDelta = false;

  let busy = false;
  let statusMessage = "Ready";
  let statusTone: "neutral" | "error" = "neutral";
  let payloads: PlotResponse[] = [];
  let overlayColorIndex = 0;
  let plotHost: HTMLDivElement;

  function selectOrFirst(current: string, options: string[]): string {
    if (options.length === 0) {
      return "";
    }
    return options.includes(current) ? current : options[0];
  }

  async function renderPlot() {
    if (!plotHost) {
      return;
    }

    const figure = payloads.length > 0 ? buildPlotlyFigure(payloads) : emptyFigure();
    await Plotly.react(plotHost, figure.data, figure.layout, {
      responsive: true,
      displaylogo: false,
    });
  }

  async function refreshSelections() {
    if (!rootPath.trim()) {
      l1Options = [];
      l2Options = [];
      l3Options = [];
      l1 = "";
      l2 = "";
      l3 = "";
      return;
    }

    const rootLevels = await listFolderLevels({ rootPath });
    l1Options = rootLevels.l1Options;
    l1 = selectOrFirst(l1, l1Options);

    if (!l1) {
      l2Options = [];
      l3Options = [];
      l2 = "";
      l3 = "";
      return;
    }

    const secondLevels = await listFolderLevels({ rootPath, l1 });
    l2Options = secondLevels.l2Options;
    l2 = selectOrFirst(l2, l2Options);

    if (!l2) {
      l3Options = [];
      l3 = "";
      return;
    }

    const thirdLevels = await listFolderLevels({ rootPath, l1, l2 });
    l3Options = thirdLevels.l3Options;
    l3 = selectOrFirst(l3, l3Options);
  }

  async function handleL1Change() {
    const secondLevels = await listFolderLevels({ rootPath, l1 });
    l2Options = secondLevels.l2Options;
    l2 = selectOrFirst(l2, l2Options);

    const thirdLevels = await listFolderLevels({ rootPath, l1, l2 });
    l3Options = thirdLevels.l3Options;
    l3 = selectOrFirst(l3, l3Options);
  }

  async function handleL2Change() {
    const thirdLevels = await listFolderLevels({ rootPath, l1, l2 });
    l3Options = thirdLevels.l3Options;
    l3 = selectOrFirst(l3, l3Options);
  }

  function nextGroupColor(): string | null {
    if (!useGroupColor) {
      return null;
    }

    if (!overlay) {
      return COLOR_PALETTE[0];
    }

    return COLOR_PALETTE[overlayColorIndex % COLOR_PALETTE.length];
  }

  function buildRequest(): PlotRequest {
    return {
      rootPath,
      l1,
      l2,
      l3,
      displayMode,
      overlay,
      useGroupColor,
      showDropLines,
      legendStyle,
      showGroup,
      showBase,
      showDelta,
      groupColor: nextGroupColor(),
    };
  }

  async function plotData() {
    if (!l1 || !l2 || !l3) {
      statusTone = "error";
      statusMessage = "Please select all folder levels.";
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
        if (useGroupColor && payload.series.length > 0) {
          overlayColorIndex += 1;
        }
      }

      await renderPlot();
      statusMessage =
        payload.series.length > 0
          ? `Loaded ${payload.series.length} trace(s) from ${payload.title}`
          : "No plottable traces were found in the selected folder.";
    } catch (error) {
      const appError = error as AppError;
      statusTone = "error";
      statusMessage = appError.message ?? "Failed to load or plot data.";
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
      statusMessage = `Folder list refreshed for ${rootPath || "empty path"}`;
    } catch (error) {
      const appError = error as AppError;
      statusTone = "error";
      statusMessage = appError.message ?? "Failed to refresh folder lists.";
    } finally {
      busy = false;
    }
  }

  async function browseRoot() {
    const selected = await open({
      directory: true,
      multiple: false,
      defaultPath: rootPath || DEFAULT_ROOT_PATH,
    });

    if (typeof selected === "string") {
      rootPath = selected;
      await refreshLists();
    }
  }

  async function exportPlot() {
    if (!plotHost || payloads.length === 0) {
      statusTone = "error";
      statusMessage = "Plot something before exporting a PNG.";
      return;
    }

    busy = true;
    try {
      const suggestedName = `${l1 || "plot"}-${l2 || "plot"}-${l3 || "plot"}.png`
        .replace(/\s+/g, "-")
        .toLowerCase();
      const exportPath = await chooseExportPath(suggestedName);
      if (!exportPath) {
        statusTone = "neutral";
        statusMessage = "Export cancelled.";
        return;
      }

      const dataUrl = await Plotly.toImage(plotHost, {
        format: "png",
        width: 1800,
        height: 1000,
        scale: 2,
      });
      await writeFile(exportPath, dataUrlToBytes(dataUrl));
      statusTone = "neutral";
      statusMessage = `Saved plot to ${exportPath}`;
    } catch (error) {
      const appError = error as AppError;
      statusTone = "error";
      statusMessage = appError.message ?? "Failed to export plot.";
    } finally {
      busy = false;
    }
  }

  onMount(async () => {
    await refreshSelections();
    await renderPlot();
  });
</script>

<svelte:head>
  <title>Skin Analysis Desktop</title>
</svelte:head>

<div class="shell">
  <aside class="controls">
    <div class="control-header">
      <p class="eyebrow">Parallel Migration Build</p>
      <h1>Skin Analysis Desktop</h1>
      <p class="subtle">
        Rust/Tauri rewrite that preserves the Python workflow while targeting smaller macOS and
        Windows packages.
      </p>
    </div>

    <section class="card path-card">
      <label for="root-path">Root path</label>
      <div class="path-row">
        <input id="root-path" bind:value={rootPath} disabled={busy} />
        <button class="secondary" on:click={browseRoot} disabled={busy}>Browse</button>
      </div>
      <div class="button-row">
        <button class="secondary" on:click={refreshLists} disabled={busy}>Refresh List</button>
      </div>
    </section>

    <section class="card">
      <label for="l1-select">Step 1: Folder</label>
      <select id="l1-select" bind:value={l1} size="6" on:change={handleL1Change} disabled={busy}>
        {#each l1Options as option}
          <option value={option}>{option}</option>
        {/each}
      </select>

      <label for="l2-select">Step 2: Volume</label>
      <select id="l2-select" bind:value={l2} size="6" on:change={handleL2Change} disabled={busy}>
        {#each l2Options as option}
          <option value={option}>{option}</option>
        {/each}
      </select>

      <label for="l3-select">Step 3: Solution</label>
      <select id="l3-select" bind:value={l3} size="6" disabled={busy}>
        {#each l3Options as option}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </section>

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
    </section>

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

    <section class="card actions">
      <button class="primary" on:click={plotData} disabled={busy}>Load &amp; Plot</button>
      <button class="secondary" on:click={clearPlot} disabled={busy}>Clear Plot</button>
      <button class="secondary" on:click={exportPlot} disabled={busy}>Export Plot</button>
    </section>
  </aside>

  <main class="workspace">
    <div class="workspace-top">
      <div>
        <p class="eyebrow">Status</p>
        <p class:status-error={statusTone === "error"} class="status">{statusMessage}</p>
      </div>
      <div class="legend-chip-row">
        <span class="legend-chip">Python reference retained</span>
        <span class="legend-chip">Parity-test ready</span>
        <span class="legend-chip">macOS + Windows target</span>
      </div>
    </div>

    <section class="plot-card">
      <div bind:this={plotHost} class="plot-host"></div>
    </section>
  </main>
</div>
