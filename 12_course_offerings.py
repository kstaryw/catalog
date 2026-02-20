# -----------------------------------------------
#  12. Course Offerings Over Time
# 
#  After extracting the course data from 
#  both the 1996 and present catalogs, 
#  analyze the number of courses offered 
#  in various departments. Are there any 
#  departments that have significantly 
#  expanded or reduced their course offerings? 
#  If so, identify them and discuss possible 
#  reasons for these changes.
# -----------------------------------------------

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt


IN_1996_JSON = Path("10_mit_1996.json")
IN_2024_JSON = Path("11_mit_2024.json")

# If your instructor used .txt filenames but the content is JSON, we support that too:
IN_1996_TXT = Path("10_mit_1996.txt")
IN_2024_TXT = Path("11_mit_2024.txt")

OUT_DIR = Path("data/analysis")
OUT_CSV = OUT_DIR / "course_offerings_by_dept.csv"
OUT_PNG_EXPAND = OUT_DIR / "top_changes_expanded.png"
OUT_PNG_REDUCE = OUT_DIR / "top_changes_reduced.png"


def load_json_flexible(path_json: Path, path_txt: Path) -> List[Dict[str, Any]]:
    """
    Load JSON from either .json or .txt (if .txt contains JSON).
    """
    if path_json.exists():
        return json.loads(path_json.read_text(encoding="utf-8"))
    if path_txt.exists():
        return json.loads(path_txt.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Missing input file: {path_json} (or {path_txt})")


def dept_from_1996(subject_number: str) -> Optional[str]:
    """
    1996 ids look like '1.125'. Department proxy is the part before the first dot.
    """
    if not subject_number:
        return None
    m = re.match(r"^\s*([0-9A-Z]+)\.", str(subject_number).strip())
    if not m:
        return None
    return m.group(1)


def dept_from_2024(course_id: str) -> Optional[str]:
    """
    2024 ids can be:
      '1.00', '6.100A', '21H.001', 'CMS.100', '16.C20' ...
    Department proxy = prefix before first dot.
    """
    if not course_id:
        return None
    s = str(course_id).strip()
    m = re.match(r"^\s*([0-9A-Z]+)\.", s)
    if not m:
        return None
    return m.group(1)


def count_by_dept_1996(rows: List[Dict[str, Any]]) -> Counter:
    c = Counter()
    for r in rows:
        dept = dept_from_1996(r.get("subject_number", ""))
        if dept:
            c[dept] += 1
    return c


def count_by_dept_2024(rows: List[Dict[str, Any]]) -> Counter:
    c = Counter()
    for r in rows:
        dept = dept_from_2024(r.get("course_id", ""))
        if dept:
            c[dept] += 1
    return c


@dataclass
class DeptChange:
    dept: str
    n_1996: int
    n_2024: int
    delta: int
    pct_change: Optional[float]  # None if 1996 is 0 (avoid divide by zero)


def compute_changes(c96: Counter, c24: Counter) -> List[DeptChange]:
    depts = sorted(set(c96.keys()) | set(c24.keys()))
    out: List[DeptChange] = []
    for d in depts:
        n96 = int(c96.get(d, 0))
        n24 = int(c24.get(d, 0))
        delta = n24 - n96
        pct = None if n96 == 0 else (delta / n96) * 100.0
        out.append(DeptChange(d, n96, n24, delta, pct))
    return out


def write_csv(changes: List[DeptChange]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    header = "dept,n_1996,n_2024,delta,pct_change\n"
    lines = [header]
    for ch in changes:
        pct = "" if ch.pct_change is None else f"{ch.pct_change:.2f}"
        lines.append(f"{ch.dept},{ch.n_1996},{ch.n_2024},{ch.delta},{pct}\n")
    OUT_CSV.write_text("".join(lines), encoding="utf-8")


def plot_top_changes(changes: List[DeptChange], out_path: Path, kind: str, top_n: int = 15) -> None:
    """
    kind: 'expand' or 'reduce'
    """
    if kind == "expand":
        subset = sorted(changes, key=lambda x: x.delta, reverse=True)[:top_n]
        title = f"Top {top_n} departments by course expansion (2024 - 1996)"
    else:
        subset = sorted(changes, key=lambda x: x.delta)[:top_n]
        title = f"Top {top_n} departments by course reduction (2024 - 1996)"

    depts = [x.dept for x in subset]
    deltas = [x.delta for x in subset]

    plt.figure(figsize=(10, 6))
    plt.bar(depts, deltas)
    plt.title(title)
    plt.xlabel("Department (course number prefix)")
    plt.ylabel("Change in course count")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def print_summary(changes: List[DeptChange]) -> None:
    # Expanded / reduced (absolute delta)
    expanded = sorted(changes, key=lambda x: x.delta, reverse=True)
    reduced = sorted(changes, key=lambda x: x.delta)

    print("\n=== Biggest expansions (absolute) ===")
    for x in expanded[:10]:
        pct = "n/a" if x.pct_change is None else f"{x.pct_change:.1f}%"
        print(f"  Dept {x.dept:>4}: {x.n_1996:>4} -> {x.n_2024:>4}  (Δ {x.delta:+4}, {pct})")

    print("\n=== Biggest reductions (absolute) ===")
    for x in reduced[:10]:
        pct = "n/a" if x.pct_change is None else f"{x.pct_change:.1f}%"
        print(f"  Dept {x.dept:>4}: {x.n_1996:>4} -> {x.n_2024:>4}  (Δ {x.delta:+4}, {pct})")

    # Also show % change leaders (but only where 1996 count is not tiny)
    eligible = [x for x in changes if x.n_1996 >= 20]  # avoid noisy % from tiny bases
    pct_up = sorted(eligible, key=lambda x: (x.pct_change if x.pct_change is not None else -math.inf), reverse=True)
    pct_down = sorted(eligible, key=lambda x: (x.pct_change if x.pct_change is not None else math.inf))

    print("\n=== Biggest expansions (percent, only depts with >=20 courses in 1996) ===")
    for x in pct_up[:10]:
        print(f"  Dept {x.dept:>4}: {x.n_1996:>4} -> {x.n_2024:>4}  ({x.pct_change:.1f}%)")

    print("\n=== Biggest reductions (percent, only depts with >=20 courses in 1996) ===")
    for x in pct_down[:10]:
        print(f"  Dept {x.dept:>4}: {x.n_1996:>4} -> {x.n_2024:>4}  ({x.pct_change:.1f}%)")

    print("\nInterpretation hints (possible reasons):")
    print("- New fields/programs and interdisciplinary growth can increase offerings (e.g., computing/data/AI, design, policy).")
    print("- Department mergers/renaming can shift counts across prefixes (apparent increases/decreases may reflect reorg, not true shrinkage).")
    print("- Curriculum streamlining can reduce catalog size (consolidating similar subjects, retiring legacy offerings).")
    print("- Administrative/catalog practices change over time (more granular topics/seminars in one era vs fewer, broader subjects in another).")


def main() -> None:
    data_1996 = load_json_flexible(IN_1996_JSON, IN_1996_TXT)
    data_2024 = load_json_flexible(IN_2024_JSON, IN_2024_TXT)

    c96 = count_by_dept_1996(data_1996)
    c24 = count_by_dept_2024(data_2024)

    changes = compute_changes(c96, c24)

    # Save table + plots
    write_csv(changes)
    plot_top_changes(changes, OUT_PNG_EXPAND, kind="expand", top_n=15)
    plot_top_changes(changes, OUT_PNG_REDUCE, kind="reduce", top_n=15)

    # Print summary
    print(f"[done] Loaded 1996 courses: {len(data_1996)}")
    print(f"[done] Loaded 2024 courses: {len(data_2024)}")
    print(f"[done] Wrote CSV -> {OUT_CSV}")
    print(f"[done] Wrote plots -> {OUT_PNG_EXPAND}, {OUT_PNG_REDUCE}")

    print_summary(changes)


if __name__ == "__main__":
    main()