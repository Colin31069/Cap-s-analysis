use std::cmp::Ordering;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
enum NaturalToken {
    Number(u64),
    Text(String),
}

fn tokenize(value: &str) -> Vec<NaturalToken> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut numeric = false;

    for ch in value.chars() {
        if ch.is_ascii_digit() {
            if !numeric && !current.is_empty() {
                tokens.push(NaturalToken::Text(current.to_lowercase()));
                current.clear();
            }
            numeric = true;
            current.push(ch);
        } else {
            if numeric && !current.is_empty() {
                let parsed = current.parse::<u64>().unwrap_or(0);
                tokens.push(NaturalToken::Number(parsed));
                current.clear();
            }
            numeric = false;
            current.push(ch);
        }
    }

    if !current.is_empty() {
        if numeric {
            let parsed = current.parse::<u64>().unwrap_or(0);
            tokens.push(NaturalToken::Number(parsed));
        } else {
            tokens.push(NaturalToken::Text(current.to_lowercase()));
        }
    }

    tokens
}

pub fn compare_natural(left: &str, right: &str) -> Ordering {
    let left_tokens = tokenize(left);
    let right_tokens = tokenize(right);

    for (left_token, right_token) in left_tokens.iter().zip(right_tokens.iter()) {
        let ordering = match (left_token, right_token) {
            (NaturalToken::Number(left_num), NaturalToken::Number(right_num)) => left_num.cmp(right_num),
            (NaturalToken::Text(left_text), NaturalToken::Text(right_text)) => left_text.cmp(right_text),
            (NaturalToken::Number(_), NaturalToken::Text(_)) => Ordering::Less,
            (NaturalToken::Text(_), NaturalToken::Number(_)) => Ordering::Greater,
        };

        if ordering != Ordering::Equal {
            return ordering;
        }
    }

    left_tokens.len().cmp(&right_tokens.len())
}

pub fn get_subfolders(path: &Path) -> Vec<String> {
    if !path.is_dir() {
        return Vec::new();
    }

    let mut folders = fs::read_dir(path)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .filter(|entry| entry.path().is_dir())
        .filter_map(|entry| entry.file_name().into_string().ok())
        .collect::<Vec<_>>();

    folders.sort_by(|left, right| compare_natural(left, right));
    folders
}

pub fn list_xlsx_files(path: &Path) -> Vec<String> {
    if !path.is_dir() {
        return Vec::new();
    }

    let mut files = fs::read_dir(path)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .filter(|entry| entry.path().is_file())
        .filter_map(|entry| entry.file_name().into_string().ok())
        .filter(|name| name.to_ascii_lowercase().ends_with(".xlsx"))
        .collect::<Vec<_>>();

    files.sort_by(|left, right| compare_natural(left, right));
    files
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::{compare_natural, get_subfolders, list_xlsx_files};

    #[test]
    fn natural_sort_orders_numbers_like_people_expect() {
        let mut values = vec!["sample10", "sample2", "sample1"];
        values.sort_by(|left, right| compare_natural(left, right));
        assert_eq!(values, vec!["sample1", "sample2", "sample10"]);
    }

    #[test]
    fn get_subfolders_returns_sorted_directories_only() {
        let temp = tempfile::tempdir().unwrap();
        fs::create_dir(temp.path().join("folder10")).unwrap();
        fs::create_dir(temp.path().join("folder2")).unwrap();
        fs::create_dir(temp.path().join("folder1")).unwrap();
        fs::write(temp.path().join("notes.txt"), "ignore").unwrap();

        assert_eq!(
            get_subfolders(temp.path()),
            vec!["folder1".to_string(), "folder2".to_string(), "folder10".to_string()]
        );
    }

    #[test]
    fn list_xlsx_files_filters_and_sorts() {
        let temp = tempfile::tempdir().unwrap();
        fs::write(temp.path().join("2.xlsx"), "").unwrap();
        fs::write(temp.path().join("10.xlsx"), "").unwrap();
        fs::write(temp.path().join("1.xlsx"), "").unwrap();
        fs::write(temp.path().join("notes.csv"), "").unwrap();

        assert_eq!(
            list_xlsx_files(temp.path()),
            vec!["1.xlsx".to_string(), "2.xlsx".to_string(), "10.xlsx".to_string()]
        );
    }
}
