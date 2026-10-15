from __future__ import annotations

import os
import re


def natural_sort_key(value: str) -> list[int | str]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"([0-9]+)", value)]


def normalize_directory_path(path: str) -> str:
    stripped = path.strip()
    if not stripped:
        return ""

    expanded = os.path.expanduser(stripped)
    return os.path.abspath(os.path.normpath(expanded))


def resolve_directory_path(path: str) -> str | None:
    normalized = normalize_directory_path(path)
    if not normalized or not os.path.isdir(normalized):
        return None
    return normalized


def get_subfolders(path: str) -> list[str]:
    if not os.path.isdir(path):
        return []

    folders = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
    return sorted(folders, key=natural_sort_key)


def list_xlsx_files(path: str) -> list[str]:
    if not os.path.isdir(path):
        return []

    files = [
        name
        for name in os.listdir(path)
        if name.lower().endswith(".xlsx") and not name.startswith("~$") and os.path.isfile(os.path.join(path, name))
    ]
    return sorted(files, key=natural_sort_key)


def discover_experiment_folders(path: str, max_depth: int = 3) -> list[str]:
    """Find separate Excel groups in the root and up to three child levels.

    Return relative paths so identically named folders remain distinct. Files
    are never pooled across directories, and directory symlinks are not followed.
    """
    if max_depth < 0:
        raise ValueError("掃描深度不可小於 0。")
    if not os.path.isdir(path):
        return []

    def report_error(error: OSError) -> None:
        raise error

    groups: list[str] = []
    for current, directories, _files in os.walk(path, onerror=report_error, followlinks=False):
        relative = os.path.relpath(current, path)
        depth = 0 if relative == os.curdir else relative.count(os.sep) + 1
        directories[:] = (
            [name for name in directories if not os.path.islink(os.path.join(current, name))]
            if depth < max_depth else []
        )
        if list_xlsx_files(current):
            groups.append(relative)
    return sorted(groups, key=natural_sort_key)
