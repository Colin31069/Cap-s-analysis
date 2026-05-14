use std::path::Path;

use crate::config::{DEFAULT_MEDICINE_COUNT, MAX_MEDICINES, METADATA_FILENAME};
use crate::models::{AppError, ExcludedSample, ExperimentMetadata, MedicineEntry};

pub fn metadata_file_path(folder_path: &Path) -> std::path::PathBuf {
    folder_path.join(METADATA_FILENAME)
}

pub fn default_experiment_metadata() -> ExperimentMetadata {
    ExperimentMetadata {
        medicine_count: DEFAULT_MEDICINE_COUNT,
        medicines: (0..DEFAULT_MEDICINE_COUNT)
            .map(|_| MedicineEntry { name: String::new(), dose: String::new() })
            .collect(),
        excluded_samples: Vec::new(),
    }
}

fn normalize_metadata(raw: serde_json::Value) -> Result<ExperimentMetadata, String> {
    let obj = raw.as_object().ok_or("Metadata content must be a JSON object.")?;

    let medicine_count = obj
        .get("medicine_count")
        .and_then(|v| v.as_u64())
        .map(|v| v as usize)
        .unwrap_or(DEFAULT_MEDICINE_COUNT)
        .clamp(0, MAX_MEDICINES);

    let medicines_raw = obj.get("medicines").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut medicines: Vec<MedicineEntry> = medicines_raw
        .iter()
        .take(medicine_count)
        .map(|item| {
            let m = item.as_object();
            MedicineEntry {
                name: m
                    .and_then(|m| m.get("name"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
                dose: m
                    .and_then(|m| m.get("dose"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
            }
        })
        .collect();
    while medicines.len() < medicine_count {
        medicines.push(MedicineEntry { name: String::new(), dose: String::new() });
    }

    let excluded_raw = obj
        .get("excluded_samples")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut excluded_samples: Vec<ExcludedSample> = Vec::new();
    let mut seen: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    for item in &excluded_raw {
        let m = match item.as_object() {
            Some(m) => m,
            None => continue,
        };
        let raw_file_name = m.get("file_name").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
        let file_name = Path::new(&raw_file_name)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();
        if file_name.is_empty() {
            continue;
        }
        let reason = m.get("reason").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
        let method = m.get("method").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
        let key = file_name.to_lowercase();
        if let Some(&idx) = seen.get(&key) {
            let e = &mut excluded_samples[idx];
            if e.reason.is_empty() && !reason.is_empty() {
                e.reason = reason;
            }
            if e.method.is_empty() && !method.is_empty() {
                e.method = method;
            }
        } else {
            seen.insert(key, excluded_samples.len());
            excluded_samples.push(ExcludedSample { file_name, reason, method });
        }
    }

    Ok(ExperimentMetadata { medicine_count, medicines, excluded_samples })
}

pub fn load_experiment_metadata(folder_path: &Path) -> (ExperimentMetadata, Option<String>) {
    let path = metadata_file_path(folder_path);
    if !path.exists() {
        return (default_experiment_metadata(), None);
    }
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(e) => {
            return (
                default_experiment_metadata(),
                Some(format!("Metadata file was reset because it could not be read: {e}")),
            );
        }
    };
    let raw: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(e) => {
            return (
                default_experiment_metadata(),
                Some(format!("Metadata file was reset because it could not be parsed: {e}")),
            );
        }
    };
    match normalize_metadata(raw) {
        Ok(meta) => (meta, None),
        Err(e) => (
            default_experiment_metadata(),
            Some(format!("Metadata file was reset because it was invalid: {e}")),
        ),
    }
}

pub fn save_experiment_metadata(folder_path: &Path, metadata: &ExperimentMetadata) -> Result<(), AppError> {
    let medicine_count = metadata.medicine_count.clamp(0, MAX_MEDICINES);
    let mut medicines_json: Vec<serde_json::Value> = metadata
        .medicines
        .iter()
        .take(medicine_count)
        .map(|m| serde_json::json!({"name": m.name.trim(), "dose": m.dose.trim()}))
        .collect();
    while medicines_json.len() < medicine_count {
        medicines_json.push(serde_json::json!({"name": "", "dose": ""}));
    }

    let excluded_json: Vec<serde_json::Value> = metadata
        .excluded_samples
        .iter()
        .filter_map(|e| {
            let file_name = Path::new(&e.file_name)
                .file_name()
                .and_then(|n| n.to_str())
                .map(|s| s.trim().to_string())
                .unwrap_or_default();
            if file_name.is_empty() {
                return None;
            }
            let mut obj = serde_json::json!({"file_name": file_name, "reason": e.reason.trim()});
            if !e.method.trim().is_empty() {
                obj["method"] = serde_json::Value::String(e.method.trim().to_string());
            }
            Some(obj)
        })
        .collect();

    let payload = serde_json::json!({
        "medicine_count": medicine_count,
        "medicines": medicines_json,
        "excluded_samples": excluded_json,
    });
    let json_str = serde_json::to_string_pretty(&payload)
        .map_err(|e| AppError::new("serialize_error", e.to_string()))?;
    std::fs::write(metadata_file_path(folder_path), json_str)?;
    Ok(())
}
