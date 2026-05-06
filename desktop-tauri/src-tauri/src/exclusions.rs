use crate::config::DIXON_Q_EXCLUSION_METHOD;
use crate::models::ExcludedSample;

pub fn max_excluded_samples(sample_count: usize) -> usize {
    if sample_count < 5 {
        0
    } else {
        sample_count / 5
    }
}

pub fn is_dixon_q_exclusion(sample: &ExcludedSample) -> bool {
    sample.method.trim().to_lowercase() == DIXON_Q_EXCLUSION_METHOD
}

pub fn dixon_q_exception_allowed(sample_count: usize) -> bool {
    sample_count >= 3 && sample_count < 5
}

pub fn current_excluded_samples(excluded: &[ExcludedSample], all_files: &[String]) -> Vec<ExcludedSample> {
    let allowed_count = max_excluded_samples(all_files.len());
    let dixon_exception_available = dixon_q_exception_allowed(all_files.len());
    if allowed_count == 0 && !dixon_exception_available {
        return Vec::new();
    }

    let file_keys: std::collections::HashMap<String, &String> =
        all_files.iter().map(|f| (f.to_lowercase(), f)).collect();
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut current: Vec<ExcludedSample> = Vec::new();
    let mut dixon_exception_used = false;

    for excluded_sample in excluded {
        let key = excluded_sample.file_name.to_lowercase();
        if !file_keys.contains_key(&key) || seen.contains(&key) {
            continue;
        }
        let is_dixon_exc = allowed_count == 0
            && dixon_exception_available
            && !dixon_exception_used
            && is_dixon_q_exclusion(excluded_sample);
        if current.len() >= allowed_count && !is_dixon_exc {
            continue;
        }
        let canonical_name = file_keys[&key].clone();
        current.push(ExcludedSample {
            file_name: canonical_name,
            reason: excluded_sample.reason.trim().to_string(),
            method: excluded_sample.method.trim().to_string(),
        });
        if is_dixon_exc {
            dixon_exception_used = true;
        }
        seen.insert(key);
        if current.len() >= allowed_count && !dixon_exception_available {
            break;
        }
    }
    current
}

pub fn current_excluded_file_names(excluded: &[ExcludedSample], all_files: &[String]) -> std::collections::HashSet<String> {
    current_excluded_samples(excluded, all_files)
        .into_iter()
        .map(|e| e.file_name)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_exc(file_name: &str) -> ExcludedSample {
        ExcludedSample { file_name: file_name.to_string(), reason: String::new(), method: String::new() }
    }
    fn mk_dixon(file_name: &str) -> ExcludedSample {
        ExcludedSample {
            file_name: file_name.to_string(),
            reason: String::new(),
            method: DIXON_Q_EXCLUSION_METHOD.to_string(),
        }
    }

    #[test]
    fn max_excluded_samples_rules() {
        assert_eq!(max_excluded_samples(0), 0);
        assert_eq!(max_excluded_samples(4), 0);
        assert_eq!(max_excluded_samples(5), 1);
        assert_eq!(max_excluded_samples(9), 1);
        assert_eq!(max_excluded_samples(10), 2);
    }

    #[test]
    fn n_lt_5_excludes_nothing() {
        let files: Vec<String> = (1..=4).map(|i| format!("{i}.xlsx")).collect();
        let excluded = vec![mk_exc("1.xlsx")];
        assert!(current_excluded_samples(&excluded, &files).is_empty());
    }

    #[test]
    fn n_eq_5_allows_one_exclusion() {
        let files: Vec<String> = (1..=5).map(|i| format!("{i}.xlsx")).collect();
        let excluded = vec![mk_exc("1.xlsx"), mk_exc("2.xlsx")];
        let result = current_excluded_samples(&excluded, &files);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].file_name, "1.xlsx");
    }

    #[test]
    fn dixon_exception_n3() {
        let files: Vec<String> = (1..=3).map(|i| format!("{i}.xlsx")).collect();
        let excluded = vec![mk_dixon("1.xlsx")];
        let result = current_excluded_samples(&excluded, &files);
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn dixon_exception_n3_only_one_allowed() {
        let files: Vec<String> = (1..=3).map(|i| format!("{i}.xlsx")).collect();
        let excluded = vec![mk_dixon("1.xlsx"), mk_dixon("2.xlsx")];
        let result = current_excluded_samples(&excluded, &files);
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn non_dixon_n3_excluded_nothing() {
        let files: Vec<String> = (1..=3).map(|i| format!("{i}.xlsx")).collect();
        let excluded = vec![mk_exc("1.xlsx")];
        assert!(current_excluded_samples(&excluded, &files).is_empty());
    }
}
