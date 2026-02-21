from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import requests


P1996 = Path("10_mit_1996.json")
P2024 = Path("11_mit_2024.json")
OFFER_CSV = Path("data/analysis/course_offerings_by_dept.csv")
SUBJECT_CSV = Path("data/subject_changes/subject_changes.csv")
BREADTH_TXT = Path("data/breadth/metrics_summary.txt")
TITLE_COMPARE_CSV = Path("data/title_evolution/title_word_compare.csv")
OUT_TXT = Path("16_summary_reflection.txt")


def load_json(path: Path) -> List[dict]:
	if not path.exists():
		raise FileNotFoundError(f"Missing input file: {path}")
	return json.loads(path.read_text(encoding="utf-8"))


def load_offering_rows(path: Path) -> List[Dict[str, str]]:
	if not path.exists():
		raise FileNotFoundError(f"Missing input file: {path}")
	rows = list(csv.DictReader(path.open(encoding="utf-8")))
	for row in rows:
		row["n_1996"] = int(row.get("n_1996", 0))
		row["n_2024"] = int(row.get("n_2024", 0))
		row["delta"] = int(row.get("delta", 0))
	return rows


def load_subject_change_counts(path: Path) -> Dict[str, int]:
	if not path.exists():
		raise FileNotFoundError(f"Missing input file: {path}")
	out = {"new": 0, "discontinued": 0, "persistent": 0}
	for row in csv.DictReader(path.open(encoding="utf-8")):
		cat = str(row.get("category", "")).strip().lower()
		if cat in out:
			out[cat] += 1
	return out


def parse_breadth_metrics(path: Path) -> Dict[str, float]:
	if not path.exists():
		raise FileNotFoundError(f"Missing input file: {path}")
	txt = path.read_text(encoding="utf-8")

	def grab(label: str) -> float:
		match = re.search(rf"{re.escape(label)}:\s*([0-9.]+)", txt)
		return float(match.group(1)) if match else float("nan")

	return {
		"multi_1996": grab("1996 multi-topic rate"),
		"multi_2024": grab("2024 multi-topic rate"),
		"avg_1996": grab("1996 avg topics/course"),
		"avg_2024": grab("2024 avg topics/course"),
		"entropy_1996": grab("1996 topic entropy"),
		"entropy_2024": grab("2024 topic entropy"),
	}


def top_shift_words(path: Path, top_n: int = 6) -> tuple[List[str], List[str]]:
	if not path.exists():
		return [], []

	rows = list(csv.DictReader(path.open(encoding="utf-8")))
	cleaned = []
	for row in rows:
		try:
			w = str(row.get("word", "")).strip()
			score = float(row.get("log_ratio_2024_vs_1996", 0.0))
			c96 = int(row.get("count_1996", 0))
			c24 = int(row.get("count_2024", 0))
		except Exception:
			continue
		if not w:
			continue
		if (c96 + c24) < 10:
			continue
		cleaned.append((w, score))

	if not cleaned:
		return [], []

	more_2024 = [w for w, _ in sorted(cleaned, key=lambda x: x[1], reverse=True)[:top_n]]
	more_1996 = [w for w, _ in sorted(cleaned, key=lambda x: x[1])[:top_n]]
	return more_2024, more_1996


def fmt_word_list(words: List[str]) -> str:
	return ", ".join(words) if words else "(insufficient data)"


def build_facts() -> Dict[str, Any]:
	data96 = load_json(P1996)
	data24 = load_json(P2024)

	offer_rows = load_offering_rows(OFFER_CSV)
	subject_counts = load_subject_change_counts(SUBJECT_CSV)
	breadth = parse_breadth_metrics(BREADTH_TXT)
	words_2024, words_1996 = top_shift_words(TITLE_COMPARE_CSV)

	top_expand = sorted(offer_rows, key=lambda row: row["delta"], reverse=True)[:6]
	negative_rows = [row for row in offer_rows if row["delta"] < 0]
	top_reduce = sorted(negative_rows, key=lambda row: row["delta"])[:3]

	growth_factor = (len(data24) / len(data96)) if len(data96) else float("nan")
	growth_text = f"{growth_factor:.2f}x" if not math.isnan(growth_factor) else "n/a"

	return {
		"n_1996": len(data96),
		"n_2024": len(data24),
		"growth_text": growth_text,
		"top_expand": top_expand,
		"top_reduce": top_reduce,
		"subject_counts": subject_counts,
		"breadth": breadth,
		"words_2024": words_2024,
		"words_1996": words_1996,
	}


def render_rule_based_summary(facts: Dict[str, Any]) -> str:
	top_expand = facts["top_expand"]
	top_reduce = facts["top_reduce"]
	breadth = facts["breadth"]
	subject_counts = facts["subject_counts"]

	expand_text = ", ".join([f"{row['dept']} ({row['delta']:+d})" for row in top_expand])
	reduce_text = ", ".join([f"{row['dept']} ({row['delta']:+d})" for row in top_reduce])

	lines = []
	lines.append("MIT's catalog shows a major expansion from 1996 to 2024: ")
	lines.append(
		f"{facts['n_1996']:,} extracted courses in 1996 versus {facts['n_2024']:,} in 2024 ({facts['growth_text']} growth). "
	)
	lines.append(
		"This likely reflects both true curricular growth and a more granular catalog structure with many specialized offerings.\n\n"
	)

	if top_reduce:
		reduction_sentence = f"Largest reductions include {reduce_text}. "
	else:
		reduction_sentence = "True reductions were limited in this extraction; most prefixes were flat or grew. "

	lines.append(
		"Department-level change is concentrated in several prefixes. "
		f"Largest expansions are {expand_text}. "
		f"{reduction_sentence}"
		"This pattern is consistent with stronger emphasis on computation, analytics, management, and technology-driven design.\n\n"
	)

	lines.append(
		"Subject-prefix turnover indicates institutional diversification: "
		f"persistent={subject_counts['persistent']}, new={subject_counts['new']}, discontinued={subject_counts['discontinued']}. "
		"Rather than shrinking, the catalog appears to have been reorganized and expanded into more specialized or interdisciplinary administrative groupings.\n\n"
	)

	lines.append(
		"Title-language trends also shifted. "
		f"Words more associated with 2024 include {fmt_word_list(facts['words_2024'])}, "
		f"while 1996-associated terms include {fmt_word_list(facts['words_1996'])}. "
		"This suggests movement from discipline-internal framing toward application, integration, and skills that map to modern technology and leadership contexts.\n\n"
	)

	lines.append(
		"Breadth metrics add nuance: "
		f"multi-topic rate changed from {breadth['multi_1996']:.3f} to {breadth['multi_2024']:.3f}, "
		f"average topics per course from {breadth['avg_1996']:.3f} to {breadth['avg_2024']:.3f}, "
		f"and topic entropy from {breadth['entropy_1996']:.4f} to {breadth['entropy_2024']:.4f}. "
		"The curriculum is broader in total volume, but individual courses are often more tightly scoped, indicating specialization alongside program-level interdisciplinarity.\n\n"
	)

	lines.append(
		"In broader education and industry terms, these changes align with demand for rapid skill refresh, data/AI fluency, cross-domain collaboration, and mission-driven applications in areas like climate, health, policy, and media. "
		"Overall, the catalog evolution is best described as expansion + specialization + reorganization for a faster-moving, digitally integrated innovation economy.\n"
	)

	return "".join(lines)


def render_llm_summary(
	facts: Dict[str, Any],
	api_key: str,
	model: str,
	endpoint: str,
	timeout_seconds: int,
) -> str:
	system_prompt = (
		"You are an academic analyst. Write a concise but insightful reflection based ONLY on the provided metrics. "
		"Do not invent numbers. Focus on the most significant catalog changes over time and connect them to broader trends in education and industry. "
		"Use 6-8 short paragraphs in plain text (no markdown lists)."
	)

	user_prompt = (
		"Create the final narrative for a file named 16_summary_reflection.txt. "
		"Keep the tone analytical and grounded. Here are the computed facts as JSON:\n\n"
		+ json.dumps(facts, indent=2, ensure_ascii=False)
	)

	payload = {
		"model": model,
		"temperature": 0.2,
		"messages": [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
	}

	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}

	response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_seconds)
	response.raise_for_status()
	data = response.json()

	content = (
		data.get("choices", [{}])[0]
		.get("message", {})
		.get("content", "")
	)
	content = str(content).strip()
	content = re.sub(r"^```(?:text|markdown)?\s*", "", content, flags=re.I)
	content = re.sub(r"\s*```$", "", content).strip()

	if not content:
		raise RuntimeError("LLM returned empty content")
	return content + "\n"


def build_file_text(body: str) -> str:
	header = (
		"# -----------------------------------------------\n"
		"#  16. Summary and Reflection:\n"
		"# -----------------------------------------------\n\n"
	)
	return header + body


def main() -> None:
	parser = argparse.ArgumentParser(description="Generate 16_summary_reflection.txt from analysis outputs")
	parser.add_argument("--use-llm", action="store_true", help="Use an OpenAI-compatible LLM to generate the narrative")
	parser.add_argument("--no-llm", action="store_true", help="Disable LLM generation and force rule-based summary")
	parser.add_argument("--provider", choices=["openai", "github"], default=os.getenv("LLM_PROVIDER", "github"))
	parser.add_argument("--model", default=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")))
	parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
	parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
	parser.add_argument("--endpoint", default=os.getenv("LLM_ENDPOINT", ""))
	parser.add_argument("--timeout", type=int, default=90)
	args = parser.parse_args()

	facts = build_facts()
	mode = "rule-based"

	use_llm = not args.no_llm
	if args.use_llm:
		use_llm = True

	if use_llm:
		provider = args.provider.lower()
		if provider == "github":
			api_key = args.api_key or os.getenv("GITHUB_TOKEN", "")
			endpoint = args.endpoint or "https://models.github.ai/inference/chat/completions"
		else:
			api_key = args.api_key
			endpoint = args.endpoint or (args.base_url.rstrip("/") + "/chat/completions")

		if not api_key:
			print("[info] LLM unavailable, running free local fallback")
			if provider == "github":
				print("[warn] Missing GITHUB_TOKEN/--api-key for GitHub Models.")
			else:
				print("[warn] Missing OPENAI_API_KEY/--api-key for OpenAI-compatible provider.")
			body = render_rule_based_summary(facts)
		else:
			try:
				body = render_llm_summary(
					facts=facts,
					api_key=api_key,
					model=args.model,
					endpoint=endpoint,
					timeout_seconds=args.timeout,
				)
				mode = f"llm:{provider}:{args.model}"
			except Exception as exc:
				print(f"[warn] LLM generation failed ({exc}). Falling back to rule-based summary.")
				body = render_rule_based_summary(facts)
	else:
		body = render_rule_based_summary(facts)

	OUT_TXT.write_text(build_file_text(body), encoding="utf-8")

	expand_text = ", ".join([f"{row['dept']} ({row['delta']:+d})" for row in facts["top_expand"]])
	print("[done] Auto summary written ->", OUT_TXT)
	print(f"[info] Mode: {mode}")
	print(f"[info] Courses: 1996={facts['n_1996']}, 2024={facts['n_2024']}")
	print(f"[info] Subject prefixes: {facts['subject_counts']}")
	print(f"[info] Top expansions: {expand_text}")


if __name__ == "__main__":
	main()