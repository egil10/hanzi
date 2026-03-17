from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HSK_SOURCE_URL = "https://raw.githubusercontent.com/ivankra/hsk30/master/hsk30-chars.csv"
UNIHAN_SOURCE_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
DEFAULT_LIMIT = 10_000
UNIHAN_READING_FIELDS = {"kMandarin", "kDefinition"}
UNIHAN_META_FIELDS = {"kGradeLevel", "kUnihanCore2020"}
UNIHAN_IRG_FIELDS = {"kIRG_GSource", "kIRG_SSource", "kTotalStrokes"}
UNIHAN_VARIANT_FIELDS = {"kSimplifiedVariant", "kTraditionalVariant"}


def output_path(limit: int) -> Path:
    return ROOT / "data" / f"hanzi-{limit}.js"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        handle.write(response.read())


def prepare_sources(workspace: Path) -> tuple[Path, Path, Path, Path]:
    hsk_csv = workspace / "hsk30-chars.csv"
    unihan_zip = workspace / "Unihan.zip"
    unihan_dir = workspace / "unihan"

    download_file(HSK_SOURCE_URL, hsk_csv)
    download_file(UNIHAN_SOURCE_URL, unihan_zip)

    with zipfile.ZipFile(unihan_zip) as archive:
        archive.extractall(unihan_dir)

    return (
        hsk_csv,
        unihan_dir / "Unihan_Readings.txt",
        unihan_dir / "Unihan_DictionaryLikeData.txt",
        unihan_dir / "Unihan_IRGSources.txt",
    )


def parse_unihan_line(raw_line: str) -> tuple[str, str, str] | None:
    if not raw_line or raw_line.startswith("#"):
        return None

    line = raw_line.rstrip("\n")
    if not line:
        return None

    parts = line.split("\t", 2)
    if len(parts) != 3:
        return None

    codepoint, field, value = parts
    char = chr(int(codepoint[2:], 16))
    return char, field, value.strip()


def load_unihan_fields(path: Path, allowed_fields: set[str]) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_unihan_line(raw_line)
            if not parsed:
                continue

            char, field, value = parsed
            if field not in allowed_fields:
                continue

            data.setdefault(char, {})[field] = value

    return data


def load_unihan_variants(path: Path) -> dict[str, dict[str, str]]:
    variants: dict[str, dict[str, str]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_unihan_line(raw_line)
            if not parsed:
                continue

            char, field, value = parsed
            if field not in UNIHAN_VARIANT_FIELDS:
                continue

            target = first_variant_char(value)
            if not target:
                continue

            variants.setdefault(char, {})[field] = target

    return variants


def first_variant_char(value: str) -> str:
    for token in value.split():
        match = re.match(r"U\+([0-9A-F]+)", token)
        if match:
            return chr(int(match.group(1), 16))
    return ""


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


def build_hsk_entries(hsk_csv_path: Path, unihan_readings: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    for index, row in enumerate(load_hsk_rows(hsk_csv_path), start=1):
        char = row["Hanzi"].strip()
        traditional = row["Traditional"].strip()
        reading = unihan_readings.get(char, {})
        pinyin = choose_pinyin(reading["kMandarin"]) if reading.get("kMandarin") else ""
        gloss = simplify_definition(reading["kDefinition"]) if reading.get("kDefinition") else ""

        entries.append(
            {
                "rank": index,
                "hanzi": char,
                "traditional": traditional or char,
                "pinyin": pinyin,
                "english": gloss,
                "level": parse_int(row["Level"]),
                "writingLevel": parse_int(row["WritingLevel"]),
                "frequency": parse_int(row["Freq"]),
                "examples": [item for item in row["Examples"].split() if item],
            }
        )

    return entries


def is_bmp_hanzi(char: str) -> bool:
    codepoint = ord(char)
    return 0x3400 <= codepoint <= 0x9FFF


def candidate_sort_key(
    char: str,
    meta: dict[str, str],
    irg: dict[str, str],
) -> tuple[int, int, int, int, int, int]:
    codepoint = ord(char)
    in_basic_block = 0 if 0x4E00 <= codepoint <= 0x9FFF else 1
    grade_level = parse_int(meta.get("kGradeLevel", "")) or 99
    in_core = 0 if meta.get("kUnihanCore2020") else 1
    has_mainland_source = 0 if irg.get("kIRG_GSource") else 1
    has_simplified_source = 0 if irg.get("kIRG_SSource") else 1
    total_strokes = parse_int(irg.get("kTotalStrokes", "")) or 99

    return (
        in_basic_block,
        grade_level,
        in_core,
        has_mainland_source,
        has_simplified_source,
        total_strokes,
    )


def build_unihan_backfill(
    limit: int,
    existing_chars: set[str],
    unihan_readings: dict[str, dict[str, str]],
    unihan_meta: dict[str, dict[str, str]],
    unihan_irg: dict[str, dict[str, str]],
    unihan_variants: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    candidates: list[tuple[tuple[int, int, int, int, int, int], int, str]] = []

    for char, reading in unihan_readings.items():
        if char in existing_chars or not reading.get("kMandarin") or not is_bmp_hanzi(char):
            continue

        # Prefer simplified or script-neutral forms in the main list.
        if unihan_variants.get(char, {}).get("kSimplifiedVariant"):
            continue

        meta = unihan_meta.get(char, {})
        irg = unihan_irg.get(char, {})
        candidates.append((candidate_sort_key(char, meta, irg), ord(char), char))

    candidates.sort()
    remaining = max(limit - len(existing_chars), 0)
    entries: list[dict[str, object]] = []

    for offset, (_, _, char) in enumerate(candidates[:remaining], start=1):
        reading = unihan_readings.get(char, {})
        variants = unihan_variants.get(char, {})

        entries.append(
            {
                "rank": len(existing_chars) + offset,
                "hanzi": char,
                "traditional": variants.get("kTraditionalVariant", char),
                "pinyin": choose_pinyin(reading["kMandarin"]),
                "english": simplify_definition(reading["kDefinition"]) if reading.get("kDefinition") else "",
                "level": 0,
                "writingLevel": 0,
                "frequency": 0,
                "examples": [],
            }
        )

    return entries


def build_entries(
    limit: int,
    hsk_csv_path: Path,
    unihan_readings_path: Path,
    unihan_meta_path: Path,
    unihan_irg_path: Path,
    unihan_variants_path: Path,
) -> list[dict[str, object]]:
    unihan_readings = load_unihan_fields(unihan_readings_path, UNIHAN_READING_FIELDS)
    unihan_meta = load_unihan_fields(unihan_meta_path, UNIHAN_META_FIELDS)
    unihan_irg = load_unihan_fields(unihan_irg_path, UNIHAN_IRG_FIELDS)
    unihan_variants = load_unihan_variants(unihan_variants_path)

    hsk_entries = build_hsk_entries(hsk_csv_path, unihan_readings)
    if limit <= len(hsk_entries):
        return hsk_entries[:limit]

    existing_chars = {entry["hanzi"] for entry in hsk_entries}
    backfill_entries = build_unihan_backfill(
        limit,
        existing_chars,
        unihan_readings,
        unihan_meta,
        unihan_irg,
        unihan_variants,
    )
    return hsk_entries + backfill_entries


def write_output(entries: list[dict[str, object]], limit: int) -> Path:
    output = output_path(limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = "window.HANZI_DATA = " + json.dumps(entries, ensure_ascii=False, indent=2) + ";\n"
    output.write_text(payload, encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build static hanzi data.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Number of characters to emit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        (
            hsk_csv_path,
            unihan_readings_path,
            unihan_meta_path,
            unihan_irg_path,
        ) = prepare_sources(Path(temp_dir))
        entries = build_entries(
            args.limit,
            hsk_csv_path,
            unihan_readings_path,
            unihan_meta_path,
            unihan_irg_path,
            Path(temp_dir) / "unihan" / "Unihan_Variants.txt",
        )

    output = write_output(entries, args.limit)
    print(f"Wrote {len(entries)} entries to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
