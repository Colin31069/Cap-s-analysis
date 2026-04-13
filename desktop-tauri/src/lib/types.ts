export type DisplayMode = "Norm" | "Raw" | "Base";
export type LegendStyle = "Simple" | "Detailed";

export interface FolderLevelsRequest {
  rootPath: string;
  l1?: string | null;
  l2?: string | null;
}

export interface FolderLevelsResponse {
  l1Options: string[];
  l2Options: string[];
  l3Options: string[];
}

export interface PlotRequest {
  rootPath: string;
  l1: string;
  l2: string;
  l3: string;
  displayMode: DisplayMode;
  overlay: boolean;
  useGroupColor: boolean;
  showDropLines: boolean;
  legendStyle: LegendStyle;
  showGroup: boolean;
  showBase: boolean;
  showDelta: boolean;
  groupColor: string | null;
}

export interface PlotSeries {
  sampleName: string;
  x: number[];
  y: number[];
  dropTime: number;
  lineStyle: string;
  color: string | null;
  legendLabel: string;
}

export interface PlotResponse {
  title: string;
  yUnit: string;
  series: PlotSeries[];
  settings: PlotRequest;
}

export interface AppError {
  code: string;
  message: string;
}
