use std::fs;
use std::path::Path;

use approx::assert_relative_eq;
use rust_xlsxwriter::Workbook;
use serde::Deserialize;
use skin_analysis_desktop_lib::analysis::{process_single_file, read_xlsx_single};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ParityCases {
    xlsx_cases: Vec<XlsxCase>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct XlsxCase {
    name: String,
    column: String,
    segments: Vec<Segment>,
    expected: Option<ExpectedSignal>,
    expected_error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Segment {
    repeat: usize,
    value: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ExpectedSignal {
    initial_avg: f64,
    drop_time: f64,
    delta_capacitance: serde_json::Value,
}

fn load_cases() -> ParityCases {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("shared")
        .join("parity_cases.json");
    let content = fs::read_to_string(path).unwrap();
    serde_json::from_str(&content).unwrap()
}

fn expand_segments(segments: &[Segment]) -> Vec<f64> {
    let mut values = Vec::new();
    for segment in segments {
        values.extend(std::iter::repeat(segment.value).take(segment.repeat));
    }
    values
}

fn write_case_xlsx(path: &Path, column_name: &str, values: &[f64]) {
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();
    worksheet.write_string(0, 0, column_name).unwrap();
    for (row_index, value) in values.iter().enumerate() {
        worksheet.write_number((row_index + 1) as u32, 0, *value).unwrap();
    }
    workbook.save(path).unwrap();
}

#[test]
fn xlsx_cases_match_shared_expectations() {
    let cases = load_cases();
    let temp = tempfile::tempdir().unwrap();

    for case in cases.xlsx_cases {
        let path = temp.path().join(format!("{}.xlsx", case.name));
        let values = expand_segments(&case.segments);
        write_case_xlsx(&path, &case.column, &values);

        if case.expected_error.as_deref() == Some("missing_column") {
            assert!(read_xlsx_single(&path).is_none(), "{}", case.name);
            assert!(process_single_file(&path).is_none(), "{}", case.name);
            continue;
        }

        let signal = process_single_file(&path).expect("signal should parse");
        let expected = case.expected.expect("expected signal");
        assert_relative_eq!(signal.initial_avg, expected.initial_avg, epsilon = 1e-9);
        assert_relative_eq!(signal.drop_time, expected.drop_time, epsilon = 1e-9);

        match expected.delta_capacitance {
            serde_json::Value::String(value) if value == "NaN" => {
                assert!(signal.delta_capacitance.is_nan(), "{}", case.name);
            }
            serde_json::Value::Number(value) => {
                assert_relative_eq!(
                    signal.delta_capacitance,
                    value.as_f64().unwrap(),
                    epsilon = 1e-9
                );
            }
            other => panic!("unexpected delta expectation for {}: {other}", case.name),
        }
    }
}
