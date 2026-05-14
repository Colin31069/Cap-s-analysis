use crate::models::{ExperimentMetadata, PlotRequest, PlotSeries, ProcessedSignal};

pub fn display_mode_to_y_unit(display_mode: &str) -> String {
    match display_mode {
        "Norm" => "Normalized (%)".to_string(),
        "Base" => "Baseline Capacitance (pF)".to_string(),
        _ => "Raw Capacitance (pF)".to_string(),
    }
}

pub fn transform_signal_for_display(
    signal: &ProcessedSignal,
    display_mode: &str,
) -> (Vec<f64>, Vec<f64>, String) {
    // Align time so drop is at t = 0 (parity with Python)
    let x_aligned: Vec<f64> = signal.time_sec.iter().map(|t| t - signal.drop_time).collect();

    let (x_plot, y_plot, delta_label) = match display_mode {
        "Norm" => {
            let base = signal.initial_avg;
            let y: Vec<f64> = signal.capacitance.iter().map(|v| (v / base) * 100.0).collect();
            let delta_pct = (((base + signal.delta_capacitance) / base) * 100.0) - 100.0;
            (x_aligned, y, format!("Δ:{delta_pct:.2}%"))
        }
        "Base" => {
            let limit = signal.effective_baseline_points.min(signal.capacitance.len());
            (x_aligned[..limit].to_vec(), signal.capacitance[..limit].to_vec(), format!("Δ:{:.2}pF", signal.delta_capacitance))
        }
        _ => {
            let delta_raw = signal.delta_capacitance;
            (x_aligned, signal.capacitance.clone(), format!("Δ:{delta_raw:.2}pF"))
        }
    };
    (x_plot, y_plot, delta_label)
}

fn warning_status_suffix(status: &str) -> &'static str {
    match status {
        "warning" => " [!]",
        "inaccurate" => " [!!]",
        _ => "",
    }
}

pub fn build_medicine_legend_summary(metadata: &ExperimentMetadata) -> String {
    let parts: Vec<String> = metadata
        .medicines
        .iter()
        .take(metadata.medicine_count)
        .filter_map(|m| {
            let name = m.name.trim();
            let dose = m.dose.trim();
            match (name.is_empty(), dose.is_empty()) {
                (true, true) => None,
                (false, false) => Some(format!("{name} {dose}")),
                (false, true) => Some(name.to_string()),
                (true, false) => Some(dose.to_string()),
            }
        })
        .collect();
    parts.join(" / ")
}

pub fn build_overlay_group_label(experiment_name: &str, metadata: &ExperimentMetadata) -> String {
    let summary = build_medicine_legend_summary(metadata);
    if summary.is_empty() { experiment_name.trim().to_string() } else { summary }
}

pub fn build_plot_title(experiment_name: &str, metadata: &ExperimentMetadata, custom_title: &str) -> String {
    let custom = custom_title.trim();
    if !custom.is_empty() { return custom.to_string(); }
    let mut parts = vec![experiment_name.to_string()];
    for m in metadata.medicines.iter().take(metadata.medicine_count) {
        let name = m.name.trim();
        let dose = m.dose.trim();
        match (name.is_empty(), dose.is_empty()) {
            (true, true) => {}
            (false, false) => parts.push(format!("{name}: {dose}")),
            (false, true) => parts.push(name.to_string()),
            (true, false) => parts.push(dose.to_string()),
        }
    }
    parts.join(" | ")
}

pub fn build_legend_label(
    sample_name: &str,
    settings: &PlotRequest,
    base: f64,
    delta_label: &str,
    warning_status: &str,
    is_overlay_with_group_color: bool,
) -> String {
    // In overlay+group-color mode each sample trace is hidden from legend
    if is_overlay_with_group_color {
        return "_nolegend_".to_string();
    }

    let suffix = warning_status_suffix(warning_status);
    let prefix = format!("N {sample_name}{suffix}");

    if settings.legend_style == "Simple" {
        return prefix;
    }

    let mut parts = Vec::new();
    if settings.show_group {
        parts.push(format!("[{}]", settings.experiment_name));
    }
    parts.push(prefix);

    let mut details = Vec::new();
    if settings.show_base {
        details.push(format!("Base:{base:.2} pF"));
    }
    if settings.show_delta {
        details.push(delta_label.to_string());
    }

    if details.is_empty() {
        parts.join(" ")
    } else {
        format!("{} ({})", parts.join(" "), details.join(", "))
    }
}

pub fn build_plot_series(
    signal: &ProcessedSignal,
    sample_name: &str,
    settings: &PlotRequest,
    line_style: &str,
    color: Option<String>,
    is_overlay_with_group_color: bool,
) -> PlotSeries {
    let (x, y, delta_label) = transform_signal_for_display(signal, &settings.display_mode);
    let legend_label = build_legend_label(
        sample_name,
        settings,
        signal.initial_avg,
        &delta_label,
        &signal.baseline_warning_status,
        is_overlay_with_group_color,
    );
    PlotSeries {
        sample_name: sample_name.to_string(),
        x,
        y,
        drop_time: 0.0, // always 0 after alignment
        line_style: line_style.to_string(),
        color,
        legend_label,
        baseline_warning_status: signal.baseline_warning_status.clone(),
        timing_warning_details: signal.timing_warning_details.clone(),
        drop_detection_source: signal.drop_detection_source.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::{build_legend_label, display_mode_to_y_unit, transform_signal_for_display};
    use crate::config::INITIAL_BASELINE_POINTS;
    use crate::models::{PlotRequest, ProcessedSignal};

    fn make_settings() -> PlotRequest {
        PlotRequest {
            root_path: "/tmp".to_string(),
            experiment_name: "GroupA".to_string(),
            display_mode: "Norm".to_string(),
            overlay: false,
            use_group_color: true,
            show_drop_lines: true,
            legend_style: "Detailed".to_string(),
            show_group: true,
            show_base: true,
            show_delta: false,
            group_color: None,
            baseline_duration_sec: None,
            drug_apply_time_sec: None,
            drug_apply_tolerance_sec: None,
            baseline_warning_threshold_pct: None,
            custom_title: String::new(),
        }
    }

    fn make_signal() -> ProcessedSignal {
        ProcessedSignal {
            time_sec: vec![0.0, 0.1, 0.2, 0.3],
            capacitance: vec![10.0, 12.0, 14.0, 16.0],
            drop_time: 0.2,
            delta_capacitance: 2.5,
            initial_avg: 10.0,
            effective_baseline_points: INITIAL_BASELINE_POINTS.min(4),
            effective_baseline_duration_sec: 0.4,
            baseline_was_auto_shortened: false,
            drop_detection_source: "window".to_string(),
            drop_search_fallback_used: false,
            timing_warning_details: Vec::new(),
            baseline_warning_status: "ok".to_string(),
            baseline_tail_offset_pct: 0.0,
            baseline_rise_offset_pct: 0.0,
            baseline_tail_warning_hit: false,
            baseline_rise_warning_hit: false,
        }
    }

    #[test]
    fn simple_legend_uses_sample_name_only() {
        let mut settings = make_settings();
        settings.legend_style = "Simple".to_string();
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF", "ok", false);
        assert_eq!(label, "N 3");
    }

    #[test]
    fn detailed_legend_includes_enabled_metadata() {
        let mut settings = make_settings();
        settings.show_delta = true;
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF", "ok", false);
        assert_eq!(label, "[GroupA] N 3 (Base:10.00 pF, Δ:2.50pF)");
    }

    #[test]
    fn overlay_group_color_returns_nolegend() {
        let settings = make_settings();
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF", "ok", true);
        assert_eq!(label, "_nolegend_");
    }

    #[test]
    fn warning_status_shown_in_label() {
        let settings = make_settings();
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF", "warning", false);
        assert!(label.contains("[!]"));
    }

    #[test]
    fn time_axis_is_drop_aligned() {
        let signal = make_signal(); // drop_time = 0.2
        let (x, _, _) = transform_signal_for_display(&signal, "Raw");
        // x[0] = 0.0 - 0.2 = -0.2, x[2] = 0.2 - 0.2 = 0.0
        assert!((x[0] - (-0.2)).abs() < 1e-10);
        assert!((x[2] - 0.0).abs() < 1e-10);
    }

    #[test]
    fn display_mode_to_y_unit_matches_python_behavior() {
        assert_eq!(display_mode_to_y_unit("Norm"), "Normalized (%)");
        assert_eq!(display_mode_to_y_unit("Raw"), "Raw Capacitance (pF)");
        assert_eq!(display_mode_to_y_unit("Base"), "Baseline Capacitance (pF)");
    }
}
