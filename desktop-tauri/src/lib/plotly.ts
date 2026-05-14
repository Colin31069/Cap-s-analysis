export interface PlotlyApi {
  react: (
    root: HTMLElement,
    data: unknown[],
    layout: Record<string, unknown>,
    config?: Record<string, unknown>,
  ) => Promise<unknown>;
  toImage: (root: HTMLElement, options: Record<string, unknown>) => Promise<string>;
  purge?: (root: HTMLElement) => void;
}

declare global {
  interface Window {
    Plotly?: PlotlyApi;
  }
}

const PLOTLY_SCRIPT_ID = "plotly-vendor-script";

let plotlyPromise: Promise<PlotlyApi> | null = null;

export function isPlotlyLoaded(): boolean {
  return Boolean(window.Plotly);
}

export function loadPlotly(): Promise<PlotlyApi> {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (plotlyPromise) return plotlyPromise;

  plotlyPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById(PLOTLY_SCRIPT_ID) as HTMLScriptElement | null;

    const finish = () => {
      if (window.Plotly) {
        resolve(window.Plotly);
      } else {
        plotlyPromise = null;
        reject(new Error("Plotly loaded without exposing window.Plotly."));
      }
    };

    if (existing) {
      if (existing.dataset.loaded === "true") {
        finish();
        return;
      }
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener(
        "error",
        () => {
          plotlyPromise = null;
          existing.remove();
          reject(new Error("Failed to load Plotly vendor asset."));
        },
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = PLOTLY_SCRIPT_ID;
    script.src = "/vendor/plotly.min.js";
    script.async = true;
    script.onload = () => {
      script.dataset.loaded = "true";
      finish();
    };
    script.onerror = () => {
      plotlyPromise = null;
      script.remove();
      reject(new Error("Failed to load Plotly vendor asset."));
    };
    document.head.appendChild(script);
  });

  return plotlyPromise;
}
