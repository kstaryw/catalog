# -----------------------------------------------
#  10. Catalog 1996
#
#  Extract course data from the scanned
#  1996 MIT course catalog. After extracting
#  the text, create a data model and save the
#  processed data. This task emphasizes
#  working with raw, scanned documents
#  and aims to teach you how to extract
#  information from non-digitized sources.
# -----------------------------------------------

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import pdfplumber

# OCR stack (optional but recommended for scanned pages)
try:
    import pytesseract
    from pdf2image import convert_from_path
except Exception:
    pytesseract = None
    convert_from_path = None


INDEX_URL = "https://onexi.org/catalog/pdf/index.html"
OUT_JSON = Path("10_mit_1996.json")

RAW_DIR = Path("data/mit1996/raw_pdfs")
TEXT_DIR = Path("data/mit1996/page_text")

# If a page has fewer than this many non-whitespace chars using pdfplumber,
# assume it is scanned-only and needs OCR.
MIN_TEXT_CHARS_BEFORE_OCR = 200


@dataclass
class MITCourse1996:
    subject_number: str          # e.g., "1.125"
    title: str                   # e.g., "Architecting and Engineering Software Systems"
    description: str             # paragraph-ish description
    raw_block: str               # raw extracted block (useful for debugging/provenance)
    source_pdf: str              # e.g., "01.pdf"
    start_page: int              # page number within that PDF (1-based)


# ------------------------
# Download PDFs
# ------------------------

def fetch_index_pdf_urls() -> List[str]:
    """
    Parse the index page and find the PDF links for Part 01..08.
    The index page lists 'Part 01' ... 'Part 08'.
    """
    r = requests.get(INDEX_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    urls: List[str] = []
    for a in soup.select("a[href]"):
        label = (a.get_text(strip=True) or "").lower()
        href = (a.get("href") or "").strip()

        # The links are typically like "01.pdf", "02.pdf", ... or "/catalog/pdf/01.pdf"
        if label.startswith("part"):
            abs_url = urljoin(INDEX_URL, href)
            if abs_url.lower().endswith(".pdf"):
                urls.append(abs_url)

    # Fallback if the page uses predictable filenames but links weren't captured
    if not urls:
        for i in range(1, 9):
            urls.append(f"https://onexi.org/catalog/pdf/{i:02d}.pdf")

    # Deduplicate while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


# ------------------------
# Text extraction (pdfplumber + OCR fallback)
# ------------------------

def extract_text_pdfplumber(pdf_path: Path) -> List[str]:
    """
    Return list of page texts (one string per page) using pdfplumber.
    """
    pages: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            pages.append(txt)
    return pages


def ocr_pdf_page(pdf_path: Path, page_index_zero_based: int) -> str:
    """
    OCR one page of a PDF using pdf2image + pytesseract.
    Requires poppler + tesseract installed.

    page_index_zero_based: 0 for first page, etc.
    """
    if pytesseract is None or convert_from_path is None:
        raise RuntimeError(
            "OCR dependencies missing. Install: pytesseract, pdf2image, pillow; "
            "and system packages: tesseract-ocr, poppler-utils."
        )

    # convert a single page to an image
    images = convert_from_path(
        str(pdf_path),
        first_page=page_index_zero_based + 1,
        last_page=page_index_zero_based + 1,
        dpi=250,
    )
    if not images:
        return ""
    img = images[0]
    text = pytesseract.image_to_string(img)
    return text or ""


def normalize_extracted_text(s: str) -> str:
    """
    Normalize common OCR/text extraction artifacts:
    - fix hyphen line breaks: "archi-\ntecture" -> "architecture"
    - normalize newlines
    - strip trailing spaces
    """
    if not s:
        return ""

    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Fix hyphenation across line breaks (letters-hyphen-newline-letters)
    s = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", s)

    # Remove repeated blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)

    # Trim each line
    s = "\n".join(line.rstrip() for line in s.splitlines())

    return s.strip()


# ------------------------
# Parsing courses from text
# ------------------------

COURSE_HEADER_RE = re.compile(
    r"^\s*(\d{1,2}\.\d{3})\s+([A-Z0-9].*?)\s*$"
)
# MIT subjects are like 1.001, 6.100, 21H.??? (but 1996 often uses 2 digits dot 3 digits)
# This regex targets the classic 1.125 style requested.

def parse_courses_from_pages(
    page_texts: List[str],
    source_pdf: str,
) -> List[MITCourse1996]:
    """
    Scan through text line-by-line and detect course entries.
    Start a new course when we see a header like: '1.125 Title...'
    Accumulate following lines until the next header.
    """
    courses: List[MITCourse1996] = []

    current_num: Optional[str] = None
    current_title: Optional[str] = None
    current_lines: List[str] = []
    current_start_page: Optional[int] = None

    def flush():
        nonlocal current_num, current_title, current_lines, current_start_page
        if not current_num or not current_title:
            return

        block = "\n".join(current_lines).strip()

        # Heuristic: description is "block" but we remove obvious admin lines
        # like "Prereq:", "Units:", "Lecture:", etc. Keep narrative sentences.
        desc_lines = []
        for ln in block.splitlines():
            l = ln.strip()
            if not l:
                continue
            if re.match(r"^(Prereq|Units|Lecture|Lab|Recitation|Instructors?|Textbook|Coreq|Same subject as)\b", l, re.I):
                continue
            # also skip image artifacts or lone punctuation
            if len(l) <= 2:
                continue
            desc_lines.append(l)

        description = " ".join(desc_lines).strip()

        courses.append(
            MITCourse1996(
                subject_number=current_num,
                title=current_title.strip(),
                description=description,
                raw_block=block,
                source_pdf=source_pdf,
                start_page=int(current_start_page or 1),
            )
        )

        current_num = None
        current_title = None
        current_lines = []
        current_start_page = None

    for page_i, raw in enumerate(page_texts, start=1):
        text = normalize_extracted_text(raw)
        if not text:
            continue

        for line in text.splitlines():
            m = COURSE_HEADER_RE.match(line)
            if m:
                # New course found: flush previous course
                flush()
                current_num = m.group(1)
                current_title = m.group(2)
                current_lines = []
                current_start_page = page_i
            else:
                if current_num is not None:
                    current_lines.append(line)

    flush()
    return courses


# ------------------------
# Main
# ------------------------

def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_urls = fetch_index_pdf_urls()
    if not pdf_urls:
        raise RuntimeError("No PDF URLs found from the index page.")

    all_courses: List[MITCourse1996] = []

    for url in pdf_urls:
        filename = url.split("/")[-1]
        pdf_path = RAW_DIR / filename

        if not pdf_path.exists():
            print(f"[info] Downloading: {url}")
            download_file(url, pdf_path)
        else:
            print(f"[info] Using cached PDF: {pdf_path}")

        # 1) try pdfplumber text extraction
        page_texts = extract_text_pdfplumber(pdf_path)

        # 2) OCR fallback per-page if needed
        final_pages: List[str] = []
        for idx, txt in enumerate(page_texts):
            norm = normalize_extracted_text(txt)
            if len(re.sub(r"\s+", "", norm)) >= MIN_TEXT_CHARS_BEFORE_OCR:
                final_pages.append(norm)
                continue

            # likely scanned-only page
            if pytesseract is None or convert_from_path is None:
                # keep whatever we have (may be empty) but warn
                print(f"[warn] Page {idx+1} in {filename} looks scanned; OCR not available. Keeping extracted text (may be empty).")
                final_pages.append(norm)
                continue

            print(f"[info] OCR page {idx+1}/{len(page_texts)} in {filename} ...")
            ocr_txt = ocr_pdf_page(pdf_path, idx)
            final_pages.append(normalize_extracted_text(ocr_txt))

        # Save per-page text (debuggable artifacts)
        for i, t in enumerate(final_pages, start=1):
            (TEXT_DIR / f"{pdf_path.stem}_p{i:03d}.txt").write_text(t + "\n", encoding="utf-8")

        # 3) parse courses from this PDF
        courses = parse_courses_from_pages(final_pages, source_pdf=filename)
        print(f"[done] {filename}: parsed {len(courses)} courses")
        all_courses.extend(courses)

    # Deduplicate: same subject_number + title (OCR may repeat)
    dedup = {}
    for c in all_courses:
        key = (c.subject_number, c.title.strip().lower())
        if key not in dedup:
            dedup[key] = c

    final_list = [asdict(v) for v in dedup.values()]
    final_list.sort(key=lambda x: (x["subject_number"], x["title"].lower()))

    OUT_JSON.write_text(json.dumps(final_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[final] Wrote {len(final_list)} unique courses to {OUT_JSON}")


if __name__ == "__main__":
    main()