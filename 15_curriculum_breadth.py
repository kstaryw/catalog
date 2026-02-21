# -----------------------------------------------
#  15. Curriculum Breadth:
# 
#  Compare the breadth of topics in the 
#  1996 and 2024 catalogs to assess whether 
#  the curriculum has become more 
#  interdisciplinary or specialized.
# -----------------------------------------------


from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import matplotlib.pyplot as plt


IN_1996 = Path("10_mit_1996.json")
IN_2024 = Path("11_mit_2024.json")

OUT_DIR = Path("data/breadth")
OUT_TOPIC_CSV = OUT_DIR / "topic_shares.csv"
OUT_METRICS_TXT = OUT_DIR / "metrics_summary.txt"
OUT_PNG_1996 = OUT_DIR / "topic_share_1996.png"
OUT_PNG_2024 = OUT_DIR / "topic_share_2024.png"
OUT_DEPT_1996 = OUT_DIR / "dept_specialization_top20_1996.csv"
OUT_DEPT_2024 = OUT_DIR / "dept_specialization_top20_2024.csv"


# -----------------------
# 1) Keyword taxonomy
# -----------------------
# Multi-label topics (a course can match multiple).
# Keep this small + interpretable.
TOPICS: Dict[str, Set[str]] = {
    "Computing & AI": {
        "computer", "comput", "algorithm", "data", "database", "software",
        "machine", "learning", "ai", "artificial", "vision", "nlp", "network",
        "security", "crypt", "distributed", "cloud", "robot", "autonomous",
        "control", "optimization"
    },
    "Math & Statistics": {
        "math", "mathemat", "calculus", "algebra", "geometry", "topology",
        "probability", "stochastic", "statistics", "statistical", "inference",
        "regression", "bayesian", "numerical", "combinator", "discrete"
    },
    "Physics": {
        "physics", "quantum", "relativity", "optics", "electromagnet",
        "thermo", "thermodynamics", "mechanics", "particle", "nuclear"
    },
    "Chemistry": {
        "chemistry", "chemical", "organic", "inorganic", "biochem",
        "polymer", "reaction", "synthesis", "catalysis"
    },
    "Biology & Health": {
        "biology", "biological", "genetic", "genomics", "cell", "neuro",
        "brain", "cognitive", "medical", "medicine", "health", "clinical",
        "biomed", "biomedical"
    },
    "Materials": {
        "material", "materials", "metals", "ceramic", "polymer", "composite",
        "microstructure", "nanomaterial", "nanotech", "solid", "mechanical"
    },
    "Energy & Environment": {
        "energy", "climate", "environment", "sustain", "sustainable",
        "carbon", "emission", "renewable", "solar", "wind", "water",
        "ecology", "earth", "geology", "ocean"
    },
    "Design, Architecture & Media": {
        "design", "architecture", "urban", "city", "planning", "landscape",
        "media", "music", "art", "visual", "film", "studio", "aesthetic",
        "fabrication", "making", "interaction"
    },
    "Business & Management": {
        "management", "finance", "accounting", "marketing", "strategy",
        "entrepreneur", "innovation", "operations", "supply", "leadership",
        "organization", "economics", "economic"
    },
    "Humanities & Society": {
        "history", "literature", "language", "writing", "philosophy", "ethics",
        "politics", "political", "policy", "law", "sociology", "anthropology",
        "culture", "gender", "sts", "society"
    },
}


STOPWORDS = {
    "a","an","and","are","as","at","be","by","for","from","in","into","is","it",
    "of","on","or","the","to","with","without","via","i","ii","iii","iv","v","vi",
    "vii","viii","ix","x",
}


def load_json(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dept_prefix_from_id(course_id: str) -> Optional[str]:
    """
    MIT subject prefix proxy:
      1.00 -> 1
      21H.001 -> 21H
      CMS.100 -> CMS
    """
    if not course_id:
        return None
    m = re.match(r"^([0-9A-Z]+)\.", str(course_id).strip())
    return m.group(1) if m else None


def tokenize(text: str) -> List[str]:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = [t for t in s.split() if t and t not in STOPWORDS and not t.isdigit()]
    return toks


def classify_topics(title: str, desc: str) -> Set[str]:
    """
    Multi-label topic assignment by keyword match.
    Uses stems-ish matching by allowing "comput" match for computing, etc.
    """
    toks = tokenize(f"{title} {desc}")
    topics = set()
    for topic, keys in TOPICS.items():
        for t in toks:
            # prefix match allows keys like "comput" to match "computational"
            if any(t.startswith(k) for k in keys):
                topics.add(topic)
                break
    if not topics:
        topics.add("Other/Unclassified")
    return topics


def shannon_entropy(counts: Dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    ent = 0.0
    for n in counts.values():
        p = n / total
        ent -= p * math.log(p)
    return ent


def hhi_from_counts(counts: Dict[str, int]) -> float:
    """
    Herfindahl-Hirschman Index of topic concentration:
      sum(p_i^2). Higher => more concentrated/specialized.
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return sum((n / total) ** 2 for n in counts.values())


def analyze_catalog(rows: List[dict], year: str, id_field: str) -> dict:
    """
    Returns:
      - topic_counts
      - multi_topic_rate
      - avg_topics_per_course
      - dept_metrics: {dept: {n_courses, entropy, hhi}}
    """
    topic_counts = Counter()
    dept_topic_counts: Dict[str, Counter] = defaultdict(Counter)

    multi = 0
    total = 0
    topic_sum = 0

    for r in rows:
        cid = str(r.get(id_field, "")).strip()
        title = str(r.get("title", "")).strip()
        desc = str(r.get("description", "")).strip()

        if not title:
            continue

        topics = classify_topics(title, desc)
        total += 1
        topic_sum += len(topics)
        if len(topics) > 1:
            multi += 1

        for t in topics:
            topic_counts[t] += 1

        dept = dept_prefix_from_id(cid) if cid else None
        if dept:
            for t in topics:
                dept_topic_counts[dept][t] += 1

    multi_topic_rate = (multi / total) if total else 0.0
    avg_topics_per_course = (topic_sum / total) if total else 0.0

    dept_metrics = []
    for dept, c in dept_topic_counts.items():
        dept_metrics.append(
            {
                "dept": dept,
                "n_courses": sum(c.values()),
                "topic_entropy": shannon_entropy(c),
                "topic_hhi": hhi_from_counts(c),
            }
        )

    # Sort: most specialized first by HHI (high concentration)
    dept_metrics.sort(key=lambda x: x["topic_hhi"], reverse=True)

    return {
        "year": year,
        "n_courses_used": total,
        "topic_counts": dict(topic_counts),
        "multi_topic_rate": multi_topic_rate,
        "avg_topics_per_course": avg_topics_per_course,
        "dept_metrics": dept_metrics,
    }


def plot_topic_shares(topic_counts: Dict[str, int], out_path: Path, title: str, top_n: int = 12) -> None:
    items = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    top = items[:top_n]
    labels = [k for k, _ in top]
    values = [v for _, v in top]

    plt.figure(figsize=(10, 6))
    plt.bar(labels, values)
    plt.title(title)
    plt.xlabel("Topic")
    plt.ylabel("Course count (multi-label)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def write_topic_csv(a96: dict, a24: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_topics = sorted(set(a96["topic_counts"].keys()) | set(a24["topic_counts"].keys()))
    total96 = sum(a96["topic_counts"].values()) or 1
    total24 = sum(a24["topic_counts"].values()) or 1

    lines = ["topic,count_1996,share_1996,count_2024,share_2024\n"]
    for t in all_topics:
        c96 = a96["topic_counts"].get(t, 0)
        c24 = a24["topic_counts"].get(t, 0)
        lines.append(f"{t},{c96},{c96/total96:.6f},{c24},{c24/total24:.6f}\n")

    OUT_TOPIC_CSV.write_text("".join(lines), encoding="utf-8")


def write_dept_top20(dept_metrics: List[dict], out_path: Path) -> None:
    lines = ["dept,n_courses,topic_entropy,topic_hhi\n"]
    for r in dept_metrics[:20]:
        lines.append(f"{r['dept']},{r['n_courses']},{r['topic_entropy']:.6f},{r['topic_hhi']:.6f}\n")
    out_path.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    data_1996 = load_json(IN_1996)
    data_2024 = load_json(IN_2024)

    # 1996 uses subject_number as id; 2024 uses course_id
    a96 = analyze_catalog(data_1996, year="1996", id_field="subject_number")
    a24 = analyze_catalog(data_2024, year="2024", id_field="course_id")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # CSV + plots
    write_topic_csv(a96, a24)
    plot_topic_shares(a96["topic_counts"], OUT_PNG_1996, "1996 Topic Breadth (keyword taxonomy)")
    plot_topic_shares(a24["topic_counts"], OUT_PNG_2024, "2024 Topic Breadth (keyword taxonomy)")
    write_dept_top20(a96["dept_metrics"], OUT_DEPT_1996)
    write_dept_top20(a24["dept_metrics"], OUT_DEPT_2024)

    # Metrics summary
    # Overall diversity is entropy of topic distribution (multi-label).
    ent96 = shannon_entropy(a96["topic_counts"])
    ent24 = shannon_entropy(a24["topic_counts"])

    summary = []
    summary.append("=== Curriculum Breadth Summary ===\n")
    summary.append(f"Courses used (1996): {a96['n_courses_used']}\n")
    summary.append(f"Courses used (2024): {a24['n_courses_used']}\n\n")

    summary.append("=== Interdisciplinarity proxies (multi-label topics) ===\n")
    summary.append(f"1996 multi-topic rate: {a96['multi_topic_rate']:.3f}\n")
    summary.append(f"2024 multi-topic rate: {a24['multi_topic_rate']:.3f}\n")
    summary.append(f"1996 avg topics/course: {a96['avg_topics_per_course']:.3f}\n")
    summary.append(f"2024 avg topics/course: {a24['avg_topics_per_course']:.3f}\n\n")

    summary.append("=== Curriculum diversity (topic entropy; higher => broader distribution) ===\n")
    summary.append(f"1996 topic entropy: {ent96:.4f}\n")
    summary.append(f"2024 topic entropy: {ent24:.4f}\n\n")

    summary.append("=== Outputs ===\n")
    summary.append(f"- Topic shares CSV: {OUT_TOPIC_CSV}\n")
    summary.append(f"- Topic plots: {OUT_PNG_1996}, {OUT_PNG_2024}\n")
    summary.append(f"- Dept specialization top20 (HHI high => specialized): {OUT_DEPT_1996}, {OUT_DEPT_2024}\n")

    OUT_METRICS_TXT.write_text("".join(summary), encoding="utf-8")

    # Print key results
    print("[done] Wrote:", OUT_TOPIC_CSV)
    print("[done] Wrote:", OUT_METRICS_TXT)
    print("[done] Wrote:", OUT_PNG_1996)
    print("[done] Wrote:", OUT_PNG_2024)
    print("[done] Wrote:", OUT_DEPT_1996)
    print("[done] Wrote:", OUT_DEPT_2024)
    print()
    print("1996 multi-topic rate:", f"{a96['multi_topic_rate']:.3f}")
    print("2024 multi-topic rate:", f"{a24['multi_topic_rate']:.3f}")
    print("1996 avg topics/course:", f"{a96['avg_topics_per_course']:.3f}")
    print("2024 avg topics/course:", f"{a24['avg_topics_per_course']:.3f}")
    print("1996 topic entropy:", f"{ent96:.4f}")
    print("2024 topic entropy:", f"{ent24:.4f}")

    print("\nTop 10 topics (1996):", Counter(a96["topic_counts"]).most_common(10))
    print("Top 10 topics (2024):", Counter(a24["topic_counts"]).most_common(10))


if __name__ == "__main__":
    main()