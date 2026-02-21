# -----------------------------------------------
#  14. New and Discontinued Subjects:
# 
#  Identify subjects that were offered in 
#  1996 but no longer exist in 2024, as 
#  well as new subjects introduced in 2024. 
#  Explore possible reasons for these changes.
# -----------------------------------------------


from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Set

IN_1996 = Path("10_mit_1996.json")
IN_2024 = Path("11_mit_2024.json")

OUT_DIR = Path("data/subject_changes")
OUT_CSV = OUT_DIR / "subject_changes.csv"


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def subject_prefix_1996(subject_number: str) -> str | None:
    """
    Example:
        '1.125' -> '1'
    """
    if not subject_number:
        return None
    m = re.match(r"^([0-9A-Z]+)\.", subject_number.strip())
    return m.group(1) if m else None


def subject_prefix_2024(course_id: str) -> str | None:
    """
    Example:
        '21G.001' -> '21G'
        '6.100A'  -> '6'
        'CMS.100' -> 'CMS'
    """
    if not course_id:
        return None
    m = re.match(r"^([0-9A-Z]+)\.", course_id.strip())
    return m.group(1) if m else None


def collect_subjects_1996(data) -> Set[str]:
    subjects = set()
    for r in data:
        s = subject_prefix_1996(r.get("subject_number", ""))
        if s:
            subjects.add(s)
    return subjects


def collect_subjects_2024(data) -> Set[str]:
    subjects = set()
    for r in data:
        s = subject_prefix_2024(r.get("course_id", ""))
        if s:
            subjects.add(s)
    return subjects


def main():
    data_1996 = load_json(IN_1996)
    data_2024 = load_json(IN_2024)

    subj_1996 = collect_subjects_1996(data_1996)
    subj_2024 = collect_subjects_2024(data_2024)

    discontinued = sorted(subj_1996 - subj_2024)
    new_subjects = sorted(subj_2024 - subj_1996)
    persistent = sorted(subj_1996 & subj_2024)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUT_CSV, "w", encoding="utf-8") as f:
        f.write("category,subject_prefix\n")
        for s in discontinued:
            f.write(f"discontinued,{s}\n")
        for s in new_subjects:
            f.write(f"new,{s}\n")
        for s in persistent:
            f.write(f"persistent,{s}\n")

    print(f"[done] 1996 subjects: {len(subj_1996)}")
    print(f"[done] 2024 subjects: {len(subj_2024)}")
    print(f"[done] Persistent subjects: {len(persistent)}")
    print(f"[done] Discontinued subjects: {len(discontinued)}")
    print(f"[done] New subjects: {len(new_subjects)}")
    print(f"[done] CSV -> {OUT_CSV}")

    print("\n=== Discontinued Subjects (1996 only) ===")
    print(discontinued)

    print("\n=== New Subjects (2024 only) ===")
    print(new_subjects)


if __name__ == "__main__":
    main()