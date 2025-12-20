#!/usr/bin/env python3
"""Build OCR benchmark aggregate data (metrics + costs)."""
import json
from pathlib import Path

BASE = Path("testdata/ocr-bench/ai-ocr-simplification")
OUT = Path("docs/ocr-bench-data.json")

META = {
    "gpt5": {"name":"GPT‑5","provider":"OpenAI","tier":"SOTA"},
    "gpt5_1": {"name":"GPT‑5.1","provider":"OpenAI","tier":"SOTA"},
    "gpt5_2": {"name":"GPT‑5.2","provider":"OpenAI","tier":"SOTA"},
    "gpt5_mini": {"name":"GPT‑5 mini","provider":"OpenAI","tier":"Value"},
    "gpt5_nano": {"name":"GPT‑5 nano","provider":"OpenAI","tier":"Value"},
    "gpt5_2_chat": {"name":"GPT‑5.2 Chat (Instant)","provider":"OpenAI","tier":"Value"},
    "gpt4_1": {"name":"GPT‑4.1","provider":"OpenAI","tier":"Strong"},
    "gpt4_1-mini": {"name":"GPT‑4.1 mini","provider":"OpenAI","tier":"Value"},
    "gpt4o": {"name":"GPT‑4o","provider":"OpenAI","tier":"Legacy"},
    "gpt4o-mini": {"name":"GPT‑4o mini","provider":"OpenAI","tier":"Value"},
    "gemini-2.0-flash": {"name":"Gemini 2.0 Flash","provider":"Google","tier":"Value"},
    "gemini-3-flash": {"name":"Gemini 3 Flash (preview)","provider":"Google","tier":"Value"},
    "gemini-3-pro": {"name":"Gemini 3 Pro (preview)","provider":"Google","tier":"SOTA"},
    "mistral-ocr3": {"name":"Mistral OCR 3","provider":"Mistral","tier":"Specialist"},
    "mistral-ocr2": {"name":"Mistral OCR 2 (2505)","provider":"Mistral","tier":"Specialist"},
    "claude-opus-4-1": {"name":"Claude Opus 4.1","provider":"Anthropic","tier":"SOTA"},
    "claude-sonnet-4": {"name":"Claude Sonnet 4","provider":"Anthropic","tier":"Value"},
    "claude-3-5-sonnet": {"name":"Claude 3.5 Sonnet","provider":"Anthropic","tier":"Legacy"},
    "azure-di": {"name":"Azure Document Intelligence (Layout)","provider":"Azure","tier":"OCR Service"},
    "aws-textract": {"name":"AWS Textract (DetectText)","provider":"AWS","tier":"OCR Service"},
    "qwen2.5-vl-72b": {"name":"Qwen2.5‑VL‑72B","provider":"Qwen","tier":"Open‑weight"},
    "qwen2.5-vl-7b": {"name":"Qwen2.5‑VL‑7B","provider":"Qwen","tier":"Open‑weight"},
}

# Pricing (USD per 1M tokens) or per page (USD)
OPENAI_PRICES = {
    "gpt5": {"in": 1.25, "out": 10.0},
    "gpt5_1": {"in": 1.25, "out": 10.0},
    "gpt5_2": {"in": 1.75, "out": 14.0},
    "gpt5_mini": {"in": 0.25, "out": 2.0},
    "gpt5_nano": {"in": 0.05, "out": 0.4},
    "gpt5_2_chat": {"in": 0.75, "out": 6.0},
    "gpt4_1": {"in": 2.0, "out": 8.0},
    "gpt4_1-mini": {"in": 0.40, "out": 1.60},
    "gpt4o": {"in": 2.50, "out": 10.0},
    # gpt4o-mini price not available from sources used here
}

ANTHROPIC_PRICES = {
    "claude-opus-4-1": {"in": 15.0, "out": 75.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    "claude-3-5-sonnet": {"in": 3.0, "out": 15.0},
}

GEMINI_PRICES = {
    "gemini-3-pro": {"in": 2.0, "out": 12.0},
    "gemini-3-flash": {"in": 0.50, "out": 3.0},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40},
}

# per-page pricing
MISTRAL_OCR_PER_PAGE = 0.001  # $1 / 1000 pages
AWS_TEXTRACT_PER_PAGE = 0.0015  # DetectDocumentText example (US West)


def avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compute_cost_openai():
    # derive avg prompt/completion tokens from gpt5 logs
    path = BASE / "gpt5" / "gpt5_costs.jsonl"
    if not path.exists():
        return {}, None, None, None
    rows = load_jsonl(path)
    avg_prompt = avg([r["prompt_tokens"] for r in rows])
    avg_comp = avg([r["completion_tokens"] for r in rows])
    avg_cost = avg([r["cost_usd"] for r in rows])
    return {"avg_prompt": avg_prompt, "avg_comp": avg_comp, "avg_cost": avg_cost}, avg_prompt, avg_comp, avg_cost


def compute_cost_openai_usage(path: Path):
    if not path.exists():
        return None, None
    rows = load_jsonl(path)
    in_toks = []
    out_toks = []
    for r in rows:
        usage = r.get("usage") or {}
        if usage.get("input_tokens") is not None:
            in_toks.append(usage.get("input_tokens"))
        if usage.get("output_tokens") is not None:
            out_toks.append(usage.get("output_tokens"))
    return avg(in_toks), avg(out_toks)


def compute_cost_from_tokens(prompt_tokens, completion_tokens, price_in, price_out):
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000.0


def main():
    entries = []
    model_dirs = [p for p in BASE.iterdir() if p.is_dir()]

    gpt5_stats, avg_prompt, avg_comp, avg_cost = compute_cost_openai()

    for d in model_dirs:
        diff = d / "diffs" / "diff_summary.json"
        if not diff.exists():
            continue
        data = json.loads(diff.read_text())
        results = data.get("results", [])
        # overall averages include all pages
        avg_html_incl = data.get("avg_html_ratio")
        avg_text_incl = data.get("avg_text_ratio")
        # exclude Adventure Sheet (page-011)
        filtered = [r for r in results if r.get("page") != "page-011"]
        avg_html_excl = avg([r.get("html_ratio") for r in filtered]) if filtered else None
        avg_text_excl = avg([r.get("text_ratio") for r in filtered]) if filtered else None
        page011 = next((r for r in results if r.get("page") == "page-011"), None)

        # treat missing/empty pages (0 ratios) as dropped
        dropped = [r.get("page") for r in results if (r.get("html_ratio") == 0 or r.get("text_ratio") == 0)]
        kept = [r for r in results if r.get("page") not in dropped]
        avg_html_ignore_dropped = avg([r.get("html_ratio") for r in kept]) if kept else None
        avg_text_ignore_dropped = avg([r.get("text_ratio") for r in kept]) if kept else None

        entry = {
            "id": d.name,
            "name": META.get(d.name, {}).get("name", d.name),
            "provider": META.get(d.name, {}).get("provider", "Unknown"),
            "tier": META.get(d.name, {}).get("tier", ""),
            "avg_html_ratio_incl": avg_html_incl,
            "avg_text_ratio_incl": avg_text_incl,
            "avg_html_ratio_excl": round(avg_html_excl, 6) if avg_html_excl is not None else None,
            "avg_text_ratio_excl": round(avg_text_excl, 6) if avg_text_excl is not None else None,
            "avg_html_ratio_ignore_dropped": round(avg_html_ignore_dropped, 6) if avg_html_ignore_dropped is not None else None,
            "avg_text_ratio_ignore_dropped": round(avg_text_ignore_dropped, 6) if avg_text_ignore_dropped is not None else None,
            "dropped_pages": dropped,
            "page011_html_ratio": page011.get("html_ratio") if page011 else None,
            "page011_text_ratio": page011.get("text_ratio") if page011 else None,
        }

        # costs
        cost_per_page = None
        cost_note = None
        cost_estimated = False

        if d.name == "gpt5" and avg_cost is not None:
            cost_per_page = avg_cost
            cost_note = "measured"
        elif d.name in {"gpt5_1", "gpt5_2"}:
            in_toks, out_toks = compute_cost_openai_usage(d / "openai_usage.jsonl")
            if in_toks is not None and out_toks is not None:
                p = OPENAI_PRICES[d.name]
                cost_per_page = compute_cost_from_tokens(in_toks, out_toks, p["in"], p["out"])
                cost_note = "measured tokens"
        elif d.name in OPENAI_PRICES and avg_prompt is not None and avg_comp is not None:
            p = OPENAI_PRICES[d.name]
            cost_per_page = compute_cost_from_tokens(avg_prompt, avg_comp, p["in"], p["out"])
            cost_note = "estimated from GPT‑5 token counts"
            cost_estimated = True
        elif d.name in ANTHROPIC_PRICES:
            usage_path = d / "claude_usage.jsonl"
            if usage_path.exists():
                rows = load_jsonl(usage_path)
                in_toks = [r["usage"]["input_tokens"] for r in rows if r.get("usage")]
                out_toks = [r["usage"]["output_tokens"] for r in rows if r.get("usage")]
                if in_toks and out_toks:
                    p = ANTHROPIC_PRICES[d.name]
                    cost_per_page = compute_cost_from_tokens(avg(in_toks), avg(out_toks), p["in"], p["out"])
        elif d.name in GEMINI_PRICES:
            usage_path = d / "gemini_usage.jsonl"
            if usage_path.exists():
                rows = load_jsonl(usage_path)
                in_toks = [r["usage_metadata"]["prompt_token_count"] for r in rows if r.get("usage_metadata")]
                out_toks = [r["usage_metadata"]["candidates_token_count"] for r in rows if r.get("usage_metadata")]
                if in_toks and out_toks:
                    p = GEMINI_PRICES[d.name]
                    cost_per_page = compute_cost_from_tokens(avg(in_toks), avg(out_toks), p["in"], p["out"])
        elif d.name in {"mistral-ocr2", "mistral-ocr3"}:
            cost_per_page = MISTRAL_OCR_PER_PAGE
            cost_note = "$1 / 1000 pages"
        elif d.name == "aws-textract":
            cost_per_page = AWS_TEXTRACT_PER_PAGE
            cost_note = "DetectDocumentText US West example"
        elif d.name == "azure-di":
            cost_note = "pricing via Azure calculator"
        elif d.name in {"qwen2.5-vl-72b", "qwen2.5-vl-7b"}:
            cost_note = "HF routed; provider pricing varies"

        entry["cost_per_page_usd"] = round(cost_per_page, 6) if cost_per_page is not None else None
        entry["cost_note"] = cost_note
        entry["cost_estimated"] = cost_estimated
        entries.append(entry)

    OUT.write_text(json.dumps({"pages_default": 226, "entries": entries}, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} with {len(entries)} entries")


if __name__ == "__main__":
    main()
