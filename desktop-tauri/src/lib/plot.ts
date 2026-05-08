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

function plotTheme(theme: AppTheme) {
  if (theme === "dark") {
    return {
      background: "#191713",
      grid: "#3a352d",
      zeroLine: "#5d5347",
      text: "#f1e9dc",
      legendBackground: "rgba(25,23,19,0.88)",
      legendBorder: "#4b4338",
    };
  }

  return {
    background: "#fffdf8",
    grid: "#d7d0c4",
    zeroLine: "#c3b8a5",
    text: "#30271c",
    legendBackground: "rgba(255,253,248,0.85)",
    legendBorder: "#dfd6c6",
  };
}

export function emptyFigure(theme: AppTheme = "light") {
  const colors = plotTheme(theme);
  return {
    data: [],
    layout: {
      title: "Ready",
      paper_bgcolor: colors.background,
      plot_bgcolor: colors.background,
      font: { family: "Avenir Next, Helvetica Neue, sans-serif", color: colors.text },
      xaxis: { title: "Time relative to drop (s)", gridcolor: colors.grid, zerolinecolor: colors.zeroLine },
      yaxis: { title: "Value", gridcolor: colors.grid, zerolinecolor: colors.zeroLine },
      margin: { l: 70, r: 220, t: 70, b: 70 },
      legend: { x: 1.02, y: 1, xanchor: "left", yanchor: "top", bgcolor: colors.legendBackground },
    },
  };
}

export function buildPlotlyFigure(payloads: PlotResponse[], theme: AppTheme = "light") {
  if (payloads.length === 0) return emptyFigure(theme);

  const colors = plotTheme(theme);
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
        // Invisible marker trace just to put a colored swatch in the legend
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

      // Drop lines at x=0 because time is now drop-aligned
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

  // Deduplicate vertical drop lines at x=0
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
      title,
      paper_bgcolor: colors.background,
      plot_bgcolor: colors.background,
      font: { family: "Avenir Next, Helvetica Neue, sans-serif", color: colors.text },
      xaxis: {
        title: "Time relative to drop (s)",
        gridcolor: colors.grid,
        zerolinecolor: colors.zeroLine,
        zeroline: true,
      },
      yaxis: {
        title: latest.yUnit,
        gridcolor: colors.grid,
        zerolinecolor: colors.zeroLine,
      },
      shapes: uniqueShapes,
      showlegend: true,
      legend: {
        x: 1.02,
        y: 1,
        xanchor: "left",
        yanchor: "top",
        bgcolor: colors.legendBackground,
        bordercolor: colors.legendBorder,
        borderwidth: 1,
        font: { size: 11 },
      },
      margin: { l: 70, r: 260, t: 70, b: 70 },
    },
  };
}

export function dataUrlToBytes(dataUrl: string): Uint8Array {
  const encoded = dataUrl.split(",", 2)[1] ?? "";
  return Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
}
