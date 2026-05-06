use std::path::Path;

use statrs::distribution::{ContinuousCDF, FisherSnedecor, StudentsT};

use crate::analysis::process_single_file;
use crate::config::{
    DIXON_Q_ALPHA, DIXON_Q_CRITICAL_VALUES, DIXON_Q_MAX_N, DIXON_Q_MIN_N, MAD_EPSILON,
    MODIFIED_Z_SCORE_SCALE, OUTLIER_MIN_GROUP_N, OUTLIER_MODIFIED_Z_THRESHOLD,
};
use crate::exclusions::current_excluded_samples;
use crate::filesystem::list_xlsx_files;
use crate::metadata::load_experiment_metadata;
use crate::models::{AnalysisParams, ExcludedSample};

// ── Data structures ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StatisticalSample {
    pub group_name: String,
    pub sample_name: String,
    pub file_name: String,
    pub delta_percent: f64,
    pub delta_capacitance: f64,
    pub baseline: f64,
    pub drop_time: f64,
    pub baseline_warning_status: String,
    pub drop_detection_source: String,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct StatisticalExclusion {
    pub group_name: String,
    pub file_name: String,
    pub reason: String,
    pub method: String,
}

#[derive(Debug, Clone)]
pub struct GroupStatistics {
    pub group_name: String,
    pub n: usize,
    pub mean: f64,
    pub sd: f64,
    pub sem: f64,
    pub median: f64,
    pub q1: f64,
    pub q3: f64,
    pub iqr: f64,
    pub ci95_low: f64,
    pub ci95_high: f64,
    pub normality_note: String,
}

#[derive(Debug, Clone)]
pub struct VarianceCheckResult {
    pub method: String,
    pub statistic: f64,
    pub p_value: f64,
    pub note: String,
}

#[derive(Debug, Clone)]
pub struct AnovaResult {
    pub method: String,
    pub group_count: usize,
    pub sample_count: usize,
    pub statistic: f64,
    pub df_num: f64,
    pub df_den: f64,
    pub p_value: f64,
    pub eta_squared: f64,
    pub omega_squared: f64,
    pub note: String,
}

#[derive(Debug, Clone)]
pub struct DixonQRecommendation {
    pub group_name: String,
    pub sample_name: String,
    pub file_name: String,
    pub side: String,
    pub delta_percent: f64,
    pub nearest_delta_percent: f64,
    pub gap_delta_percent: f64,
    pub range_delta_percent: f64,
    pub q_statistic: f64,
    pub critical_value: f64,
    pub alpha: f64,
    pub warnings: Vec<String>,
    pub note: String,
}

#[derive(Debug, Clone)]
pub struct OutlierCandidate {
    pub group_name: String,
    pub sample_name: String,
    pub delta_percent: f64,
    pub peer_median: f64,
    pub peer_mad: f64,
    pub delta_from_peer_median: f64,
    pub modified_z_score: f64,
    pub warnings: Vec<String>,
    pub note: String,
}

pub struct StatisticalAnalysisResult {
    pub root_path: String,
    pub samples: Vec<StatisticalSample>,
    pub excluded_samples: Vec<StatisticalExclusion>,
    pub group_statistics: Vec<GroupStatistics>,
    pub variance_check: VarianceCheckResult,
    pub anova: AnovaResult,
    pub dixon_recommendations: Vec<DixonQRecommendation>,
    pub dixon_review_notes: Vec<String>,
    pub dixon_sensitivity_anova: Option<AnovaResult>,
    pub outlier_candidates: Vec<OutlierCandidate>,
    pub outlier_review_notes: Vec<String>,
    pub warnings: Vec<String>,
}

// ── Numeric helpers ────────────────────────────────────────────────────────────

fn nan() -> f64 {
    f64::NAN
}
fn is_finite(v: f64) -> bool {
    v.is_finite()
}
fn fmt_f(v: f64) -> String {
    if !is_finite(v) { "NA".to_string() } else { format!("{v:.4}") }
}

fn sorted_finite(values: &[f64]) -> Vec<f64> {
    let mut v: Vec<f64> = values.iter().copied().filter(|x| x.is_finite()).collect();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v
}

fn arr_mean(values: &[f64]) -> f64 {
    if values.is_empty() { return nan(); }
    values.iter().sum::<f64>() / values.len() as f64
}

fn arr_std(values: &[f64]) -> f64 {
    if values.len() < 2 { return nan(); }
    let m = arr_mean(values);
    let var = values.iter().map(|v| (v - m).powi(2)).sum::<f64>() / (values.len() - 1) as f64;
    var.sqrt()
}

fn percentile_linear(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() { return nan(); }
    let index = p / 100.0 * (sorted.len() - 1) as f64;
    let lo = index.floor() as usize;
    let hi = index.ceil() as usize;
    if lo == hi { return sorted[lo]; }
    let frac = index - lo as f64;
    sorted[lo] * (1.0 - frac) + sorted[hi] * frac
}

fn arr_median(sorted: &[f64]) -> f64 {
    percentile_linear(sorted, 50.0)
}

fn t_quantile(df: f64, p: f64) -> f64 {
    StudentsT::new(0.0, 1.0, df).ok().map(|d| d.inverse_cdf(p)).unwrap_or(nan())
}

fn f_sf(statistic: f64, df1: f64, df2: f64) -> f64 {
    if !statistic.is_finite() || statistic <= 0.0 { return nan(); }
    FisherSnedecor::new(df1, df2).ok().map(|d| 1.0 - d.cdf(statistic)).unwrap_or(nan())
}

fn dixon_critical_value(n: usize) -> Option<f64> {
    DIXON_Q_CRITICAL_VALUES.iter().find(|(k, _)| *k == n).map(|(_, v)| *v)
}

// ── Group summary ──────────────────────────────────────────────────────────────

pub fn summarize_group(group_name: &str, values: &[f64]) -> GroupStatistics {
    let sorted = sorted_finite(values);
    let n = sorted.len();
    if n == 0 {
        return GroupStatistics {
            group_name: group_name.to_string(),
            n: 0,
            mean: nan(), sd: nan(), sem: nan(), median: nan(),
            q1: nan(), q3: nan(), iqr: nan(), ci95_low: nan(), ci95_high: nan(),
            normality_note: "No valid samples.".to_string(),
        };
    }
    let mean = arr_mean(&sorted);
    let sd = arr_std(&sorted);
    let sem = if n >= 2 && is_finite(sd) { sd / (n as f64).sqrt() } else { nan() };
    let median = arr_median(&sorted);
    let q1 = percentile_linear(&sorted, 25.0);
    let q3 = percentile_linear(&sorted, 75.0);
    let iqr = q3 - q1;
    let (ci95_low, ci95_high) = if n >= 2 && is_finite(sem) {
        let t = t_quantile((n - 1) as f64, 0.975);
        if is_finite(t) { (mean - t * sem, mean + t * sem) } else { (nan(), nan()) }
    } else {
        (nan(), nan())
    };
    let normality_note = if n < 3 {
        "Shapiro-Wilk not available (n < 3).".to_string()
    } else {
        "Shapiro-Wilk not available in Tauri version.".to_string()
    };
    GroupStatistics {
        group_name: group_name.to_string(),
        n, mean, sd, sem, median, q1, q3, iqr, ci95_low, ci95_high,
        normality_note,
    }
}

// ── One-way ANOVA ──────────────────────────────────────────────────────────────

fn group_values_for_anova<'a>(
    group_stats: &[GroupStatistics],
    samples: &'a [StatisticalSample],
) -> Vec<Vec<f64>> {
    group_stats
        .iter()
        .filter(|g| g.n >= 2)
        .map(|g| {
            samples
                .iter()
                .filter(|s| s.group_name == g.group_name && is_finite(s.delta_percent))
                .map(|s| s.delta_percent)
                .collect()
        })
        .collect()
}

fn classical_anova_effects(group_values: &[Vec<f64>]) -> (f64, f64, f64, f64, f64, f64) {
    let valid: Vec<&Vec<f64>> = group_values.iter().filter(|g| !g.is_empty()).collect();
    if valid.len() < 2 { return (nan(), nan(), nan(), nan(), nan(), nan()); }
    let all: Vec<f64> = valid.iter().flat_map(|g| g.iter().copied()).collect();
    let n_total = all.len();
    let k = valid.len();
    if n_total <= k { return (nan(), nan(), nan(), nan(), nan(), nan()); }
    let grand_mean = arr_mean(&all);
    let ss_between: f64 = valid.iter().map(|g| g.len() as f64 * (arr_mean(g) - grand_mean).powi(2)).sum();
    let ss_within: f64 = valid.iter().map(|g| {
        let gm = arr_mean(g);
        g.iter().map(|v| (v - gm).powi(2)).sum::<f64>()
    }).sum();
    let ss_total = ss_between + ss_within;
    let df_between = (k - 1) as f64;
    let df_within = (n_total - k) as f64;
    let ms_within = if df_within > 0.0 { ss_within / df_within } else { nan() };
    let eta_squared = if ss_total > 0.0 { ss_between / ss_total } else { nan() };
    let omega_squared = if ss_total > 0.0 && is_finite(ms_within) {
        ((ss_between - df_between * ms_within) / (ss_total + ms_within)).max(0.0)
    } else { nan() };
    (ss_between, ss_within, df_between, df_within, eta_squared, omega_squared)
}

pub fn compute_one_way_anova(
    group_stats: &[GroupStatistics],
    samples: &[StatisticalSample],
    method: &str,
) -> AnovaResult {
    let group_values = group_values_for_anova(group_stats, samples);
    let total_n: usize = group_values.iter().map(|g| g.len()).sum();
    let k = group_values.len();
    let (ss_between, ss_within, df_between, df_within, eta_squared, omega_squared) =
        classical_anova_effects(&group_values);

    if k < 2 || total_n <= k {
        return AnovaResult {
            method: method.to_string(),
            group_count: k,
            sample_count: total_n,
            statistic: nan(), df_num: df_between, df_den: df_within,
            p_value: nan(), eta_squared, omega_squared,
            note: "ANOVA not run because at least two groups need n >= 2.".to_string(),
        };
    }
    let ms_between = ss_between / df_between;
    let ms_within = ss_within / df_within;
    let (statistic, p_value, note) = if ms_within <= 0.0 {
        (nan(), nan(), "ANOVA not run because within-group variance is zero.".to_string())
    } else {
        let f = ms_between / ms_within;
        let p = f_sf(f, df_between, df_within);
        (f, p, "Classical one-way ANOVA.".to_string())
    };
    AnovaResult {
        method: method.to_string(),
        group_count: k,
        sample_count: total_n,
        statistic, df_num: df_between, df_den: df_within,
        p_value, eta_squared, omega_squared, note,
    }
}

// ── Brown-Forsythe variance check ─────────────────────────────────────────────

pub fn compute_variance_check(
    group_stats: &[GroupStatistics],
    samples: &[StatisticalSample],
) -> VarianceCheckResult {
    let group_values = group_values_for_anova(group_stats, samples);
    if group_values.len() < 2 {
        return VarianceCheckResult {
            method: "Brown-Forsythe".to_string(),
            statistic: nan(), p_value: nan(),
            note: "Variance check not run because at least two groups need n >= 2.".to_string(),
        };
    }
    let abs_dev_groups: Vec<Vec<f64>> = group_values
        .iter()
        .map(|g| {
            let sorted = { let mut v = g.clone(); v.sort_by(|a, b| a.partial_cmp(b).unwrap()); v };
            let med = arr_median(&sorted);
            g.iter().map(|v| (v - med).abs()).collect()
        })
        .collect();
    let all_devs: Vec<f64> = abs_dev_groups.iter().flat_map(|g| g.iter().copied()).collect();
    let total_var: f64 = { let m = arr_mean(&all_devs); all_devs.iter().map(|v| (v - m).powi(2)).sum::<f64>() };
    if total_var <= 1e-15 {
        return VarianceCheckResult {
            method: "Brown-Forsythe".to_string(),
            statistic: nan(), p_value: nan(),
            note: "Variance check not run because median-centered deviations are identical.".to_string(),
        };
    }
    // Run one-way ANOVA on abs-deviations
    let (ss_between, ss_within, df_between, df_within, _, _) = classical_anova_effects(&abs_dev_groups);
    let ms_between = ss_between / df_between;
    let ms_within = if df_within > 0.0 { ss_within / df_within } else { nan() };
    let (statistic, p_value) = if ms_within > 0.0 {
        let f = ms_between / ms_within;
        (f, f_sf(f, df_between, df_within))
    } else { (nan(), nan()) };
    VarianceCheckResult {
        method: "Brown-Forsythe".to_string(),
        statistic, p_value,
        note: "Levene variance check centered on group medians.".to_string(),
    }
}

// ── Dixon Q10 ─────────────────────────────────────────────────────────────────

fn samples_for_group<'a>(samples: &'a [StatisticalSample], group: &str) -> Vec<&'a StatisticalSample> {
    samples.iter().filter(|s| s.group_name == group && is_finite(s.delta_percent)).collect()
}

fn dixon_for_group(group_name: &str, group_samples: &[&StatisticalSample]) -> (Option<DixonQRecommendation>, Option<String>) {
    let n = group_samples.len();
    if n < DIXON_Q_MIN_N {
        return (None, Some(format!("Group '{group_name}' has n={n}; Dixon Q10 needs n >= {DIXON_Q_MIN_N}.")));
    }
    if n > DIXON_Q_MAX_N {
        return (None, Some(format!("Group '{group_name}' has n={n}; Dixon Q10 table is available only up to n={DIXON_Q_MAX_N}.")));
    }
    let critical = match dixon_critical_value(n) {
        Some(c) => c,
        None => return (None, Some(format!("Group '{group_name}' has n={n}; Dixon Q10 table missing entry."))),
    };

    let mut sorted = group_samples.to_vec();
    sorted.sort_by(|a, b| a.delta_percent.partial_cmp(&b.delta_percent).unwrap());

    let low_s = sorted[0];
    let low_nb = sorted[1];
    let high_nb = sorted[n - 2];
    let high_s = sorted[n - 1];
    let range = high_s.delta_percent - low_s.delta_percent;
    if !is_finite(range) || range <= 0.0 {
        return (None, Some(format!("Group '{group_name}' Dixon Q10 not run because Delta % range is zero.")));
    }

    let low_gap = low_nb.delta_percent - low_s.delta_percent;
    let high_gap = high_s.delta_percent - high_nb.delta_percent;
    let low_q = low_gap / range;
    let high_q = high_gap / range;
    let low_pass = low_q > critical;
    let high_pass = high_q > critical;

    if low_pass && high_pass && (low_q - high_q).abs() < 1e-12 {
        return (None, Some(format!("Group '{group_name}' has tied Dixon Q10 candidates; no single recommendation made.")));
    }
    let (selected, nearest, gap, q_stat, side) = if low_pass && (!high_pass || low_q > high_q) {
        (low_s, low_nb.delta_percent, low_gap, low_q, "low")
    } else if high_pass {
        (high_s, high_nb.delta_percent, high_gap, high_q, "high")
    } else {
        return (None, None);
    };

    (
        Some(DixonQRecommendation {
            group_name: selected.group_name.clone(),
            sample_name: selected.sample_name.clone(),
            file_name: selected.file_name.clone(),
            side: side.to_string(),
            delta_percent: selected.delta_percent,
            nearest_delta_percent: nearest,
            gap_delta_percent: gap,
            range_delta_percent: range,
            q_statistic: q_stat,
            critical_value: critical,
            alpha: DIXON_Q_ALPHA,
            warnings: selected.warnings.clone(),
            note: "Dixon Q10 recommends exclusion review; not automatically excluded.".to_string(),
        }),
        None,
    )
}

pub fn compute_dixon_q_review(
    group_stats: &[GroupStatistics],
    samples: &[StatisticalSample],
) -> (Vec<DixonQRecommendation>, Vec<String>) {
    let mut recs = Vec::new();
    let mut notes = Vec::new();
    for g in group_stats {
        let gs = samples_for_group(samples, &g.group_name);
        let (rec, note) = dixon_for_group(&g.group_name, &gs);
        if let Some(r) = rec { recs.push(r); }
        if let Some(n) = note { notes.push(n); }
    }
    (recs, notes)
}

pub fn compute_dixon_sensitivity_anova(
    samples: &[StatisticalSample],
    group_names: &[String],
    recommendations: &[DixonQRecommendation],
) -> Option<AnovaResult> {
    if recommendations.is_empty() { return None; }
    let excluded_keys: std::collections::HashSet<(String, String)> = recommendations
        .iter()
        .map(|r| (r.group_name.clone(), r.file_name.to_lowercase()))
        .collect();
    let sensitivity_samples: Vec<&StatisticalSample> = samples
        .iter()
        .filter(|s| !excluded_keys.contains(&(s.group_name.clone(), s.file_name.to_lowercase())))
        .collect();
    let sensitivity_groups: Vec<GroupStatistics> = group_names
        .iter()
        .map(|g| {
            let vals: Vec<f64> = sensitivity_samples
                .iter()
                .filter(|s| s.group_name == *g && is_finite(s.delta_percent))
                .map(|s| s.delta_percent)
                .collect();
            summarize_group(g, &vals)
        })
        .collect();
    let owned: Vec<StatisticalSample> = sensitivity_samples.iter().map(|s| (*s).clone()).collect();
    let anova = compute_one_way_anova(&sensitivity_groups, &owned, "One-way ANOVA");
    Some(AnovaResult {
        method: "One-way ANOVA (Dixon sensitivity)".to_string(),
        note: format!("{} Preview excludes {} Dixon Q recommendation(s).", anova.note, recommendations.len()),
        ..anova
    })
}

// ── Robust outlier review ──────────────────────────────────────────────────────

pub fn compute_outlier_review(
    group_stats: &[GroupStatistics],
    samples: &[StatisticalSample],
    excluded: &[StatisticalExclusion],
) -> (Vec<OutlierCandidate>, Vec<String>) {
    let mut candidates = Vec::new();
    let mut notes = Vec::new();
    let mut excl_count: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    for e in excluded { *excl_count.entry(e.group_name.clone()).or_default() += 1; }

    for g in group_stats {
        let gs = samples_for_group(samples, &g.group_name);
        let n = gs.len();
        if n < OUTLIER_MIN_GROUP_N {
            notes.push(format!("Group '{}' has n={n}; robust outlier review needs n >= {OUTLIER_MIN_GROUP_N}.", g.group_name));
            continue;
        }
        let group_vals: Vec<f64> = gs.iter().map(|s| s.delta_percent).collect();
        let mut group_candidates: Vec<OutlierCandidate> = Vec::new();
        let mut zero_mad_count = 0usize;

        for (i, sample) in gs.iter().enumerate() {
            let peers: Vec<f64> = group_vals.iter().enumerate().filter(|(j, _)| *j != i).map(|(_, &v)| v).collect();
            let mut sorted_peers = peers.clone();
            sorted_peers.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let peer_median = arr_median(&sorted_peers);
            let mad_vals: Vec<f64> = peers.iter().map(|v| (v - peer_median).abs()).collect();
            let mut sorted_mad = mad_vals.clone();
            sorted_mad.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let peer_mad = arr_median(&sorted_mad);
            if !is_finite(peer_mad) || peer_mad <= MAD_EPSILON {
                zero_mad_count += 1;
                continue;
            }
            let delta_from_peer = sample.delta_percent - peer_median;
            let modified_z = MODIFIED_Z_SCORE_SCALE * delta_from_peer / peer_mad;
            if modified_z.abs() < OUTLIER_MODIFIED_Z_THRESHOLD { continue; }
            group_candidates.push(OutlierCandidate {
                group_name: sample.group_name.clone(),
                sample_name: sample.sample_name.clone(),
                delta_percent: sample.delta_percent,
                peer_median,
                peer_mad,
                delta_from_peer_median: delta_from_peer,
                modified_z_score: modified_z,
                warnings: sample.warnings.clone(),
                note: format!("abs(modified z) >= {OUTLIER_MODIFIED_Z_THRESHOLD}; review raw curve; not automatically excluded."),
            });
        }
        if zero_mad_count == n {
            notes.push(format!("Group '{}' robust outlier review could not compute modified z-scores because peer MAD was zero.", g.group_name));
        } else if zero_mad_count > 0 {
            notes.push(format!("Group '{}' skipped {zero_mad_count} sample(s) in robust outlier review because peer MAD was zero.", g.group_name));
        }
        let original_n = n + excl_count.get(&g.group_name).copied().unwrap_or(0);
        let max_allowed = crate::exclusions::max_excluded_samples(original_n);
        let current_excl = excl_count.get(&g.group_name).copied().unwrap_or(0);
        if !group_candidates.is_empty() && group_candidates.len() > max_allowed {
            notes.push(format!("Group '{}' has {} outlier candidate(s), above the manual exclusion cap of {max_allowed}; review whether the whole group has a quality problem.", g.group_name, group_candidates.len()));
        } else if !group_candidates.is_empty() && group_candidates.len() + current_excl > max_allowed {
            notes.push(format!("Group '{}' already has {current_excl} excluded sample(s); excluding every candidate would exceed the manual exclusion cap of {max_allowed}.", g.group_name));
        }
        candidates.extend(group_candidates);
    }
    (candidates, notes)
}

// ── Collection ────────────────────────────────────────────────────────────────

fn delta_percent_from(delta_cap: f64, initial_avg: f64) -> f64 {
    if initial_avg.abs() < 1e-12 || !is_finite(delta_cap) { return nan(); }
    (delta_cap / initial_avg) * 100.0
}

pub fn collect_samples_for_group(
    group_name: &str,
    group_dir: &Path,
    files: &[String],
    excluded_file_names: &std::collections::HashSet<String>,
    params: &AnalysisParams,
) -> (Vec<StatisticalSample>, Vec<String>) {
    let mut samples = Vec::new();
    let mut warnings = Vec::new();
    for file_name in files {
        if excluded_file_names.contains(file_name) { continue; }
        let file_path = group_dir.join(file_name);
        let signal = match process_single_file(&file_path, params) {
            Some(s) => s,
            None => {
                warnings.push(format!("{group_name}/{file_name} could not be analyzed."));
                continue;
            }
        };
        let delta_percent = delta_percent_from(signal.delta_capacitance, signal.initial_avg);
        if !is_finite(delta_percent) {
            warnings.push(format!("{group_name}/{file_name} has an invalid Delta % and was skipped."));
            continue;
        }
        let mut sample_warnings: Vec<String> = Vec::new();
        if signal.baseline_warning_status != "ok" {
            sample_warnings.push(format!("baseline {}", signal.baseline_warning_status));
        }
        sample_warnings.extend(signal.timing_warning_details.clone());
        let sample_name = std::path::Path::new(file_name)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or(file_name)
            .to_string();
        samples.push(StatisticalSample {
            group_name: group_name.to_string(),
            sample_name,
            file_name: file_name.clone(),
            delta_percent,
            delta_capacitance: signal.delta_capacitance,
            baseline: signal.initial_avg,
            drop_time: signal.drop_time,
            baseline_warning_status: signal.baseline_warning_status,
            drop_detection_source: signal.drop_detection_source,
            warnings: sample_warnings,
        });
    }
    (samples, warnings)
}

pub fn build_statistical_analysis(
    stats_root: &Path,
    root_path_label: &str,
    params: &AnalysisParams,
) -> StatisticalAnalysisResult {
    let mut samples: Vec<StatisticalSample> = Vec::new();
    let mut excluded_samples: Vec<StatisticalExclusion> = Vec::new();
    let mut warnings: Vec<String> = Vec::new();

    let group_names: Vec<String> = crate::filesystem::get_subfolders(stats_root);

    for group_name in &group_names {
        let group_dir = stats_root.join(group_name);
        let files = list_xlsx_files(&group_dir);
        if files.is_empty() {
            warnings.push(format!("Group '{group_name}' has no .xlsx files."));
            continue;
        }
        let (metadata, meta_warning) = load_experiment_metadata(&group_dir);
        if let Some(w) = meta_warning {
            warnings.push(format!("Group '{group_name}' metadata warning: {w}"));
        }
        let current_excls: Vec<ExcludedSample> =
            current_excluded_samples(&metadata.excluded_samples, &files);
        let excluded_file_names: std::collections::HashSet<String> =
            current_excls.iter().map(|e| e.file_name.clone()).collect();
        excluded_samples.extend(current_excls.iter().map(|e| StatisticalExclusion {
            group_name: group_name.clone(),
            file_name: e.file_name.clone(),
            reason: e.reason.clone(),
            method: e.method.clone(),
        }));
        let (group_samples, group_warnings) =
            collect_samples_for_group(group_name, &group_dir, &files, &excluded_file_names, params);
        samples.extend(group_samples);
        warnings.extend(group_warnings);
    }

    let group_stats: Vec<GroupStatistics> = group_names
        .iter()
        .map(|g| {
            let vals: Vec<f64> = samples
                .iter()
                .filter(|s| s.group_name == *g && is_finite(s.delta_percent))
                .map(|s| s.delta_percent)
                .collect();
            summarize_group(g, &vals)
        })
        .collect();

    for g in &group_stats {
        if g.n < 2 {
            warnings.push(format!("Group '{}' has n={}; one-way ANOVA needs n >= 2.", g.group_name, g.n));
        } else if g.n < 3 {
            warnings.push(format!("Group '{}' has n={}; normality tests need n >= 3.", g.group_name, g.n));
        }
    }

    let variance_check = compute_variance_check(&group_stats, &samples);
    let anova = compute_one_way_anova(&group_stats, &samples, "One-way ANOVA");
    let (dixon_recommendations, dixon_review_notes) = compute_dixon_q_review(&group_stats, &samples);
    let dixon_sensitivity_anova =
        compute_dixon_sensitivity_anova(&samples, &group_names, &dixon_recommendations);
    let (outlier_candidates, outlier_review_notes) =
        compute_outlier_review(&group_stats, &samples, &excluded_samples);

    StatisticalAnalysisResult {
        root_path: root_path_label.to_string(),
        samples,
        excluded_samples,
        group_statistics: group_stats,
        variance_check,
        anova,
        dixon_recommendations,
        dixon_review_notes,
        dixon_sensitivity_anova,
        outlier_candidates,
        outlier_review_notes,
        warnings,
    }
}

// ── Formatting ────────────────────────────────────────────────────────────────

fn fmt_dixon_q_rule() -> String {
    format!(
        "Q10; alpha={DIXON_Q_ALPHA}; n={DIXON_Q_MIN_N}-{DIXON_Q_MAX_N}; Q = gap / range; checks one low or high endpoint only."
    )
}

fn fmt_outlier_rule() -> String {
    format!(
        "Delta % only; group n >= {OUTLIER_MIN_GROUP_N}; leave-one-out peer median/MAD; abs(modified z) >= {OUTLIER_MODIFIED_Z_THRESHOLD}; not automatically excluded."
    )
}

pub fn format_statistics_result(result: &StatisticalAnalysisResult) -> String {
    let mut lines: Vec<String> = vec![
        "Statistical Analysis - Delta %".to_string(),
        format!("Root: {}", if result.root_path.is_empty() { "N/A" } else { &result.root_path }),
        String::new(),
        "Warnings".to_string(),
    ];
    if result.warnings.is_empty() {
        lines.push("- None".to_string());
    } else {
        lines.extend(result.warnings.iter().map(|w| format!("- {w}")));
    }

    lines.extend(["".to_string(), "Excluded Samples".to_string()]);
    if result.excluded_samples.is_empty() {
        lines.push("None".to_string());
    } else {
        for e in &result.excluded_samples {
            let method_tag = if e.method.is_empty() { String::new() } else { format!(" [{}]", e.method) };
            let reason = if e.reason.is_empty() { "No reason provided" } else { &e.reason };
            lines.push(format!("{}/{}{}: {}", e.group_name, e.file_name, method_tag, reason));
        }
    }

    lines.extend(["".to_string(), "Dixon Q Review".to_string(), format!("Rule: {}", fmt_dixon_q_rule())]);
    lines.extend(result.dixon_review_notes.iter().map(|n| format!("- {n}")));
    if result.dixon_recommendations.is_empty() {
        lines.push("No Dixon Q recommended exclusions.".to_string());
    } else {
        lines.push(format!("Recommended Dixon Exclusions: {}", result.dixon_recommendations.len()));
        for r in &result.dixon_recommendations {
            let qw = if r.warnings.is_empty() { "None".to_string() } else { r.warnings.join("; ") };
            lines.push(format!(
                "{}/{}: side={}, delta={}, nearest={}, gap={}, range={}, Q={}, critical={}; quality warnings={}; {}",
                r.group_name, r.file_name, r.side,
                fmt_f(r.delta_percent), fmt_f(r.nearest_delta_percent),
                fmt_f(r.gap_delta_percent), fmt_f(r.range_delta_percent),
                fmt_f(r.q_statistic), fmt_f(r.critical_value), qw, r.note
            ));
        }
    }

    lines.extend(["".to_string(), "Outlier Review".to_string(), format!("Rule: {}", fmt_outlier_rule())]);
    lines.extend(result.outlier_review_notes.iter().map(|n| format!("- {n}")));
    if result.outlier_candidates.is_empty() {
        lines.push("No robust outlier candidates.".to_string());
    } else {
        lines.push(format!("Candidate count: {}", result.outlier_candidates.len()));
        for c in &result.outlier_candidates {
            let qw = if c.warnings.is_empty() { "None".to_string() } else { c.warnings.join("; ") };
            lines.push(format!(
                "{}/{}: delta={}, peer median={}, diff={}, peer MAD={}, modified z={}; quality warnings={}; {}",
                c.group_name, c.sample_name,
                fmt_f(c.delta_percent), fmt_f(c.peer_median),
                fmt_f(c.delta_from_peer_median), fmt_f(c.peer_mad),
                fmt_f(c.modified_z_score), qw, c.note
            ));
        }
    }

    lines.extend(["".to_string(), "Descriptive Statistics".to_string()]);
    if result.group_statistics.is_empty() {
        lines.push("No valid groups.".to_string());
    } else {
        for g in &result.group_statistics {
            lines.push(format!(
                "{}: n={}, mean={}%, SD={}%, SEM={}%, median={}%, IQR={}%, 95% CI [{}%, {}%]",
                g.group_name, g.n,
                fmt_f(g.mean), fmt_f(g.sd), fmt_f(g.sem),
                fmt_f(g.median), fmt_f(g.iqr), fmt_f(g.ci95_low), fmt_f(g.ci95_high)
            ));
        }
    }

    lines.extend(["".to_string(), "Assumption Checks".to_string()]);
    let vc = &result.variance_check;
    lines.push(format!("{}: statistic={}, p={}; {}", vc.method, fmt_f(vc.statistic), fmt_f(vc.p_value), vc.note));
    for g in &result.group_statistics {
        lines.push(format!("{} normality: {}", g.group_name, g.normality_note));
    }

    lines.extend(["".to_string(), "One-way ANOVA".to_string()]);
    let a = &result.anova;
    lines.push(format!(
        "{}: F={}, df=({}, {}), p={}, eta2={}, omega2={}; {}",
        a.method, fmt_f(a.statistic), fmt_f(a.df_num), fmt_f(a.df_den),
        fmt_f(a.p_value), fmt_f(a.eta_squared), fmt_f(a.omega_squared), a.note
    ));

    lines.extend(["".to_string(), "ANOVA Sensitivity After Dixon Recommendations".to_string()]);
    match &result.dixon_sensitivity_anova {
        None => lines.push("Not run because Dixon Q made no recommended exclusions.".to_string()),
        Some(a) => lines.push(format!(
            "{}: F={}, df=({}, {}), p={}, eta2={}, omega2={}; {}",
            a.method, fmt_f(a.statistic), fmt_f(a.df_num), fmt_f(a.df_den),
            fmt_f(a.p_value), fmt_f(a.eta_squared), fmt_f(a.omega_squared), a.note
        )),
    }

    lines.extend(["".to_string(), "Per-Sample Delta %".to_string()]);
    if result.samples.is_empty() {
        lines.push("No valid samples.".to_string());
    } else {
        for s in &result.samples {
            let w = if s.warnings.is_empty() { "None".to_string() } else { s.warnings.join("; ") };
            lines.push(format!(
                "{}/{}: delta={}%, baseline={} pF, raw delta={} pF, drop={}s, warnings={}",
                s.group_name, s.sample_name,
                fmt_f(s.delta_percent), fmt_f(s.baseline),
                fmt_f(s.delta_capacitance), fmt_f(s.drop_time), w
            ));
        }
    }
    lines.join("\n")
}

pub fn statistics_result_to_csv(result: &StatisticalAnalysisResult) -> String {
    let mut rows: Vec<Vec<String>> = Vec::new();
    let s = |v: &str| v.to_string();
    let ff = |v: f64| fmt_f(v);

    rows.push(vec![s("Statistical Analysis - Delta %")]);
    rows.push(vec![s("root_path"), result.root_path.clone()]);
    rows.push(vec![]);
    rows.push(vec![s("Warnings")]);
    if result.warnings.is_empty() { rows.push(vec![s("None")]); }
    else { result.warnings.iter().for_each(|w| rows.push(vec![w.clone()])); }

    rows.push(vec![]);
    rows.push(vec![s("Excluded Samples")]);
    rows.push(vec![s("group"), s("file"), s("method"), s("reason")]);
    if result.excluded_samples.is_empty() { rows.push(vec![s("None")]); }
    else { result.excluded_samples.iter().for_each(|e| rows.push(vec![e.group_name.clone(), e.file_name.clone(), e.method.clone(), e.reason.clone()])); }

    rows.push(vec![]);
    rows.push(vec![s("Dixon Q Review")]);
    rows.push(vec![s("rule"), fmt_dixon_q_rule()]);
    result.dixon_review_notes.iter().for_each(|n| rows.push(vec![n.clone()]));
    rows.push(vec![s("Recommended Dixon Exclusions")]);
    rows.push(vec![s("group"), s("file"), s("sample"), s("side"), s("delta_percent"), s("nearest"), s("gap"), s("range"), s("q"), s("critical"), s("alpha"), s("quality_warnings"), s("note")]);
    if result.dixon_recommendations.is_empty() { rows.push(vec![s("None")]); }
    else {
        result.dixon_recommendations.iter().for_each(|r| rows.push(vec![
            r.group_name.clone(), r.file_name.clone(), r.sample_name.clone(), r.side.clone(),
            ff(r.delta_percent), ff(r.nearest_delta_percent), ff(r.gap_delta_percent), ff(r.range_delta_percent),
            ff(r.q_statistic), ff(r.critical_value), ff(r.alpha), r.warnings.join("; "), r.note.clone(),
        ]));
    }

    rows.push(vec![]);
    rows.push(vec![s("Outlier Review Candidates")]);
    rows.push(vec![s("rule"), fmt_outlier_rule()]);
    result.outlier_review_notes.iter().for_each(|n| rows.push(vec![n.clone()]));
    rows.push(vec![s("group"), s("sample"), s("delta_percent"), s("peer_median"), s("delta_from_peer_median"), s("peer_mad"), s("modified_z_score"), s("quality_warnings"), s("note")]);
    if result.outlier_candidates.is_empty() { rows.push(vec![s("None")]); }
    else {
        result.outlier_candidates.iter().for_each(|c| rows.push(vec![
            c.group_name.clone(), c.sample_name.clone(), ff(c.delta_percent), ff(c.peer_median),
            ff(c.delta_from_peer_median), ff(c.peer_mad), ff(c.modified_z_score), c.warnings.join("; "), c.note.clone(),
        ]));
    }

    rows.push(vec![]);
    rows.push(vec![s("Descriptive Statistics")]);
    rows.push(vec![s("group"), s("n"), s("mean_delta_pct"), s("sd"), s("sem"), s("median"), s("q1"), s("q3"), s("iqr"), s("ci95_low"), s("ci95_high"), s("normality_note")]);
    result.group_statistics.iter().for_each(|g| rows.push(vec![
        g.group_name.clone(), g.n.to_string(), ff(g.mean), ff(g.sd), ff(g.sem),
        ff(g.median), ff(g.q1), ff(g.q3), ff(g.iqr), ff(g.ci95_low), ff(g.ci95_high), g.normality_note.clone(),
    ]));

    rows.push(vec![]);
    rows.push(vec![s("Assumption Checks")]);
    rows.push(vec![s("method"), s("statistic"), s("p_value"), s("note")]);
    let vc = &result.variance_check;
    rows.push(vec![vc.method.clone(), ff(vc.statistic), ff(vc.p_value), vc.note.clone()]);

    rows.push(vec![]);
    rows.push(vec![s("One-way ANOVA")]);
    rows.push(vec![s("method"), s("group_count"), s("sample_count"), s("df_num"), s("df_den"), s("statistic"), s("p_value"), s("eta_squared"), s("omega_squared"), s("note")]);
    let a = &result.anova;
    rows.push(vec![a.method.clone(), a.group_count.to_string(), a.sample_count.to_string(), ff(a.df_num), ff(a.df_den), ff(a.statistic), ff(a.p_value), ff(a.eta_squared), ff(a.omega_squared), a.note.clone()]);

    rows.push(vec![]);
    rows.push(vec![s("ANOVA Sensitivity After Dixon Recommendations")]);
    rows.push(vec![s("method"), s("group_count"), s("sample_count"), s("df_num"), s("df_den"), s("statistic"), s("p_value"), s("eta_squared"), s("omega_squared"), s("note")]);
    match &result.dixon_sensitivity_anova {
        None => rows.push(vec![s("None")]),
        Some(a) => rows.push(vec![a.method.clone(), a.group_count.to_string(), a.sample_count.to_string(), ff(a.df_num), ff(a.df_den), ff(a.statistic), ff(a.p_value), ff(a.eta_squared), ff(a.omega_squared), a.note.clone()]),
    }

    rows.push(vec![]);
    rows.push(vec![s("Per-Sample Delta %")]);
    rows.push(vec![s("group"), s("sample"), s("delta_percent"), s("delta_capacitance"), s("baseline"), s("drop_time"), s("baseline_warning_status"), s("drop_detection_source"), s("warnings")]);
    result.samples.iter().for_each(|sample| rows.push(vec![
        sample.group_name.clone(), sample.sample_name.clone(), ff(sample.delta_percent),
        ff(sample.delta_capacitance), ff(sample.baseline), ff(sample.drop_time),
        sample.baseline_warning_status.clone(), sample.drop_detection_source.clone(), sample.warnings.join("; "),
    ]));

    rows.iter()
        .map(|row| {
            row.iter()
                .map(|cell| {
                    if cell.contains(',') || cell.contains('"') || cell.contains('\n') {
                        format!("\"{}\"", cell.replace('"', "\"\""))
                    } else {
                        cell.clone()
                    }
                })
                .collect::<Vec<_>>()
                .join(",")
        })
        .collect::<Vec<_>>()
        .join("\n")
}
