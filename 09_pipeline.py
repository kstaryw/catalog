# -----------------------------------------------
#  9. Data pipeline:
# 
#  Write a program that automates the 
#  sequential execution of previously created 
#  script files, ensuring that each script 
#  runs to completion before the next begins. 
#  This program aims to streamline the 
#  generation of outputs from all your 
#  previous files, consolidating the 
#  results into one sequence.
# -----------------------------------------------
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


STEPS: List[Tuple[str, str]] = [
    ("01_pull", "01_pull.py"),
    ("02_combine", "02_combine.py"),
    ("03_parse", "03_parse.py"),
    ("04_clean", "04_clean.py"),
    ("05_extract", "05_extract.py"),
    ("06_frequency", "06_frequency.py"),
    ("07_visualization", "07_visualization.py"),
    ("08_export", "08_export.py"),
]


def run_step(script_path: Path) -> None:
    """
    Run one script in a subprocess using the same Python interpreter
    that is running this pipeline.
    """
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    # Use sys.executable to ensure we run with the same env (venv/conda)
    cmd = [sys.executable, str(script_path)]

    print(f"\n========== RUN: {script_path.name} ==========")
    print("Command:", " ".join(cmd))

    # capture_output=False streams output live to terminal (best for debugging)
    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {script_path.name} (exit code {result.returncode})")

    print(f"========== DONE: {script_path.name} ==========")


def slice_steps(start_at: str | None, end_at: str | None) -> List[Tuple[str, str]]:
    keys = [k for k, _ in STEPS]

    if start_at is None:
        start_idx = 0
    else:
        if start_at not in keys:
            raise ValueError(f"--start-at must be one of: {', '.join(keys)}")
        start_idx = keys.index(start_at)

    if end_at is None:
        end_idx = len(STEPS) - 1
    else:
        if end_at not in keys:
            raise ValueError(f"--end-at must be one of: {', '.join(keys)}")
        end_idx = keys.index(end_at)

    if end_idx < start_idx:
        raise ValueError("--end-at must come after --start-at")

    return STEPS[start_idx : end_idx + 1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full catalog data pipeline (01 -> 08).")
    ap.add_argument(
        "--start-at",
        default=None,
        help="Start step key (e.g., 03_parse). Useful if earlier steps already ran.",
    )
    ap.add_argument(
        "--end-at",
        default=None,
        help="End step key (e.g., 06_frequency). Useful for partial runs.",
    )
    args = ap.parse_args()

    project_root = Path(".").resolve()

    # Choose subset if requested
    steps_to_run = slice_steps(args.start_at, args.end_at)

    print("Pipeline steps:")
    for k, f in steps_to_run:
        print(f"  - {k}: {f}")

    # Run sequentially
    for key, filename in steps_to_run:
        script_path = project_root / filename
        try:
            run_step(script_path)
        except Exception as e:
            print("\n!!!!!!!! PIPELINE FAILED !!!!!!!!")
            print(f"Step: {key} ({filename})")
            print(f"Error: {e}")
            print("Tips:")
            print(f"  - Run the failing step alone: python {filename}")
            print("  - Check that prior outputs exist (dependency files).")
            sys.exit(1)

    print("\n✅ Pipeline completed successfully!")


if __name__ == "__main__":
    main()