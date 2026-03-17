from __future__ import annotations

import csv
import json
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "hanzi-3000.js"
HSK_SOURCE_URL = "https://raw.githubusercontent.com/ivankra/hsk30/master/hsk30-chars.csv"
UNIHAN_SOURCE_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        handle.write(response.read())


def prepare_sources(workspace: Path) -> tuple[Path, Path]:
    hsk_csv = workspace / "hsk30-chars.csv"
    unihan_zip = workspace / "Unihan.zip"
    unihan_dir = workspace / "unihan"
    unihan_readings = unihan_dir / "Unihan_Readings.txt"

    download_file(HSK_SOURCE_URL, hsk_csv)
    download_file(UNIHAN_SOURCE_URL, unihan_zip)

    with zipfile.ZipFile(unihan_zip) as archive:
        archive.extractall(unihan_dir)

    return hsk_csv, unihan_readings


def load_unihan_readings(unihan_readings_path: Path) -> dict[str, dict[str, str]]:
    readings: dict[str, dict[str, str]] = {}

    with unihan_readings_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line or raw_line.startswith("#"):
                continue

            line = raw_line.rstrip("\n")
            if not line:
                continue

            codepoint, field, value = line.split("\t", 2)
            if field not in {"kMandarin", "kDefinition"}:
                continue

            char = chr(int(codepoint[2:], 16))
            readings.setdefault(char, {})[field] = value.strip()

    return readings


def simplify_definition(definition: str) -> str:
    first = re.split(r"[;,]", definition, maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", first).strip()
    return cleaned


def choose_pinyin(reading: str) -> str:
    return reading.split()[0].strip()


def parse_int(value: str) -> int:
    value = value.strip()
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else 0


def load_hsk_rows(hsk_csv_path: Path) -> list[dict[str, str]]:
    with hsk_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_entries(hsk_csv_path: Path, unihan_readings_path: Path) -> list[dict[str, object]]:
    unihan = load_unihan_readings(unihan_readings_path)
    entries: list[dict[str, object]] = []

    for index, row in enumerate(load_hsk_rows(hsk_csv_path), start=1):
        char = row["Hanzi"].strip()
        traditional = row["Traditional"].strip()
        reading = unihan.get(char, {})
        pinyin = choose_pinyin(reading["kMandarin"]) if reading.get("kMandarin") else ""
        gloss = simplify_definition(reading["kDefinition"]) if reading.get("kDefinition") else ""

        entries.append(
            {
                "rank": index,
                "hanzi": char,
                "traditional": traditional,
                "pinyin": pinyin,
                "english": gloss,
                "level": parse_int(row["Level"]),
                "writingLevel": parse_int(row["WritingLevel"]),
                "frequency": parse_int(row["Freq"]),
                "examples": [item for item in row["Examples"].split() if item],
            }
        )

    return entries


def write_output(entries: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = "window.HANZI_DATA = " + json.dumps(entries, ensure_ascii=False, indent=2) + ";\n"
    OUTPUT.write_text(payload, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        hsk_csv_path, unihan_readings_path = prepare_sources(Path(temp_dir))
        entries = build_entries(hsk_csv_path, unihan_readings_path)
    write_output(entries)
    print(f"Wrote {len(entries)} entries to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
