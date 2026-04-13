use std::path::Path;

use calamine::{open_workbook_auto, DataType, Reader};

use crate::config::{DATA_COL, DROP_SIGMA_THRESHOLD, DT_SEC, INITIAL_BASELINE_POINTS};
use crate::models::ProcessedSignal;

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn sample_std(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }

    let average = mean(values);
    let variance = values
        .iter()
        .map(|value| {
            let diff = value - average;
            diff * diff
        })
        .sum::<f64>()
        / (values.len() - 1) as f64;

    variance.sqrt()
}

fn nanmean(values: &[f64]) -> f64 {
    let mut total = 0.0;
    let mut count = 0usize;

    for value in values {
        if !value.is_nan() {
            total += value;
            count += 1;
        }
    }

    if count == 0 {
        f64::NAN
    } else {
        total / count as f64
    }
}

fn cell_to_f64(cell: &impl DataType) -> f64 {
    if let Some(value) = cell.get_float() {
        value
    } else if let Some(value) = cell.get_int() {
        value as f64
    } else if let Some(value) = cell.get_string() {
        value.parse::<f64>().unwrap_or(f64::NAN)
    } else if let Some(value) = cell.get_bool() {
        if value {
            1.0
        } else {
            0.0
        }
    } else {
        f64::NAN
    }
}

pub fn read_xlsx_single(path: &Path) -> Option<Vec<f64>> {
    let mut workbook = open_workbook_auto(path).ok()?;
    let range = workbook.worksheet_range_at(0)?.ok()?;
    let mut rows = range.rows();
    let header_row = rows.next()?;
    let column_index = header_row
        .iter()
        .position(|cell| cell.to_string() == DATA_COL)?;

    let samples = rows
        .map(|row| row.get(column_index).map(cell_to_f64).unwrap_or(f64::NAN))
        .collect::<Vec<_>>();

    Some(samples)
}

pub fn analyze_signal(data: &[f64]) -> Option<ProcessedSignal> {
    if data.is_empty() {
        return None;
    }

    let samples = data.to_vec();
    let baseline_len = samples.len().min(INITIAL_BASELINE_POINTS);
    let baseline_segment = &samples[..baseline_len];
    let initial_avg = mean(baseline_segment);
    let std = sample_std(baseline_segment);
    let threshold = initial_avg + DROP_SIGMA_THRESHOLD * std.max(1e-4);
    let search_end = samples.len().min(baseline_len + 500);
    let search_range = &samples[baseline_len..search_end];
    let offset = search_range
        .iter()
        .position(|value| *value > threshold)
        .unwrap_or(0);
    let drop_index = baseline_len + offset;

    let final_avg = if samples.len() >= 100 {
        nanmean(&samples[samples.len() - 100..])
    } else {
        f64::NAN
    };
    let delta_capacitance = if final_avg.is_nan() {
        f64::NAN
    } else {
        final_avg - initial_avg
    };

    Some(ProcessedSignal {
        time_sec: (0..samples.len()).map(|index| index as f64 * DT_SEC).collect(),
        capacitance: samples,
        drop_time: drop_index as f64 * DT_SEC,
        delta_capacitance,
        initial_avg,
    })
}

pub fn process_single_file(path: &Path) -> Option<ProcessedSignal> {
    let values = read_xlsx_single(path)?;
    if values.is_empty() {
        return None;
    }
    analyze_signal(&values)
}

#[cfg(test)]
mod tests {
    use approx::assert_relative_eq;

    use super::analyze_signal;
    use crate::config::{DT_SEC, INITIAL_BASELINE_POINTS};

    #[test]
    fn baseline_uses_configured_window_for_long_signal() {
        let mut samples = vec![10.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![13.0; 120]);
        let signal = analyze_signal(&samples).unwrap();

        assert_relative_eq!(signal.initial_avg, 10.0);
        assert_relative_eq!(signal.drop_time, INITIAL_BASELINE_POINTS as f64 * DT_SEC);
    }

    #[test]
    fn short_signal_uses_full_length_as_baseline() {
        let samples = vec![2.0, 4.0, 6.0, 8.0];
        let signal = analyze_signal(&samples).unwrap();

        assert_relative_eq!(signal.initial_avg, 5.0);
        assert!(signal.delta_capacitance.is_nan());
        assert_relative_eq!(signal.drop_time, samples.len() as f64 * DT_SEC);
    }

    #[test]
    fn threshold_crossing_uses_first_crossing_after_baseline() {
        let mut samples = vec![5.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![5.0, 5.0, 5.0, 8.5, 9.0]);
        let signal = analyze_signal(&samples).unwrap();

        assert_relative_eq!(
            signal.drop_time,
            (INITIAL_BASELINE_POINTS as f64 + 3.0) * DT_SEC
        );
    }

    #[test]
    fn no_crossing_falls_back_to_baseline_boundary() {
        let samples = vec![7.0; INITIAL_BASELINE_POINTS + 10];
        let signal = analyze_signal(&samples).unwrap();

        assert_relative_eq!(signal.drop_time, INITIAL_BASELINE_POINTS as f64 * DT_SEC);
    }

    #[test]
    fn delta_uses_last_hundred_points_when_available() {
        let mut samples = vec![10.0; INITIAL_BASELINE_POINTS];
        samples.extend(vec![11.0; 50]);
        samples.extend(vec![14.0; 100]);
        let signal = analyze_signal(&samples).unwrap();

        assert_relative_eq!(signal.delta_capacitance, 4.0);
    }
}
