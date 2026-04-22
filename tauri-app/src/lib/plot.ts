import type { PlotResponse } from "./types";

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
  if (style === "--") {
    return "dash";
  }
  if (style === "-.") {
    return "dashdot";
  }
  if (style === ":") {
    return "dot";
  }
  return "solid";
}

export function emptyFigure() {
  return {
    data: [],
    layout: {
      title: "Ready",
      paper_bgcolor: "#fffdf8",
      plot_bgcolor: "#fffdf8",
      xaxis: { title: "Time (s)", gridcolor: "#d7d0c4" },
      yaxis: { title: "Value", gridcolor: "#d7d0c4" },
      margin: { l: 70, r: 220, t: 70, b: 70 },
      legend: { x: 1.02, y: 1, xanchor: "left", yanchor: "top" },
    },
  };
}

export function buildPlotlyFigure(payloads: PlotResponse[]) {
  if (payloads.length === 0) {
    return emptyFigure();
  }

  const data: Record<string, unknown>[] = [];
  const shapes: Record<string, unknown>[] = [];
  const latest = payloads[payloads.length - 1];
  const title = payloads.length > 1 && latest.settings.overlay ? "Overlay View" : latest.title;

  for (const payload of payloads) {
    for (const series of payload.series) {
      const traceColor = series.color ?? COLOR_PALETTE[0];
      data.push({
        type: "scatter",
        mode: "lines",
        x: series.x,
        y: series.y,
        name: series.legendLabel,
        line: {
          color: traceColor,
          dash: mapLineStyle(series.lineStyle),
          width: 2,
        },
        hovertemplate: `${series.legendLabel}<br>Time=%{x:.2f}s<br>Value=%{y:.3f}<extra></extra>`,
      });

      if (payload.settings.displayMode !== "Base" && payload.settings.showDropLines) {
        shapes.push({
          type: "line",
          x0: series.dropTime,
          x1: series.dropTime,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: {
            color: traceColor,
            dash: "dash",
            width: 1,
          },
          opacity: 0.35,
        });
      }
    }
  }

  return {
    data,
    layout: {
      title,
      paper_bgcolor: "#fffdf8",
      plot_bgcolor: "#fffdf8",
      font: {
        family: "Avenir Next, Helvetica Neue, sans-serif",
        color: "#30271c",
      },
      xaxis: {
        title: "Time (s)",
        gridcolor: "#d7d0c4",
        zerolinecolor: "#c3b8a5",
      },
      yaxis: {
        title: latest.yUnit,
        gridcolor: "#d7d0c4",
        zerolinecolor: "#c3b8a5",
      },
      shapes,
      showlegend: true,
      legend: {
        x: 1.02,
        y: 1,
        xanchor: "left",
        yanchor: "top",
        bgcolor: "rgba(255,253,248,0.85)",
        bordercolor: "#dfd6c6",
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
