use crate::config::INITIAL_BASELINE_POINTS;
use crate::models::{PlotRequest, PlotSeries, ProcessedSignal};

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
    let mut x_plot = signal.time_sec.clone();
    let mut y_plot = signal.capacitance.clone();
    let base = signal.initial_avg;
    let delta_raw = signal.delta_capacitance;

    let delta_label = match display_mode {
        "Norm" => {
            y_plot = signal
                .capacitance
                .iter()
                .map(|value| (value / base) * 100.0)
                .collect();
            let delta_pct = (((base + delta_raw) / base) * 100.0) - 100.0;
            format!("Δ:{delta_pct:.2}%")
        }
        "Base" => {
            let limit = INITIAL_BASELINE_POINTS.min(signal.capacitance.len());
            x_plot = signal.time_sec[..limit].to_vec();
            y_plot = signal.capacitance[..limit].to_vec();
            format!("Δ:{delta_raw:.2}pF")
        }
        _ => format!("Δ:{delta_raw:.2}pF"),
    };

    (x_plot, y_plot, delta_label)
}

pub fn build_legend_label(
    sample_name: &str,
    settings: &PlotRequest,
    base: f64,
    delta_label: &str,
) -> String {
    if settings.legend_style == "Simple" {
        return format!("N {sample_name}");
    }

    let mut parts = Vec::new();
    if settings.show_group {
        parts.push(format!("[{}]", settings.l1));
    }
    parts.push(format!("N {sample_name}"));

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
) -> PlotSeries {
    let (x, y, delta_label) = transform_signal_for_display(signal, &settings.display_mode);
    let legend_label = build_legend_label(sample_name, settings, signal.initial_avg, &delta_label);

    PlotSeries {
        sample_name: sample_name.to_string(),
        x,
        y,
        drop_time: signal.drop_time,
        line_style: line_style.to_string(),
        color,
        legend_label,
    }
}

#[cfg(test)]
mod tests {
    use super::{build_legend_label, display_mode_to_y_unit, transform_signal_for_display};
    use crate::models::{PlotRequest, ProcessedSignal};

    fn make_settings() -> PlotRequest {
        PlotRequest {
            root_path: "/tmp".to_string(),
            l1: "GroupA".to_string(),
            l2: "10uL".to_string(),
            l3: "PBS".to_string(),
            display_mode: "Norm".to_string(),
            overlay: false,
            use_group_color: true,
            show_drop_lines: true,
            legend_style: "Detailed".to_string(),
            show_group: true,
            show_base: true,
            show_delta: false,
            group_color: None,
        }
    }

    fn make_signal() -> ProcessedSignal {
        ProcessedSignal {
            time_sec: vec![0.0, 0.1, 0.2, 0.3],
            capacitance: vec![10.0, 12.0, 14.0, 16.0],
            drop_time: 0.2,
            delta_capacitance: 2.5,
            initial_avg: 10.0,
        }
    }

    #[test]
    fn simple_legend_uses_sample_name_only() {
        let mut settings = make_settings();
        settings.legend_style = "Simple".to_string();
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF");
        assert_eq!(label, "N 3");
    }

    #[test]
    fn detailed_legend_includes_enabled_metadata() {
        let mut settings = make_settings();
        settings.show_delta = true;
        let label = build_legend_label("3", &settings, 10.0, "Δ:2.50pF");
        assert_eq!(label, "[GroupA] N 3 (Base:10.00 pF, Δ:2.50pF)");
    }

    #[test]
    fn transform_signal_for_normalized_mode() {
        let (x, y, delta_label) = transform_signal_for_display(&make_signal(), "Norm");
        assert_eq!(x, vec![0.0, 0.1, 0.2, 0.3]);
        assert_eq!(y, vec![100.0, 120.0, 140.0, 160.0]);
        assert_eq!(delta_label, "Δ:25.00%");
    }

    #[test]
    fn transform_signal_for_raw_mode() {
        let (x, y, delta_label) = transform_signal_for_display(&make_signal(), "Raw");
        assert_eq!(x, vec![0.0, 0.1, 0.2, 0.3]);
        assert_eq!(y, vec![10.0, 12.0, 14.0, 16.0]);
        assert_eq!(delta_label, "Δ:2.50pF");
    }

    #[test]
    fn transform_signal_for_baseline_mode() {
        let (x, y, delta_label) = transform_signal_for_display(&make_signal(), "Base");
        assert_eq!(x, vec![0.0, 0.1, 0.2, 0.3]);
        assert_eq!(y, vec![10.0, 12.0, 14.0, 16.0]);
        assert_eq!(delta_label, "Δ:2.50pF");
    }

    #[test]
    fn display_mode_to_y_unit_matches_python_behavior() {
        assert_eq!(display_mode_to_y_unit("Norm"), "Normalized (%)");
        assert_eq!(display_mode_to_y_unit("Raw"), "Raw Capacitance (pF)");
        assert_eq!(display_mode_to_y_unit("Base"), "Baseline Capacitance (pF)");
    }
}
