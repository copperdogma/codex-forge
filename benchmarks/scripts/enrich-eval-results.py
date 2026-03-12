#!/usr/bin/env python3
"""
Enrich promptfoo eval results with cost estimates and produce a summary table.

Reads a promptfoo results JSON, extracts per-test token usage and latency,
computes cost from a pricing table, and prints a ranked summary.

Usage:
    python benchmarks/scripts/enrich-eval-results.py results/foo.json
    python benchmarks/scripts/enrich-eval-results.py results/foo.json --format registry
"""
import json
import sys
from pathlib import Path

# ── Pricing Table (USD per 1M tokens: [input, output]) ──────────────────────
# Update when models change. Source: provider pricing pages.
# fmt: off
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI — https://platform.openai.com/docs/pricing
    "gpt-5.4":         (2.00,  8.00),
    "gpt-5.4-pro":     (2.00,  8.00),
    "gpt-5.3":         (2.00,  8.00),
    "gpt-5.2":         (2.00,  8.00),
    "gpt-5.2-pro":     (2.00,  8.00),
    "gpt-5.1":         (2.00,  8.00),
    "gpt-5":           (2.00,  8.00),
    "gpt-5-pro":       (10.00, 40.00),
    "gpt-5-mini":      (0.40,  1.60),
    "gpt-5-nano":      (0.10,  0.40),
    "gpt-4.1":         (2.00,  8.00),
    "gpt-4.1-mini":    (0.40,  1.60),
    "gpt-4.1-nano":    (0.10,  0.40),
    "gpt-4o":          (2.50, 10.00),
    "gpt-4o-mini":     (0.15,  0.60),
    # Anthropic — https://docs.anthropic.com/en/docs/about-claude/models
    "claude-opus-4-6":              (15.00, 75.00),
    "claude-sonnet-4-6":            (3.00,  15.00),
    "claude-sonnet-4-5-20250929":   (3.00,  15.00),
    "claude-haiku-4-5-20251001":    (0.80,   4.00),
    # Google — https://ai.google.dev/pricing
    "gemini-2.5-pro":            (1.25,  10.00),
    "gemini-2.5-flash":          (0.15,   0.60),
    "gemini-2.5-flash-lite":     (0.075,  0.30),
    "gemini-3-pro-preview":      (1.25,  10.00),
    "gemini-3.1-pro-preview":    (1.25,  10.00),
    "gemini-3-flash-preview":    (0.15,   0.60),
    "gemini-3.1-flash-lite-preview": (0.075, 0.30),
}
# fmt: on


def normalize_model_id(provider_id: str) -> str:
    """Extract the model name from a promptfoo provider ID."""
    # "openai:gpt-5.4" → "gpt-5.4"
    # "anthropic:messages:claude-opus-4-6" → "claude-opus-4-6"
    # "google:gemini-3.1-pro-preview" → "gemini-3.1-pro-preview"
    parts = provider_id.split(":")
    return parts[-1]


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Compute cost in USD from token counts. Returns None if model not in table."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return None
    input_price, output_price = pricing
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price


def main():
    if len(sys.argv) < 2:
        print("Usage: python enrich-eval-results.py <results.json> [--format registry]")
        sys.exit(1)

    results_path = Path(sys.argv[1])
    registry_format = "--format" in sys.argv and "registry" in sys.argv

    data = json.loads(results_path.read_text())
    results = data.get("results", {}).get("results", [])

    # Group by provider
    by_provider: dict[str, list[dict]] = {}
    for r in results:
        provider_id = r.get("provider", {}).get("id", "?")
        label = r.get("provider", {}).get("label", provider_id)
        model = normalize_model_id(provider_id)

        error = r.get("error", "")
        if "API error" in str(error) or "not a chat model" in str(error):
            continue

        test_name = r.get("vars", {}).get("golden_path", "?").split("/")[-1].replace(".html", "")

        # Token usage: check response.tokenUsage first, then top-level
        resp = r.get("response") or {}
        token_usage = resp.get("tokenUsage") or r.get("tokenUsage") or {}
        prompt_tokens = token_usage.get("prompt", 0)
        completion_tokens = token_usage.get("completion", 0)
        total_tokens = token_usage.get("total", 0)

        latency_ms = r.get("latencyMs") or resp.get("latencyMs", 0)
        score = r.get("score", 0)

        # Cost: use promptfoo's if available, else compute
        cost = r.get("cost") or resp.get("cost")
        cost_estimated = False
        if not cost or cost == 0:
            cost = estimate_cost(model, prompt_tokens, completion_tokens)
            cost_estimated = True

        entry = {
            "label": label,
            "model": model,
            "test": test_name,
            "score": score,
            "latency_ms": latency_ms,
            "cost_usd": cost,
            "cost_estimated": cost_estimated,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        by_provider.setdefault(label, []).append(entry)

    # Compute per-provider averages
    summaries = []
    for label, entries in by_provider.items():
        n = len(entries)
        avg_score = sum(e["score"] for e in entries) / n
        avg_latency = sum(e["latency_ms"] for e in entries) / n
        costs = [e["cost_usd"] for e in entries if e["cost_usd"] is not None]
        avg_cost = sum(costs) / len(costs) if costs else None
        total_prompt = sum(e["prompt_tokens"] for e in entries)
        total_completion = sum(e["completion_tokens"] for e in entries)

        per_test = {e["test"]: e["score"] for e in entries}

        summaries.append({
            "label": label,
            "model": entries[0]["model"],
            "avg_score": avg_score,
            "avg_latency_ms": round(avg_latency),
            "avg_cost_usd": avg_cost,
            "cost_estimated": entries[0]["cost_estimated"],
            "per_test": per_test,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "n_tests": n,
        })

    # Sort by score descending
    summaries.sort(key=lambda s: s["avg_score"], reverse=True)

    if registry_format:
        _print_registry(summaries)
    else:
        _print_table(summaries)


def _print_table(summaries: list[dict]):
    """Print a human-readable comparison table."""
    print("=" * 100)
    print(f"{'Model':25s} | {'Score':>8s} | {'Latency':>10s} | {'Cost/call':>10s} | {'Tokens (p+c)':>16s} | Per-test scores")
    print("-" * 100)
    for s in summaries:
        cost_str = f"${s['avg_cost_usd']:.4f}" if s["avg_cost_usd"] is not None else "unknown"
        if s["cost_estimated"]:
            cost_str += "*"
        latency_str = f"{s['avg_latency_ms'] / 1000:.1f}s"
        tokens_str = f"{s['total_prompt_tokens']:,}+{s['total_completion_tokens']:,}"
        per_test = " | ".join(f"{k}={v:.3f}" for k, v in s["per_test"].items())
        print(f"{s['label']:25s} | {s['avg_score']:8.3f} | {latency_str:>10s} | {cost_str:>10s} | {tokens_str:>16s} | {per_test}")

    print()
    print("* = cost estimated from token counts (not reported by provider)")
    print()

    # Value analysis
    if len(summaries) >= 2:
        best = summaries[0]
        print(f"Quality winner: {best['label']} (score={best['avg_score']:.3f})")
        cheapest = min(summaries, key=lambda s: s["avg_cost_usd"] or float("inf"))
        if cheapest["label"] != best["label"]:
            print(f"Value winner:   {cheapest['label']} (score={cheapest['avg_score']:.3f}, cost={cheapest['avg_cost_usd']:.4f})")
        fastest = min(summaries, key=lambda s: s["avg_latency_ms"])
        if fastest["label"] != best["label"]:
            print(f"Speed winner:   {fastest['label']} (score={fastest['avg_score']:.3f}, latency={fastest['avg_latency_ms']/1000:.1f}s)")


def _print_registry(summaries: list[dict]):
    """Print in eval registry YAML format for copy-paste."""
    print("    scores:")
    for s in summaries:
        cost_line = ""
        if s["avg_cost_usd"] is not None:
            cost_line = f"\n        cost_usd: {s['avg_cost_usd']:.4f}"
            if s["cost_estimated"]:
                cost_line += "\n        cost_estimated: true"
        per_test = ", ".join(f"{k}: {v:.3f}" for k, v in s["per_test"].items())
        print(f"""      - model: "{s['label']}"
        metrics:
          structure_preservation: {s['avg_score']:.3f}
          {per_test.replace(', ', chr(10) + '          ')}
        latency_ms: {s['avg_latency_ms']}{cost_line}
        measured: 2026-03-11""")


if __name__ == "__main__":
    main()
