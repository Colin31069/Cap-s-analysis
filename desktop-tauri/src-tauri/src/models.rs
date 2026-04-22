use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppError {
    pub code: String,
    pub message: String,
}

impl AppError {
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for AppError {
    fn from(error: std::io::Error) -> Self {
        Self::new("io_error", error.to_string())
    }
}

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
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PlotResponse {
    pub title: String,
    pub y_unit: String,
    pub series: Vec<PlotSeries>,
    pub settings: PlotRequest,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProcessedSignal {
    pub time_sec: Vec<f64>,
    pub capacitance: Vec<f64>,
    pub drop_time: f64,
    pub delta_capacitance: f64,
    pub initial_avg: f64,
}
