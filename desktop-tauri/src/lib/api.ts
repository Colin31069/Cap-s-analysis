import { invoke } from "@tauri-apps/api/core";

import type { FolderLevelsRequest, FolderLevelsResponse, PlotRequest, PlotResponse } from "./types";

export function listFolderLevels(request: FolderLevelsRequest): Promise<FolderLevelsResponse> {
  return invoke("list_folder_levels", { request });
}

export function buildPlotPayload(request: PlotRequest): Promise<PlotResponse> {
  return invoke("build_plot_payload", { request });
}

export function chooseExportPath(suggestedName?: string): Promise<string | null> {
  return invoke("choose_export_path", { suggestedName });
}
