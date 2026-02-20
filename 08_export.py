# -----------------------------------------------
#  8. Export a Clean Formatted Dataset
#  of the Entire University Catalog:
# 
#  Export a Clean Formatted Dataset of 
#  the Entire University Catalog: The 
#  dataset you would have liked when you 
#  started. Prepare and export a clean, 
#  well-formatted dataset encompassing 
#  the entire university catalog. This 
#  dataset should be in a form that is 
#  readily usable for analysis and 
#  visualization, reflecting the cleaned 
#  and consolidated data you've worked 
#  with throughout the project. Document 
#  the structure of your dataset, including 
#  a description of columns, data types, and 
#  any assumptions or decisions made during 
#  the data preparation process.
# -----------------------------------------------
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


IN_JSON = Path("data/clean/ne_courses_clean.json")
OUT_DIR = Path("data/final")
OUT_JSON = OUT_DIR / "ne_catalog_dataset.json"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_float_or_none(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def normalize_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce consistent types + keys.
    """
    subject_file = str(r.get("subject_file", "")).strip()
    subject = str(r.get("subject", "")).strip().upper()
    number = str(r.get("number", "")).strip().upper()
    course_code = str(r.get("course_code", "")).strip().upper()

    title = str(r.get("title", "")).strip()
    description = str(r.get("description", "")).strip()

    credits_raw = r.get("credits_raw")
    credits_raw = str(credits_raw).strip() if credits_raw is not None else None

    credits_min = to_float_or_none(r.get("credits_min"))
    credits_max = to_float_or_none(r.get("credits_max"))

    return {
        "subject_file": subject_file,
        "subject": subject,
        "number": number,
        "course_code": course_code,
        "title": title,
        "description": description,
        "credits_raw": credits_raw,
        "credits_min": credits_min,
        "credits_max": credits_max,
    }


def main() -> None:
    if not IN_JSON.exists():
        raise FileNotFoundError(
            f"Missing cleaned dataset: {IN_JSON}\n"
            "Run 04_clean.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_data: List[Dict[str, Any]] = json.loads(IN_JSON.read_text(encoding="utf-8"))

    # Normalize/validate records
    records: List[Dict[str, Any]] = []
    for r in raw_data:
        rec = normalize_record(r)

        # Minimal validity checks to ensure the exported dataset is usable
        if not rec["course_code"] or not rec["title"]:
            continue
        if rec["credits_min"] is None or rec["credits_max"] is None:
            continue

        records.append(rec)

    # Sort for nicer downstream browsing
    def sort_key(x: Dict[str, Any]) -> tuple:
        # Number can be like "1341A" so keep lexicographic fallback
        return (x["subject"], x["number"], x["title"].lower())

    records.sort(key=sort_key)

    # Build schema documentation
    schema = {
        "dataset_name": "Northeastern University Course Catalog (Course Descriptions)",
        "record_count": len(records),
        "fields": [
            {
                "name": "subject_file",
                "type": "string",
                "description": "Source subject page filename (from acquisition/combination step).",
                "example": "arch.html",
            },
            {
                "name": "subject",
                "type": "string",
                "description": "Course subject/department code.",
                "example": "CS",
            },
            {
                "name": "number",
                "type": "string",
                "description": "Course number (may include suffix letters).",
                "example": "2500",
            },
            {
                "name": "course_code",
                "type": "string",
                "description": "Normalized subject + number, used as a primary identifier.",
                "example": "CS 2500",
            },
            {
                "name": "title",
                "type": "string",
                "description": "Course title (cleaned).",
                "example": "Fundamentals of Computer Science",
            },
            {
                "name": "description",
                "type": "string",
                "description": "Course description text (cleaned, whitespace-normalized).",
                "example": "Introduces programming and problem solving ...",
            },
            {
                "name": "credits_raw",
                "type": "string|null",
                "description": "Original credits string before numeric normalization.",
                "example": "1-4 Hours",
            },
            {
                "name": "credits_min",
                "type": "number",
                "description": "Minimum credits if a range; otherwise equals credits_max.",
                "example": 1.0,
            },
            {
                "name": "credits_max",
                "type": "number",
                "description": "Maximum credits if a range; otherwise equals credits_min.",
                "example": 4.0,
            },
        ],
    }

    assumptions = [
        "Catalog pages were downloaded from Northeastern's public course descriptions site and consolidated.",
        "HTML was parsed using DOM structure (course blocks) and converted to structured records.",
        "Whitespace was normalized and any stray HTML tags were defensively removed.",
        "Credits were normalized into numeric credits_min/credits_max; ranges like '1-4 Hours' become (1.0, 4.0).",
        "Records missing a course_code, title, or numeric credits were excluded from the final export.",
        "The exported file is sorted by (subject, number, title) for readability; this does not change the data content.",
    ]

    export_obj = {
        "metadata": {
            "generated_at_utc": iso_now(),
            "input_file": str(IN_JSON),
            "output_file": str(OUT_JSON),
            "format_version": "1.0",
        },
        "schema": schema,
        "assumptions": assumptions,
        "records": records,
    }

    OUT_JSON.write_text(json.dumps(export_obj, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] Exported final dataset with {len(records)} records")
    print(f"[done] -> {OUT_JSON}")


if __name__ == "__main__":
    main()