# -----------------------------------------------
#  1. Data Acquisition:
# 
#  Objective: Download all the public course 
#  catalog data in raw HTML format from a 
#  university website.
# 
#  Tools/Resources: Extract all the course 
#  catalog data from one of the follow 
#  three universities:
#     Harvard: https://courses.my.harvard.edu
#     BU: https://www.bu.edu/academics/cas/courses
#     NE: https://catalog.northeastern.edu/course-descriptions
# -----------------------------------------------
from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# Northeastern (NE) Course Descriptions entry point
INDEX_URL = "https://catalog.northeastern.edu/course-descriptions/"


@dataclass
class DownloadRecord:
    url: str
    path: str
    kind: str  # "index" or "subject"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _canonicalize(url: str) -> str:
    """Drop query/fragment so URLs are stable."""
    p = urlparse(url)
    return urlunparse(p._replace(query="", fragment=""))


def _request_with_retries(
    session: requests.Session,
    url: str,
    *,
    timeout: int = 30,
    max_retries: int = 5,
    backoff_base: float = 1.7,
) -> requests.Response:
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
            sleep_s = (backoff_base**attempt) + random.random()
            print(f"[warn] GET failed (attempt {attempt}/{max_retries}): {url}\n       {e}\n       sleeping {sleep_s:.2f}s")
            time.sleep(sleep_s)
    raise RuntimeError(f"Failed to GET after {max_retries} retries: {url}") from last_err


def _save_html(path: str, html: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def _extract_subject_links(index_html: str) -> list[str]:
    """
    NE has one page per subject, e.g.:
      https://catalog.northeastern.edu/course-descriptions/arch/
      https://catalog.northeastern.edu/course-descriptions/cs/
    This function extracts those subject URLs from the index page.
    """
    soup = BeautifulSoup(index_html, "html.parser")
    links: set[str] = set()

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        abs_url = _canonicalize(urljoin(INDEX_URL, href))
        p = urlparse(abs_url)

        if p.netloc != "catalog.northeastern.edu":
            continue
        if not p.path.startswith("/course-descriptions/"):
            continue
        if p.path.rstrip("/") == "/course-descriptions":
            continue

        # keep only /course-descriptions/<slug>/
        if re.fullmatch(r"/course-descriptions/[a-z0-9-]+/", p.path):
            links.add(abs_url)

    return sorted(links)


def _subject_slug(url: str) -> str:
    # /course-descriptions/arch/ -> arch
    p = urlparse(url)
    parts = p.path.strip("/").split("/")
    return parts[-1] if parts else "unknown"


def main() -> None:
    # Output layout (simple + predictable)
    out_dir = os.path.join("data", "raw_ne")
    subjects_dir = os.path.join(out_dir, "subjects")
    _ensure_dir(out_dir)
    _ensure_dir(subjects_dir)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "sensemaking-pset/01_pull (student scraper)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    manifest: list[DownloadRecord] = []

    # 1) Download index page
    print(f"[info] Fetching index: {INDEX_URL}")
    index_resp = _request_with_retries(session, INDEX_URL)
    index_html = index_resp.text

    index_path = os.path.join(out_dir, "index.html")
    _save_html(index_path, index_html)
    manifest.append(DownloadRecord(url=INDEX_URL, path=index_path, kind="index"))

    # 2) Extract + download each subject page
    subject_urls = _extract_subject_links(index_html)
    print(f"[info] Found {len(subject_urls)} subject pages")

    for i, url in enumerate(subject_urls, start=1):
        time.sleep(random.uniform(0.25, 0.75))  # polite delay
        resp = _request_with_retries(session, url)
        html = resp.text

        slug = _subject_slug(url)
        path = os.path.join(subjects_dir, f"{slug}.html")
        _save_html(path, html)
        manifest.append(DownloadRecord(url=url, path=path, kind="subject"))

        if i % 25 == 0 or i == len(subject_urls):
            print(f"[info] Downloaded {i}/{len(subject_urls)} subject pages")

    # 3) Save manifest (helps you debug + prove what you downloaded)
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in manifest], f, indent=2)

    print(f"[done] index.html:    {index_path}")
    print(f"[done] subjects/:    {subjects_dir}")
    print(f"[done] manifest.json:{manifest_path}")


if __name__ == "__main__":
    main()
