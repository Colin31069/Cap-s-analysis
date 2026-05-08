import type { PlotResponse } from "./types";

export type AppTheme = "light" | "dark";

export const COLOR_PALETTE = [
  "#1f77b4",
  "#ff7f0e",
  "#2ca02c",
  "#d62728",
  "#9467bd",
  "#8c564b",
  "#e377c2",
  "#7f7f7f",
  "#bcbd22",
  "#17becf",
];

function mapLineStyle(style: string): string {
  if (style === "--") return "dash";
  if (style === "-.") return "dashdot";
  if (style === ":") return "dot";
  return "solid";
}

const DARK = {
  paper: "#141D2E",
  plot: "#0F172A",
  grid: "#1E293B",
  zero: "#2D3F5A",
  font: "#94A3B8",
  legendBg: "rgba(20,29,46,0.92)",
  legendBorder: "#253450",
};

const LIGHT = {
  paper: "#FFFFFF",
  plot: "#F8FAFC",
  grid: "#E2E8F0",
  zero: "#CBD5E1",
  font: "#475569",
  legendBg: "rgba(255,255,255,0.96)",
  legendBorder: "#CBD5E1",
};

function plotTheme(theme: AppTheme) {
  return theme === "dark" ? DARK : LIGHT;
}

export function emptyFigure(theme: AppTheme = "dark") {
  const t = plotTheme(theme);
  return {
    data: [],
    layout: {
      title: { text: "Ready", font: { color: t.font } },
      paper_bgcolor: t.paper,
      plot_bgcolor: t.plot,
      font: { family: "-apple-system, 'Segoe UI', system-ui, sans-serif", color: t.font },
      xaxis: {
        title: "Time relative to drop (s)",
        gridcolor: t.grid,
        zerolinecolor: t.zero,
        color: t.font,
      },
      yaxis: {
        title: "Value",
        gridcolor: t.grid,
        zerolinecolor: t.zero,
        color: t.font,
      },
      margin: { l: 70, r: 220, t: 70, b: 70 },
      legend: {
        x: 1.02,
        y: 1,
        xanchor: "left",
        yanchor: "top",
        bgcolor: t.legendBg,
        bordercolor: t.legendBorder,
        borderwidth: 1,
        font: { color: t.font, size: 11 },
      },
    },
  };
}

export function buildPlotlyFigure(payloads: PlotResponse[], theme: AppTheme = "dark") {
  if (payloads.length === 0) return emptyFigure(theme);

  const t = plotTheme(theme);
  const data: Record<string, unknown>[] = [];
  const shapes: Record<string, unknown>[] = [];
  const latest = payloads[payloads.length - 1];
  const title = payloads.length > 1 && latest.settings.overlay ? "Overlay View" : latest.title;

  for (const payload of payloads) {
    for (const series of payload.series) {
      const isGroupLegend = series.sampleName === "__group_legend__";
      const isNoLegend = series.legendLabel === "_nolegend_";
      const traceColor = series.color ?? COLOR_PALETTE[0];

      if (isGroupLegend) {
        data.push({
          type: "scatter",
          mode: "markers",
          x: [null],
          y: [null],
          name: series.legendLabel,
          marker: { color: traceColor, size: 14, symbol: "square" },
          showlegend: true,
        });
        continue;
      }

      data.push({
        type: "scatter",
        mode: "lines",
        x: series.x,
        y: series.y,
        name: isNoLegend ? "" : series.legendLabel,
        showlegend: !isNoLegend,
        line: {
          color: traceColor,
          dash: mapLineStyle(series.lineStyle),
          width: 2,
        },
        hovertemplate: `${series.legendLabel}<br>t=%{x:.2f}s<br>Value=%{y:.3f}<extra></extra>`,
      });

      if (payload.settings.displayMode !== "Base" && payload.settings.showDropLines) {
        shapes.push({
          type: "line",
          x0: 0,
          x1: 0,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: { color: traceColor, dash: "dash", width: 1 },
          opacity: 0.35,
        });
      }
    }
  }

  const seenShapes = new Set<string>();
  const uniqueShapes = shapes.filter((s) => {
    const key = JSON.stringify(s);
    if (seenShapes.has(key)) return false;
    seenShapes.add(key);
    return true;
  });

  return {
    data,
    layout: {
      title: { text: title, font: { color: t.font } },
      paper_bgcolor: t.paper,
      plot_bgcolor: t.plot,
      font: { family: "-apple-system, 'Segoe UI', system-ui, sans-serif", color: t.font },
      xaxis: {
        title: { text: "Time relative to drop (s)", font: { color: t.font } },
        gridcolor: t.grid,
        zerolinecolor: t.zero,
        zeroline: true,
        color: t.font,
        linecolor: t.grid,
      },
      yaxis: {
        title: { text: latest.yUnit, font: { color: t.font } },
        gridcolor: t.grid,
        zerolinecolor: t.zero,
        color: t.font,
        linecolor: t.grid,
      },
      shapes: uniqueShapes,
      showlegend: true,
      legend: {
        x: 1.02,
        y: 1,
        xanchor: "left",
        yanchor: "top",
        bgcolor: t.legendBg,
        bordercolor: t.legendBorder,
        borderwidth: 1,
        font: { size: 11, color: t.font },
      },
      margin: { l: 70, r: 260, t: 70, b: 70 },
    },
  };
}

export function dataUrlToBytes(dataUrl: string): Uint8Array {
  const encoded = dataUrl.split(",", 2)[1] ?? "";
  return Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
}
