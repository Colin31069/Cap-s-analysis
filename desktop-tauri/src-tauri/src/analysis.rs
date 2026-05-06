use std::path::Path;

use calamine::{open_workbook_auto, DataType, Reader};

use crate::config::{
    BASELINE_RISE_MIN_RUN, BASELINE_RISE_ROLLING_POINTS, BASELINE_TAIL_POINTS, DATA_COL,
    DROP_SIGMA_THRESHOLD, DT_SEC, LEGACY_DROP_SEARCH_POINTS,
};
use crate::models::{AnalysisParams, ProcessedSignal};

// ── Numeric helpers ────────────────────────────────────────────────────────────

fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return f64::NAN;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

fn sample_std(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let avg = mean(values);
    let variance = values.iter().map(|v| (v - avg).powi(2)).sum::<f64>() / (values.len() - 1) as f64;
    variance.sqrt()
}

fn nanmean(values: &[f64]) -> f64 {
    let (sum, count) = values.iter().filter(|v| !v.is_nan()).fold((0.0, 0usize), |(s, c), &v| (s + v, c + 1));
    if count == 0 { f64::NAN } else { sum / count as f64 }
}

fn offset_pct(value: f64, baseline: f64) -> f64 {
    if baseline.abs() < 1e-12 {
        0.0
    } else {
        (value / baseline) * 100.0 - 100.0
    }
}

fn seconds_to_points(sec: f64) -> usize {
    (sec / DT_SEC).round() as usize
}

fn cell_to_f64(cell: &impl DataType) -> f64 {
    if let Some(v) = cell.get_float() {
        v
    } else if let Some(v) = cell.get_int() {
        v as f64
    } else if let Some(s) = cell.get_string() {
        s.parse::<f64>().unwrap_or(f64::NAN)
    } else if let Some(b) = cell.get_bool() {
        if b { 1.0 } else { 0.0 }
    } else {
        f64::NAN
    }
}

// ── Baseline accuracy ──────────────────────────────────────────────────────────

fn max_continuous_rise_offset_pct(baseline_segment: &[f64], baseline_avg: f64) -> f64 {
    let n = baseline_segment.len();
    if n < BASELINE_RISE_ROLLING_POINTS {
        return 0.0;
    }
    let rolling_len = n - BASELINE_RISE_ROLLING_POINTS + 1;
    let rolling_means: Vec<f64> = (0..rolling_len)
        .map(|i| mean(&baseline_segment[i..i + BASELINE_RISE_ROLLING_POINTS]))
        .collect();
    if rolling_means.len() < BASELINE_RISE_MIN_RUN {
        return 0.0;
    }
    let mut run_length = 1usize;
    let mut max_offset = 0.0f64;
    for i in 1..rolling_means.len() {
        if rolling_means[i] > rolling_means[i - 1] {
            run_length += 1;
        } else {
            if run_length >= BASELINE_RISE_MIN_RUN {
                max_offset = max_offset.max(offset_pct(rolling_means[i - 1], baseline_avg));
            }
            run_length = 1;
        }
    }
    if run_length >= BASELINE_RISE_MIN_RUN {
        if let Some(&last) = rolling_means.last() {
            max_offset = max_offset.max(offset_pct(last, baseline_avg));
        }
    }
    max_offset.max(0.0)
}

fn baseline_warning_status(tail_hit: bool, rise_hit: bool) -> String {
    match (tail_hit as u8) + (rise_hit as u8) {
        2 => "inaccurate".to_string(),
        1 => "warning".to_string(),
        _ => "ok".to_string(),
    }
}

// ── Effective baseline length ──────────────────────────────────────────────────

fn effective_baseline_points(
    sample_count: usize,
    requested_baseline_duration_sec: f64,
    apply_window_start_idx: usize,
) -> (usize, bool) {
    let requested = sample_count.min(seconds_to_points(requested_baseline_duration_sec.max(DT_SEC)).max(1));
    if requested <= apply_window_start_idx {
        return (requested, false);
    }
    let shortened = sample_count.min(apply_window_start_idx).max(1);
    (shortened, true)
}

// ── Drop detection ─────────────────────────────────────────────────────────────

fn first_threshold_crossing(samples: &[f64], threshold: f64, start: usize, end: usize) -> Option<usize> {
    if start >= end || end > samples.len() {
        return None;
    }
    samples[start..end].iter().position(|&v| v > threshold).map(|i| start + i)
}

fn fallback_drop_index(samples: &[f64], threshold: f64, baseline_end: usize) -> usize {
    let search_end = samples.len().min(baseline_end + LEGACY_DROP_SEARCH_POINTS);
    first_threshold_crossing(samples, threshold, baseline_end, search_end).unwrap_or(baseline_end)
}

fn build_timing_warning_details(
    requested_baseline_duration_sec: f64,
    effective_baseline_duration_sec: f64,
    baseline_was_auto_shortened: bool,
    apply_time_sec: f64,
    apply_tolerance_sec: f64,
    drop_search_fallback_used: bool,
) -> Vec<String> {
    let mut details = Vec::new();
    if baseline_was_auto_shortened {
        if effective_baseline_duration_sec <= DT_SEC {
            details.push(
                "Baseline overlapped the apply window and was clamped to the minimum baseline length."
                    .to_string(),
            );
        } else {
            details.push(format!(
                "Baseline shortened from {:.1}s to {:.1}s to stay before the apply window.",
                requested_baseline_duration_sec, effective_baseline_duration_sec
            ));
        }
    }
    if drop_search_fallback_used {
        details.push(format!(
            "No threshold crossing found within {:.1}s +/- {:.1}s; used automatic fallback search.",
            apply_time_sec, apply_tolerance_sec
        ));
    }
    details
}

// ── Public API ─────────────────────────────────────────────────────────────────

pub fn read_xlsx_single(path: &Path) -> Option<Vec<f64>> {
    let mut workbook = open_workbook_auto(path).ok()?;
    let range = workbook.worksheet_range_at(0)?.ok()?;
    let mut rows = range.rows();
    let header_row = rows.next()?;
    let column_index = header_row.iter().position(|cell| cell.to_string() == DATA_COL)?;
    let samples = rows.map(|row| row.get(column_index).map(cell_to_f64).unwrap_or(f64::NAN)).collect();
    Some(samples)
}

pub fn analyze_signal(data: &[f64], params: &AnalysisParams) -> Option<ProcessedSignal> {
    if data.is_empty() {
        return None;
    }
    let samples = data.to_vec();

    let requested_baseline_sec = params.baseline_duration_sec.max(DT_SEC);
    let apply_center_idx = seconds_to_points(params.drug_apply_time_sec.max(0.0));
    let apply_tolerance_pts = seconds_to_points(params.drug_apply_tolerance_sec.max(0.0));
    let apply_window_start_idx = apply_center_idx.saturating_sub(apply_tolerance_pts);
    let apply_window_end_idx = samples.len().min(apply_center_idx + apply_tolerance_pts + 1);

    let (baseline_len, baseline_was_auto_shortened) =
        effective_baseline_points(samples.len(), requested_baseline_sec, apply_window_start_idx);
    let baseline_segment = &samples[..baseline_len];
    let initial_avg = mean(baseline_segment);
    let std = sample_std(baseline_segment);
    let effective_baseline_duration_sec = baseline_len as f64 * DT_SEC;

    // Baseline accuracy
    let tail_len = baseline_segment.len().min(BASELINE_TAIL_POINTS);
    let tail_mean = if tail_len > 0 { mean(&baseline_segment[baseline_segment.len() - tail_len..]) } else { initial_avg };
    let tail_offset_pct = offset_pct(tail_mean, initial_avg);
    let rise_offset_pct = max_continuous_rise_offset_pct(baseline_segment, initial_avg);
    let warning_threshold = params.baseline_warning_threshold_pct.max(0.0);
    let tail_warning_hit = tail_offset_pct.abs() >= warning_threshold;
    let rise_warning_hit = rise_offset_pct >= warning_threshold;

    // Drop detection
    let threshold = initial_avg + DROP_SIGMA_THRESHOLD * std.max(1e-4);
    let window_search_start = baseline_len.max(apply_window_start_idx);
    let idx_drop_opt =
        first_threshold_crossing(&samples, threshold, window_search_start, apply_window_end_idx);
    let drop_search_fallback_used = idx_drop_opt.is_none();
    let (idx_drop, drop_detection_source) = if let Some(idx) = idx_drop_opt {
        (idx, "window".to_string())
    } else {
        (fallback_drop_index(&samples, threshold, baseline_len), "fallback_auto".to_string())
    };

    let final_avg = if samples.len() >= 100 { nanmean(&samples[samples.len() - 100..]) } else { f64::NAN };
    let delta_capacitance = if final_avg.is_nan() { f64::NAN } else { final_avg - initial_avg };

    let timing_warning_details = build_timing_warning_details(
        requested_baseline_sec,
        effective_baseline_duration_sec,
        baseline_was_auto_shortened,
        params.drug_apply_time_sec,
        params.drug_apply_tolerance_sec,
        drop_search_fallback_used,
    );

    Some(ProcessedSignal {
        time_sec: (0..samples.len()).map(|i| i as f64 * DT_SEC).collect(),
        capacitance: samples,
        drop_time: idx_drop as f64 * DT_SEC,
        delta_capacitance,
        initial_avg,
        effective_baseline_points: baseline_len,
        effective_baseline_duration_sec,
        baseline_was_auto_shortened,
        drop_detection_source,
        drop_search_fallback_used,
        timing_warning_details,
        baseline_warning_status: baseline_warning_status(tail_warning_hit, rise_warning_hit),
        baseline_tail_offset_pct: tail_offset_pct,
        baseline_rise_offset_pct: rise_offset_pct,
        baseline_tail_warning_hit: tail_warning_hit,
        baseline_rise_warning_hit: rise_warning_hit,
    })
}

pub fn process_single_file(path: &Path, params: &AnalysisParams) -> Option<ProcessedSignal> {
    let values = read_xlsx_single(path)?;
    if values.is_empty() {
        return None;
    }
    analyze_signal(&values, params)
}

// ── Tests ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use approx::assert_relative_eq;

    use super::analyze_signal;
    use crate::config::{DT_SEC, INITIAL_BASELINE_POINTS};
    use crate::models::AnalysisParams;

    fn default_params() -> AnalysisParams {
        AnalysisParams::default()
    }

    #[test]
    fn baseline_uses_configured_window_for_long_signal() {
        let mut samples = vec![10.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![13.0; 120]);
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_relative_eq!(signal.initial_avg, 10.0);
        assert_relative_eq!(signal.drop_time, INITIAL_BASELINE_POINTS as f64 * DT_SEC);
    }

    #[test]
    fn short_signal_uses_full_length_as_baseline() {
        let samples = vec![2.0, 4.0, 6.0, 8.0];
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_relative_eq!(signal.initial_avg, 5.0);
        assert!(signal.delta_capacitance.is_nan());
        assert_relative_eq!(signal.drop_time, samples.len() as f64 * DT_SEC);
    }

    #[test]
    fn threshold_crossing_uses_first_crossing_after_baseline() {
        let mut samples = vec![5.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![5.0, 5.0, 5.0, 8.5, 9.0]);
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_relative_eq!(signal.drop_time, (INITIAL_BASELINE_POINTS as f64 + 3.0) * DT_SEC);
    }

    #[test]
    fn no_crossing_falls_back_to_baseline_boundary() {
        let samples = vec![7.0; INITIAL_BASELINE_POINTS + 10];
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_relative_eq!(signal.drop_time, INITIAL_BASELINE_POINTS as f64 * DT_SEC);
    }

    #[test]
    fn delta_uses_last_hundred_points_when_available() {
        let mut samples = vec![10.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![11.0; 50]);
        samples.extend(vec![14.0; 100]);
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_relative_eq!(signal.delta_capacitance, 4.0);
    }

    #[test]
    fn drop_detection_source_is_window_when_crossing_in_apply_window() {
        let mut samples = vec![5.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![5.0, 9.0]); // crossing at index 201, within [200, 301]
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_eq!(signal.drop_detection_source, "window");
        assert!(!signal.drop_search_fallback_used);
    }

    #[test]
    fn drop_detection_source_is_fallback_when_no_window_crossing() {
        let samples = vec![7.0; INITIAL_BASELINE_POINTS + 10];
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert_eq!(signal.drop_detection_source, "fallback_auto");
        assert!(signal.drop_search_fallback_used);
    }

    #[test]
    fn baseline_tail_warning_fires_above_threshold() {
        // baseline rising over last 20 points → tail_offset_pct > 2%
        let mut samples: Vec<f64> = (0..INITIAL_BASELINE_POINTS)
            .map(|i| if i < 180 { 10.0 } else { 10.5 })
            .collect();
        samples.extend(vec![10.5; 100]);
        let signal = analyze_signal(&samples, &default_params()).unwrap();
        assert!(signal.baseline_tail_warning_hit);
    }
}
