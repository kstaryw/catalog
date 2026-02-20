# -----------------------------------------------
#  2. Data Preparation:
#
#  Objective: Combine multiple HTML files into
#  a single document.
#
#  Tools/Resources: Concatenate HTML text using
#  python or javascript.
# -----------------------------------------------

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_body_inner_html(html: str) -> str:
    """
    If the file is a full HTML document, keep only the inner HTML of <body>
    to avoid nesting <html><head>... multiple times.

    If <body> is missing, fall back to the full HTML string.
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if body is None:
        return html

    # Join body children back into a string (keeps original tags)
    return "".join(str(child) for child in body.contents)


def main() -> None:
    # Adjust these if your folder names are different
    input_dir = Path("data/raw_ne/subjects")
    output_dir = Path("data/combined")
    output_path = output_dir / "ne_course_catalog_combined.html"

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Input folder not found: {input_dir}\n"
            "Did you run 01_pull.py first, and does it save to data/raw_ne/subjects/?"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in input_dir.glob("*.html") if p.is_file())
    if not files:
        raise FileNotFoundError(f"No .html files found in: {input_dir}")

    generated_at = datetime.now().isoformat(timespec="seconds")

    # Build ONE valid HTML document that contains all subject bodies
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang='en'>")
    parts.append("<head>")
    parts.append("<meta charset='utf-8'/>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'/>")
    parts.append("<title>Northeastern Course Descriptions — Combined</title>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"<!-- Combined from {len(files)} subject pages. Generated at {generated_at}. -->")
    parts.append("<h1>Northeastern Course Descriptions — Combined</h1>")
    parts.append("<p>This file concatenates subject pages from data/raw_ne/subjects/.</p>")
    parts.append("<hr/>")

    for i, path in enumerate(files, start=1):
        raw = read_text(path)
        body_html = extract_body_inner_html(raw)

        # Wrap each subject page in a section for provenance
        parts.append(
            f"<section class='subject-page' data-source-file='{path.name}'>"
            f"<!-- START {path.name} ({i}/{len(files)}) -->"
        )
        parts.append(f"<h2>Source: {path.name}</h2>")
        parts.append(body_html)
        parts.append(f"<!-- END {path.name} -->")
        parts.append("</section>")
        parts.append("<hr/>")

    parts.append("</body>")
    parts.append("</html>")

    output_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"[done] Combined {len(files)} files into: {output_path}")


if __name__ == "__main__":
    main()
