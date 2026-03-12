#!/usr/bin/env node
/**
 * Discover available AI models across providers (OpenAI, Anthropic, Google).
 * Cross-reference against eval registry to flag untested models.
 *
 * Usage:
 *   npx tsx scripts/discover-models.ts              # Full report
 *   npx tsx scripts/discover-models.ts --check-new  # Flag untested models
 *   npx tsx scripts/discover-models.ts --summary    # Quick tier summary
 *
 * Or with Node 22+ (no tsx needed):
 *   node --experimental-strip-types scripts/discover-models.ts --check-new
 *
 * Adapted from storybook/scripts/discover-models.ts for codex-forge.
 */

import { readFileSync } from "fs";
import { join } from "path";

// ── Tier Classification ──────────────────────────────────────────────────────

type Tier = "sota" | "mid" | "cheap" | "reasoning" | "legacy";

const TIER_PATTERNS: [RegExp, Tier][] = [
  // Reasoning models (check before generic GPT/Claude matches)
  [/^o[134]\b/, "reasoning"],
  [/^o[134]-/, "reasoning"],

  // Budget qualifiers — checked FIRST so "gpt-4.1-mini" hits cheap
  [/[-_]mini\b/, "cheap"],
  [/[-_]nano\b/, "cheap"],
  [/flash-lite/, "cheap"],
  [/flash-8b/, "cheap"],
  [/claude-haiku/, "cheap"],

  // OpenAI flagship
  [/^gpt-5/, "sota"],

  // OpenAI mid-tier
  [/^gpt-4[.-]1/, "mid"],

  // OpenAI legacy
  [/^gpt-4o/, "legacy"],
  [/^gpt-4\b/, "legacy"],
  [/^chatgpt-4o/, "legacy"],

  // Anthropic flagship
  [/claude-opus/, "sota"],

  // Anthropic mid-tier
  [/claude-sonnet/, "mid"],

  // Anthropic legacy
  [/claude-3/, "legacy"],
  [/claude-2/, "legacy"],

  // Google flagship
  [/gemini-3[\.-]?[12]?-?pro/, "sota"],
  [/gemini-2[.-]5-pro/, "sota"],

  // Google mid-tier
  [/gemini-3[\.-]?[12]?-?flash\b/, "mid"],
  [/gemini-2[.-]5-flash\b/, "mid"],
  [/gemini-flash/, "mid"],

  // Google legacy
  [/gemini-2[.-]0/, "legacy"],
  [/gemini-1/, "legacy"],
];

const TIER_LABELS: Record<Tier, string> = {
  sota: "SOTA      (flagship/frontier)",
  mid: "MID       (strong mid-tier)",
  cheap: "CHEAP     (budget/fast)",
  reasoning: "REASONING (chain-of-thought)",
  legacy: "LEGACY    (older generation)",
};

const TIER_ORDER: Tier[] = ["sota", "mid", "cheap", "reasoning", "legacy"];

function classifyTier(modelId: string): Tier {
  const lower = modelId.toLowerCase();
  for (const [pattern, tier] of TIER_PATTERNS) {
    if (pattern.test(lower)) return tier;
  }
  return "mid"; // conservative default
}

// ── Skip Patterns ────────────────────────────────────────────────────────────

const OPENAI_CHAT_PATTERNS = [/^gpt-/, /^o[134]-/, /^chatgpt-/];
const OPENAI_SKIP = [
  /-instruct/,
  /^gpt-3\.5/,
  /^gpt-4-\d{4}/,
  /-realtime/,
  /-audio/,
  /-transcribe/,
  /-tts/,
  /-search-/,
  /-image/,
  /-codex/,
  /^chatgpt-image/,
  /-deep-research/,
];
const GOOGLE_SKIP = [
  /^gemma-/,
  /-tts/,
  /-image/,
  /-robotics-/,
  /^deep-research-/,
  /-customtools/,
  /^gemini-2\.0-/,
  /^gemini-1\./,
];

// ── Types ────────────────────────────────────────────────────────────────────

interface ModelInfo {
  id: string;
  provider: string;
  displayName?: string;
  created: string;
  tier: Tier;
}

interface ProviderResult {
  provider: string;
  display: string;
  keyPresent: boolean;
  models: ModelInfo[];
  error?: string;
}

// ── Provider Queries ─────────────────────────────────────────────────────────

async function queryOpenAI(apiKey: string): Promise<ModelInfo[]> {
  const resp = await fetch("https://api.openai.com/v1/models", {
    headers: { Authorization: `Bearer ${apiKey}` },
    signal: AbortSignal.timeout(15000),
  });
  if (!resp.ok) throw new Error(`OpenAI API: ${resp.status} ${resp.statusText}`);
  const data = (await resp.json()) as { data: Array<{ id: string; created: number }> };

  return data.data
    .filter((m) => OPENAI_CHAT_PATTERNS.some((p) => p.test(m.id)))
    .filter((m) => !OPENAI_SKIP.some((p) => p.test(m.id)))
    .map((m) => ({
      id: m.id,
      provider: "openai",
      created: new Date(m.created * 1000).toISOString().slice(0, 10),
      tier: classifyTier(m.id),
    }))
    .sort((a, b) => b.created.localeCompare(a.created));
}

async function queryAnthropic(apiKey: string): Promise<ModelInfo[]> {
  try {
    const resp = await fetch("https://api.anthropic.com/v1/models", {
      headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
      signal: AbortSignal.timeout(15000),
    });
    if (!resp.ok) throw new Error(`${resp.status}`);
    const data = (await resp.json()) as {
      data: Array<{ id: string; display_name?: string; created_at?: string | number }>;
    };

    return data.data.map((m) => {
      let created = "unknown";
      if (typeof m.created_at === "string") created = m.created_at.slice(0, 10);
      else if (typeof m.created_at === "number" && m.created_at > 0)
        created = new Date(m.created_at * 1000).toISOString().slice(0, 10);
      return {
        id: m.id,
        provider: "anthropic",
        displayName: m.display_name,
        created,
        tier: classifyTier(m.id),
      };
    });
  } catch {
    // Fallback to known models if endpoint isn't available
    console.error("  Note: Anthropic /v1/models unavailable. Using known model list.");
    return [
      { id: "claude-opus-4-6", provider: "anthropic", displayName: "Claude Opus 4.6", created: "2025-12-01", tier: "sota" as Tier },
      { id: "claude-sonnet-4-6", provider: "anthropic", displayName: "Claude Sonnet 4.6", created: "2025-12-01", tier: "mid" as Tier },
      { id: "claude-haiku-4-5-20251001", provider: "anthropic", displayName: "Claude Haiku 4.5", created: "2025-10-01", tier: "cheap" as Tier },
    ];
  }
}

async function queryGoogle(apiKey: string): Promise<ModelInfo[]> {
  const resp = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`,
    { signal: AbortSignal.timeout(15000) },
  );
  if (!resp.ok) throw new Error(`Google API: ${resp.status} ${resp.statusText}`);
  const data = (await resp.json()) as {
    models: Array<{
      name: string;
      displayName?: string;
      supportedGenerationMethods?: string[];
    }>;
  };

  return data.models
    .filter((m) => m.supportedGenerationMethods?.includes("generateContent"))
    .map((m) => {
      const id = m.name.replace("models/", "");
      return { id, provider: "google", displayName: m.displayName, created: "", tier: classifyTier(id) };
    })
    .filter((m) => !GOOGLE_SKIP.some((p) => p.test(m.id)));
}

// ── Registry Cross-Reference ─────────────────────────────────────────────────

function loadTestedModels(): Set<string> {
  const tested = new Set<string>();
  try {
    const registryPath = join(process.cwd(), "docs/evals/registry.yaml");
    const content = readFileSync(registryPath, "utf-8");
    // Extract model names from "model:" fields and score entries
    const modelPattern = /model:\s*"([^"]+)"/g;
    let match;
    while ((match = modelPattern.exec(content)) !== null) {
      tested.add(normalizeModelName(match[1]));
    }
  } catch {
    // No registry yet — all models are "new"
  }
  return tested;
}

function normalizeModelName(name: string): string {
  return name
    .toLowerCase()
    .replace(/^claude-/, "")
    .replace(/^gpt-/, "")
    .replace(/-\d{4}-\d{2}-\d{2}$/, "") // strip dated snapshots
    .replace(/-\d{8}$/, ""); // strip compact date suffixes
}

// ── Output Formatting ────────────────────────────────────────────────────────

function printReport(results: ProviderResult[], checkNew: boolean, tested: Set<string>) {
  console.log("═══ Model Discovery Report ═══\n");

  // API key status
  console.log("API Key Status:");
  for (const r of results) {
    const status = r.keyPresent ? (r.error ? `⚠ Error: ${r.error}` : "✓ configured") : "✗ not set";
    console.log(`  ${r.display.padEnd(20)} ${status}`);
  }
  console.log();

  // Models by provider
  for (const r of results) {
    if (!r.models.length) continue;
    console.log(`── ${r.display} (${r.models.length} models) ──`);

    const byTier = new Map<Tier, ModelInfo[]>();
    for (const m of r.models) {
      if (!byTier.has(m.tier)) byTier.set(m.tier, []);
      byTier.get(m.tier)!.push(m);
    }

    for (const tier of TIER_ORDER) {
      const models = byTier.get(tier);
      if (!models?.length) continue;
      console.log(`  ${TIER_LABELS[tier]}:`);
      for (const m of models) {
        const name = m.displayName ? `${m.id} (${m.displayName})` : m.id;
        let flag = "";
        if (checkNew) {
          const norm = normalizeModelName(m.id);
          flag = tested.has(norm) ? " [TESTED]" : " [NEW]";
        }
        const date = m.created ? ` (${m.created})` : "";
        console.log(`    ${name}${date}${flag}`);
      }
    }
    console.log();
  }
}

function printSummary(results: ProviderResult[], tested: Set<string>) {
  console.log("═══ Model Discovery Summary ═══\n");

  const allModels = results.flatMap((r) => r.models);
  const byTier = new Map<Tier, ModelInfo[]>();
  for (const m of allModels) {
    if (!byTier.has(m.tier)) byTier.set(m.tier, []);
    byTier.get(m.tier)!.push(m);
  }

  for (const tier of TIER_ORDER) {
    const models = byTier.get(tier) ?? [];
    const untested = models.filter((m) => !tested.has(normalizeModelName(m.id)));
    const newest = models[0];
    console.log(
      `${TIER_LABELS[tier]}: ${models.length} models` +
        (untested.length ? ` (${untested.length} untested)` : "") +
        (newest ? ` — newest: ${newest.id}` : ""),
    );
  }

  // Highlight untested models worth trying
  const untestedSota = allModels.filter(
    (m) => m.tier === "sota" && !tested.has(normalizeModelName(m.id)),
  );
  const untestedCheap = allModels.filter(
    (m) => m.tier === "cheap" && !tested.has(normalizeModelName(m.id)),
  );
  if (untestedSota.length || untestedCheap.length) {
    console.log("\n⚡ Worth testing:");
    for (const m of untestedSota) console.log(`  SOTA: ${m.id} (${m.provider})`);
    for (const m of untestedCheap) console.log(`  CHEAP: ${m.id} (${m.provider})`);
  }
}

// ── Main ─────────────────────────────────────────────────────────────────────

const PROVIDERS = [
  { key: "openai", envKey: "OPENAI_API_KEY", display: "OpenAI", query: queryOpenAI },
  { key: "anthropic", envKey: "ANTHROPIC_API_KEY", display: "Anthropic", query: queryAnthropic },
  { key: "google", envKey: "GEMINI_API_KEY", display: "Google (Gemini)", query: queryGoogle },
] as const;

async function main() {
  const args = process.argv.slice(2);
  const checkNew = args.includes("--check-new");
  const summary = args.includes("--summary");

  const tested = loadTestedModels();
  const results: ProviderResult[] = [];

  // Query all providers in parallel
  const queries = PROVIDERS.map(async (p) => {
    const apiKey = process.env[p.envKey];
    const result: ProviderResult = {
      provider: p.key,
      display: p.display,
      keyPresent: !!apiKey,
      models: [],
    };

    if (!apiKey) {
      result.error = `Set ${p.envKey} to enable`;
      return result;
    }

    try {
      result.models = await p.query(apiKey);
    } catch (e) {
      result.error = e instanceof Error ? e.message : String(e);
    }

    return result;
  });

  results.push(...(await Promise.all(queries)));

  if (summary) {
    printSummary(results, tested);
  } else {
    printReport(results, checkNew, tested);
  }

  // Total count
  const total = results.reduce((sum, r) => sum + r.models.length, 0);
  const totalUntested = results
    .flatMap((r) => r.models)
    .filter((m) => !tested.has(normalizeModelName(m.id))).length;
  console.log(`Total: ${total} models across ${results.filter((r) => r.models.length).length} providers`);
  if (checkNew || summary) console.log(`Untested: ${totalUntested}`);
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
