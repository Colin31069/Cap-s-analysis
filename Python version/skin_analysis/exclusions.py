from __future__ import annotations

from collections.abc import Sequence

from .models import ExcludedSample


def max_excluded_samples(sample_count: int) -> int:
    if sample_count < 5:
        return 0
    return sample_count // 5


def current_excluded_samples(
    excluded_samples: Sequence[ExcludedSample],
    all_files: Sequence[str],
) -> list[ExcludedSample]:
    allowed_count = max_excluded_samples(len(all_files))
    if allowed_count <= 0:
        return []

    file_names_by_key = {file_name.casefold(): file_name for file_name in all_files}
    seen: set[str] = set()
    current: list[ExcludedSample] = []

    for excluded_sample in excluded_samples:
        key = excluded_sample.file_name.casefold()
        if key not in file_names_by_key or key in seen:
            continue

        current.append(
            ExcludedSample(
                file_name=file_names_by_key[key],
                reason=excluded_sample.reason.strip(),
            )
        )
        seen.add(key)
        if len(current) >= allowed_count:
            break

    return current


def current_excluded_file_names(
    excluded_samples: Sequence[ExcludedSample],
    all_files: Sequence[str],
) -> set[str]:
    return {
        excluded_sample.file_name
        for excluded_sample in current_excluded_samples(excluded_samples, all_files)
    }
