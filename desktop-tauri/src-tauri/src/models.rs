use serde::{Deserialize, Serialize};

// ── Error ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppError {
    pub code: String,
    pub message: String,
}

impl AppError {
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self { code: code.into(), message: message.into() }
    }
}

impl From<std::io::Error> for AppError {
    fn from(error: std::io::Error) -> Self {
        Self::new("io_error", error.to_string())
    }
}

// ── Analysis params & signal ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AnalysisParams {
    pub baseline_duration_sec: f64,
    pub drug_apply_time_sec: f64,
    pub drug_apply_tolerance_sec: f64,
    pub baseline_warning_threshold_pct: f64,
}

impl Default for AnalysisParams {
    fn default() -> Self {
        use crate::config::{
            DEFAULT_BASELINE_DURATION_SEC, DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
            DEFAULT_DRUG_APPLY_TIME_SEC, DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
        };
        Self {
            baseline_duration_sec: DEFAULT_BASELINE_DURATION_SEC,
            drug_apply_time_sec: DEFAULT_DRUG_APPLY_TIME_SEC,
            drug_apply_tolerance_sec: DEFAULT_DRUG_APPLY_TOLERANCE_SEC,
            baseline_warning_threshold_pct: DEFAULT_BASELINE_WARNING_THRESHOLD_PCT,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProcessedSignal {
    pub time_sec: Vec<f64>,
    pub capacitance: Vec<f64>,
    pub drop_time: f64,
    pub delta_capacitance: f64,
    pub initial_avg: f64,
    pub effective_baseline_points: usize,
    pub effective_baseline_duration_sec: f64,
    pub baseline_was_auto_shortened: bool,
    pub drop_detection_source: String,
    pub drop_search_fallback_used: bool,
    pub timing_warning_details: Vec<String>,
    pub baseline_warning_status: String,
    pub baseline_tail_offset_pct: f64,
    pub baseline_rise_offset_pct: f64,
    pub baseline_tail_warning_hit: bool,
    pub baseline_rise_warning_hit: bool,
}

// ── Metadata ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct MedicineEntry {
    pub name: String,
    pub dose: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ExcludedSample {
    pub file_name: String,
    pub reason: String,
    #[serde(default)]
    pub method: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ExperimentMetadata {
    pub medicine_count: usize,
    pub medicines: Vec<MedicineEntry>,
    pub excluded_samples: Vec<ExcludedSample>,
}

// ── Folder navigation ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct FolderLevelsRequest {
    pub root_path: String,
    pub l1: Option<String>,
    pub l2: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct FolderLevelsResponse {
    pub l1_options: Vec<String>,
    pub l2_options: Vec<String>,
    pub l3_options: Vec<String>,
}

// ── Sample list ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct SampleInfo {
    pub file_name: String,
    pub sample_name: String,
    pub included: bool,
    pub reason: String,
    pub method: String,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ListSamplesResponse {
    pub samples: Vec<SampleInfo>,
    pub max_exclusions: usize,
    pub current_exclusions: usize,
    pub dixon_exception_available: bool,
    pub metadata: ExperimentMetadata,
}

// ── Plot request/response ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PlotRequest {
    pub root_path: String,
    pub l1: String,
    pub l2: String,
    pub l3: String,
    pub display_mode: String,
    pub overlay: bool,
    pub use_group_color: bool,
    pub show_drop_lines: bool,
    pub legend_style: String,
    pub show_group: bool,
    pub show_base: bool,
    pub show_delta: bool,
    pub group_color: Option<String>,
    #[serde(default)]
    pub baseline_duration_sec: Option<f64>,
    #[serde(default)]
    pub drug_apply_time_sec: Option<f64>,
    #[serde(default)]
    pub drug_apply_tolerance_sec: Option<f64>,
    #[serde(default)]
    pub baseline_warning_threshold_pct: Option<f64>,
    #[serde(default)]
    pub custom_title: String,
}

impl PlotRequest {
    pub fn analysis_params(&self) -> AnalysisParams {
        let defaults = AnalysisParams::default();
        AnalysisParams {
            baseline_duration_sec: self.baseline_duration_sec.unwrap_or(defaults.baseline_duration_sec),
            drug_apply_time_sec: self.drug_apply_time_sec.unwrap_or(defaults.drug_apply_time_sec),
            drug_apply_tolerance_sec: self
                .drug_apply_tolerance_sec
                .unwrap_or(defaults.drug_apply_tolerance_sec),
            baseline_warning_threshold_pct: self
                .baseline_warning_threshold_pct
                .unwrap_or(defaults.baseline_warning_threshold_pct),
        }
    }
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PlotSeries {
    pub sample_name: String,
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub drop_time: f64,
    pub line_style: String,
    pub color: Option<String>,
    pub legend_label: String,
    pub baseline_warning_status: String,
    pub timing_warning_details: Vec<String>,
    pub drop_detection_source: String,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PlotResponse {
    pub title: String,
    pub y_unit: String,
    pub series: Vec<PlotSeries>,
    pub settings: PlotRequest,
    pub baseline_warning_count: usize,
    pub timing_warning_count: usize,
}

// ── Statistics ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct StatisticsRequest {
    pub root_path: String,
    pub l1: String,
    pub l2: String,
    pub baseline_duration_sec: f64,
    pub drug_apply_time_sec: f64,
    pub drug_apply_tolerance_sec: f64,
    pub baseline_warning_threshold_pct: f64,
}

impl StatisticsRequest {
    pub fn analysis_params(&self) -> AnalysisParams {
        AnalysisParams {
            baseline_duration_sec: self.baseline_duration_sec,
            drug_apply_time_sec: self.drug_apply_time_sec,
            drug_apply_tolerance_sec: self.drug_apply_tolerance_sec,
            baseline_warning_threshold_pct: self.baseline_warning_threshold_pct,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StatisticsResponse {
    pub text: String,
    pub csv: String,
}

// ── Metadata commands ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveMetadataRequest {
    pub folder_path: String,
    pub metadata: ExperimentMetadata,
}
