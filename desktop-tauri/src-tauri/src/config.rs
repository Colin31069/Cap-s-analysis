pub const DEFAULT_ROOT_PATH: &str = "/Users/k/Downloads/20260303";
pub const DATA_COL: &str = "pF - Plot 0";
pub const DT_SEC: f64 = 0.1;
pub const INITIAL_BASELINE_POINTS: usize = 200;

pub const DEFAULT_BASELINE_DURATION_SEC: f64 = 20.0;
pub const DEFAULT_DRUG_APPLY_TIME_SEC: f64 = 25.0;
pub const DEFAULT_DRUG_APPLY_TOLERANCE_SEC: f64 = 5.0;
pub const DEFAULT_BASELINE_WARNING_THRESHOLD_PCT: f64 = 2.0;
pub const DROP_SIGMA_THRESHOLD: f64 = 3.0;
pub const LEGACY_DROP_SEARCH_POINTS: usize = 500;

pub const BASELINE_TAIL_POINTS: usize = 20;
pub const BASELINE_RISE_ROLLING_POINTS: usize = 5;
pub const BASELINE_RISE_MIN_RUN: usize = 10;

pub const COLOR_PALETTE: [&str; 10] = [
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
pub const LINE_STYLE_CYCLE: [&str; 4] = ["-", "--", "-.", ":"];

pub const METADATA_FILENAME: &str = ".skin_analysis_metadata.json";
pub const MAX_MEDICINES: usize = 5;
pub const DEFAULT_MEDICINE_COUNT: usize = 1;

pub const OUTLIER_MIN_GROUP_N: usize = 5;
pub const OUTLIER_MODIFIED_Z_THRESHOLD: f64 = 3.5;
pub const MODIFIED_Z_SCORE_SCALE: f64 = 0.6745;
pub const MAD_EPSILON: f64 = 1e-12;

pub const DIXON_Q_ALPHA: f64 = 0.05;
pub const DIXON_Q_MIN_N: usize = 3;
pub const DIXON_Q_MAX_N: usize = 10;
pub const DIXON_Q_CRITICAL_VALUES: [(usize, f64); 8] = [
    (3, 0.970),
    (4, 0.829),
    (5, 0.710),
    (6, 0.625),
    (7, 0.568),
    (8, 0.526),
    (9, 0.493),
    (10, 0.466),
];
pub const DIXON_Q_EXCLUSION_METHOD: &str = "dixon_q";
