from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def read_csv_records(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [{str(key): str(value or "") for key, value in row.items()} for row in reader]


def write_csv_records(path: Path, columns: list[str], records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({column: stringify(record.get(column, "")) for column in columns})


def stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)
