from __future__ import annotations

import json
import os

from .config import DEFAULT_MEDICINE_COUNT, MAX_MEDICINES, METADATA_FILENAME
from .models import ExperimentMetadata, MedicineEntry


def metadata_file_path(folder_path: str) -> str:
    return os.path.join(folder_path, METADATA_FILENAME)


def default_experiment_metadata() -> ExperimentMetadata:
    return ExperimentMetadata(
        medicine_count=DEFAULT_MEDICINE_COUNT,
        medicines=[MedicineEntry(name="", dose="") for _ in range(DEFAULT_MEDICINE_COUNT)],
    )


def _normalize_metadata(raw_data: object) -> ExperimentMetadata:
    if not isinstance(raw_data, dict):
        raise ValueError("Metadata content must be a JSON object.")

    medicine_count = raw_data.get("medicine_count", DEFAULT_MEDICINE_COUNT)
    medicines = raw_data.get("medicines", [])

    if not isinstance(medicine_count, int):
        raise ValueError("medicine_count must be an integer.")
    if not isinstance(medicines, list):
        raise ValueError("medicines must be a list.")

    medicine_count = max(0, min(MAX_MEDICINES, medicine_count))

    entries: list[MedicineEntry] = []
    for item in medicines[:medicine_count]:
        if not isinstance(item, dict):
            raise ValueError("Each medicine entry must be an object.")

        name = item.get("name", "")
        dose = item.get("dose", "")
        if not isinstance(name, str) or not isinstance(dose, str):
            raise ValueError("Medicine name and dose must be strings.")
        entries.append(MedicineEntry(name=name.strip(), dose=dose.strip()))

    while len(entries) < medicine_count:
        entries.append(MedicineEntry(name="", dose=""))

    return ExperimentMetadata(medicine_count=medicine_count, medicines=entries)


def load_experiment_metadata(folder_path: str) -> tuple[ExperimentMetadata, str | None]:
    path = metadata_file_path(folder_path)
    if not os.path.exists(path):
        return default_experiment_metadata(), None

    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            raw_data = json.load(file_obj)
        return _normalize_metadata(raw_data), None
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return default_experiment_metadata(), f"Metadata file was reset because it could not be read: {exc}"


def save_experiment_metadata(folder_path: str, metadata: ExperimentMetadata) -> None:
    path = metadata_file_path(folder_path)
    medicine_count = max(0, min(MAX_MEDICINES, metadata.medicine_count))
    medicines = list(metadata.medicines[:medicine_count])
    while len(medicines) < medicine_count:
        medicines.append(MedicineEntry(name="", dose=""))

    payload = {
        "medicine_count": medicine_count,
        "medicines": [{"name": entry.name.strip(), "dose": entry.dose.strip()} for entry in medicines],
    }

    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
