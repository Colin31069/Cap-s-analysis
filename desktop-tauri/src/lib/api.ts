import { invoke } from "@tauri-apps/api/core";

import type {
  ExperimentMetadata,
  FolderLevelsRequest,
  FolderLevelsResponse,
  ListSamplesResponse,
  PlotRequest,
  PlotResponse,
  SaveMetadataRequest,
  StatisticsRequest,
  StatisticsResponse,
} from "./types";

export function listFolderLevels(request: FolderLevelsRequest): Promise<FolderLevelsResponse> {
  return invoke("list_folder_levels", { request });
}

export function loadMetadata(folderPath: string): Promise<ExperimentMetadata> {
  return invoke("load_metadata", { folderPath });
}

export function saveMetadata(request: SaveMetadataRequest): Promise<void> {
  return invoke("save_metadata", { request });
}

export function listSamplesInFolder(
  rootPath: string,
  l1: string,
  l2: string,
  l3: string,
): Promise<ListSamplesResponse> {
  return invoke("list_samples_in_folder", { rootPath, l1, l2, l3 });
}

export function buildPlotPayload(request: PlotRequest): Promise<PlotResponse> {
  return invoke("build_plot_payload", { request });
}

export function runStatistics(request: StatisticsRequest): Promise<StatisticsResponse> {
  return invoke("run_statistics", { request });
}

export function chooseExportPath(suggestedName?: string): Promise<string | null> {
  return invoke("choose_export_path", { suggestedName });
}

export function chooseCsvExportPath(suggestedName?: string): Promise<string | null> {
  return invoke("choose_csv_export_path", { suggestedName });
}
