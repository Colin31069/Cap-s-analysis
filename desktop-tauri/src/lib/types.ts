export type DisplayMode = "Norm" | "Raw" | "Base";
export type LegendStyle = "Simple" | "Detailed";

// ── Folder navigation ──────────────────────────────────────────────────────────

export interface FolderLevelsRequest {
  rootPath: string;
}

export interface FolderLevelsResponse {
  experimentOptions: string[];
}

// ── Metadata ───────────────────────────────────────────────────────────────────

export interface MedicineEntry {
  name: string;
  dose: string;
}

export interface ExcludedSample {
  fileName: string;
  reason: string;
  method: string;
}

export interface ExperimentMetadata {
  medicineCount: number;
  medicines: MedicineEntry[];
  excludedSamples: ExcludedSample[];
}

export interface SaveMetadataRequest {
  folderPath: string;
  metadata: ExperimentMetadata;
}

// ── Sample list ────────────────────────────────────────────────────────────────

export interface SampleInfo {
  fileName: string;
  sampleName: string;
  included: boolean;
  reason: string;
  method: string;
}

export interface ListSamplesResponse {
  samples: SampleInfo[];
  maxExclusions: number;
  currentExclusions: number;
  dixonExceptionAvailable: boolean;
  metadata: ExperimentMetadata;
}

// ── Plot ───────────────────────────────────────────────────────────────────────

export interface PlotRequest {
  rootPath: string;
  experimentName: string;
  displayMode: DisplayMode;
  overlay: boolean;
  useGroupColor: boolean;
  showDropLines: boolean;
  legendStyle: LegendStyle;
  showGroup: boolean;
  showBase: boolean;
  showDelta: boolean;
  groupColor: string | null;
  baselineDurationSec?: number | null;
  drugApplyTimeSec?: number | null;
  drugApplyToleranceSec?: number | null;
  baselineWarningThresholdPct?: number | null;
  customTitle?: string;
}

export interface PlotSeries {
  sampleName: string;
  x: number[];
  y: number[];
  dropTime: number;
  lineStyle: string;
  color: string | null;
  legendLabel: string;
  baselineWarningStatus: string;
  timingWarningDetails: string[];
  dropDetectionSource: string;
}

export interface PlotResponse {
  title: string;
  yUnit: string;
  series: PlotSeries[];
  settings: PlotRequest;
  baselineWarningCount: number;
  timingWarningCount: number;
}

// ── Statistics ─────────────────────────────────────────────────────────────────

export interface StatisticsRequest {
  rootPath: string;
  baselineDurationSec: number;
  drugApplyTimeSec: number;
  drugApplyToleranceSec: number;
  baselineWarningThresholdPct: number;
}

export interface StatisticsResponse {
  text: string;
  csv: string;
}

// ── Error ──────────────────────────────────────────────────────────────────────

export interface AppError {
  code: string;
  message: string;
}
