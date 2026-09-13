import { normalizeDataStatus, type DataStatus, type SnapshotPayload } from "./snapshot";

/**
 * Canonical research-answer display cap (shared with Agent A backend:
 * `scripts/enrich_tavily_context.py`, `scripts/enrich_you_context.py`,
 * `you_client.py` all truncate stored evidence `content` to 1200 chars).
 * Renderers must truncate through `truncateResearchAnswer` so the cap,
 * provenance banner, and CONTEXT badge stay consistent everywhere.
 */
export const RESEARCH_ANSWER_MAX_CHARS = 1200;

export interface TruncatedResearchAnswer {
  text: string;
  truncated: boolean;
  originalLength: number;
}

/** Enforce the canonical 1200-char cap at render. Never throws. */
export function truncateResearchAnswer(
  value: string | null | undefined,
  max: number = RESEARCH_ANSWER_MAX_CHARS,
): TruncatedResearchAnswer {
  const text = (value ?? "").replace(/\s+/g, " ").trim();
  if (!text) {
    return { text: "No research synthesis was returned.", truncated: false, originalLength: 0 };
  }
  if (text.length <= max) {
    return { text, truncated: false, originalLength: text.length };
  }
  return {
    text: `${text.slice(0, max - 1).trimEnd()}…`,
    truncated: true,
    originalLength: text.length,
  };
}

export type ResearchContextCategory = "foreign_flow" | "fundamentals" | "events";

export interface TavilyEvidenceRecord {
  source_type?: string;
  category?: string;
  provider?: string;
  url: string;
  title: string;
  content?: string;
  relevance_score?: number;
  retrieved_at?: string;
  request_id?: string;
  quantitative_use: false;
}

export interface TavilyCategoryContext {
  status?: string;
  query?: string;
  source_policy?: string[];
  source_count?: number;
  records: TavilyEvidenceRecord[];
  note?: string;
}

export interface TavilyCrawlContext {
  status?: string;
  url?: string;
  source_count?: number;
  records: TavilyEvidenceRecord[];
  note?: string;
}

export interface TavilyContext {
  status?: string;
  completion_status?: string;
  provider?: string;
  as_of?: string;
  retrieved_at?: string;
  quantitative_use?: false;
  scope?: string;
  categories: Partial<Record<ResearchContextCategory, TavilyCategoryContext>>;
  crawl?: TavilyCrawlContext;
}

const categories: ResearchContextCategory[] = [
  "foreign_flow",
  "fundamentals",
  "events",
];

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function safeUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

function normalizeRecords(value: unknown, category?: string): TavilyEvidenceRecord[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const row = asRecord(item);
    const url = safeUrl(row?.url);
    if (!row || !url) return [];
    const title = typeof row.title === "string" && row.title.trim()
      ? row.title.trim().slice(0, 300)
      : url;
    const score = row.relevance_score;
    return [{
      source_type: typeof row.source_type === "string" ? row.source_type : "WEB_CONTEXT",
      category: typeof row.category === "string" ? row.category : category,
      provider: typeof row.provider === "string" ? row.provider : "tavily",
      url,
      title,
      content: typeof row.content === "string" ? row.content.trim().slice(0, RESEARCH_ANSWER_MAX_CHARS) : undefined,
      relevance_score: typeof score === "number" && Number.isFinite(score) ? score : undefined,
      retrieved_at: typeof row.retrieved_at === "string" ? row.retrieved_at : undefined,
      request_id: typeof row.request_id === "string" ? row.request_id : undefined,
      quantitative_use: false as const,
    }];
  });
}

function normalizeCategory(value: unknown, category: ResearchContextCategory): TavilyCategoryContext | null {
  const row = asRecord(value);
  if (!row) return null;
  return {
    status: typeof row.status === "string" ? row.status : undefined,
    query: typeof row.query === "string" ? row.query : undefined,
    source_policy: Array.isArray(row.source_policy)
      ? row.source_policy.filter((item): item is string => typeof item === "string")
      : undefined,
    source_count: typeof row.source_count === "number" && Number.isFinite(row.source_count)
      ? row.source_count
      : undefined,
    records: normalizeRecords(row.records, category),
    note: typeof row.note === "string" ? row.note : undefined,
  };
}

function normalizeCrawl(value: unknown): TavilyCrawlContext | undefined {
  const row = asRecord(value);
  if (!row) return undefined;
  return {
    status: typeof row.status === "string" ? row.status : undefined,
    url: safeUrl(row.url) ?? undefined,
    source_count: typeof row.source_count === "number" && Number.isFinite(row.source_count)
      ? row.source_count
      : undefined,
    records: normalizeRecords(row.records, "crawl"),
    note: typeof row.note === "string" ? row.note : undefined,
  };
}

export function normalizeTavilyContext(value: unknown): TavilyContext | null {
  const row = asRecord(value);
  if (!row || row.quantitative_use === true) return null;
  const rawCategories = asRecord(row.categories);
  const normalizedCategories: Partial<Record<ResearchContextCategory, TavilyCategoryContext>> = {};
  for (const category of categories) {
    const normalized = normalizeCategory(rawCategories?.[category], category);
    if (normalized) normalizedCategories[category] = normalized;
  }
  return {
    status: typeof row.status === "string" ? row.status : undefined,
    completion_status: typeof row.completion_status === "string" ? row.completion_status : undefined,
    provider: typeof row.provider === "string" ? row.provider : undefined,
    as_of: typeof row.as_of === "string" ? row.as_of : undefined,
    retrieved_at: typeof row.retrieved_at === "string" ? row.retrieved_at : undefined,
    quantitative_use: false,
    scope: typeof row.scope === "string" ? row.scope : undefined,
    categories: normalizedCategories,
    crawl: normalizeCrawl(row.crawl),
  };
}

export function getTavilyCategory(
  payload: SnapshotPayload | null | undefined,
  category: ResearchContextCategory,
): TavilyCategoryContext {
  return normalizeTavilyContext(payload?.tavily_context)?.categories[category] ?? {
    records: [],
  };
}

/**
 * A category with sources is intentionally READY_WITH_GAPS: sources improve
 * discoverability, but they do not turn qualitative web text into a
 * quantitative confirmation metric.
 */
export function getTavilyCategoryStatus(
  payload: SnapshotPayload | null | undefined,
  category: ResearchContextCategory,
): DataStatus {
  const context = normalizeTavilyContext(payload?.tavily_context);
  const entry = context?.categories[category];
  if (entry?.records.length) return "READY_WITH_GAPS";
  if (normalizeDataStatus(entry?.status) === "FAILED") return "FAILED";
  return "DATA_GAP";
}

export function getTavilyCrawl(payload: SnapshotPayload | null | undefined): TavilyCrawlContext {
  return normalizeTavilyContext(payload?.tavily_context)?.crawl ?? { records: [] };
}
export interface YouEvidenceRecord {
  source_type?: string;
  category?: string;
  provider?: string;
  url: string;
  title: string;
  content?: string;
  retrieved_at?: string;
  request_id?: string;
  quantitative_use: false;
}

export interface YouCategoryContext {
  status?: string;
  query?: string;
  source_policy?: string[];
  source_count?: number;
  records: YouEvidenceRecord[];
  research_answer?: string;
  note?: string;
}

export interface YouContext {
  status?: string;
  completion_status?: string;
  provider?: string;
  as_of?: string;
  retrieved_at?: string;
  quantitative_use?: false;
  scope?: string;
  source_policy?: string[];
  categories: Partial<Record<ResearchContextCategory, YouCategoryContext>>;
}

function normalizeYouRecords(value: unknown, category?: string): YouEvidenceRecord[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const row = asRecord(item);
    const url = safeUrl(row?.url);
    if (!row || !url) return [];
    const title = typeof row.title === "string" && row.title.trim()
      ? row.title.trim().slice(0, 300)
      : url;
    return [{
      source_type: typeof row.source_type === "string" ? row.source_type : "WEB_CONTEXT",
      category: typeof row.category === "string" ? row.category : category,
      provider: typeof row.provider === "string" ? row.provider : "you",
      url,
      title,
      content: typeof row.content === "string" ? row.content.trim().slice(0, RESEARCH_ANSWER_MAX_CHARS) : undefined,
      retrieved_at: typeof row.retrieved_at === "string" ? row.retrieved_at : undefined,
      request_id: typeof row.request_id === "string" ? row.request_id : undefined,
      quantitative_use: false as const,
    }];
  });
}

function normalizeYouCategory(
  value: unknown,
  category: ResearchContextCategory,
): YouCategoryContext | null {
  const row = asRecord(value);
  if (!row) return null;
  return {
    status: typeof row.status === "string" ? row.status : undefined,
    query: typeof row.query === "string" ? row.query : undefined,
    source_policy: Array.isArray(row.source_policy)
      ? row.source_policy.filter((item): item is string => typeof item === "string")
      : undefined,
    source_count: typeof row.source_count === "number" && Number.isFinite(row.source_count)
      ? row.source_count
      : undefined,
    records: normalizeYouRecords(row.records, category),
    research_answer: typeof row.research_answer === "string" ? row.research_answer : undefined,
    note: typeof row.note === "string" ? row.note : undefined,
  };
}

export function normalizeYouContext(value: unknown): YouContext | null {
  const row = asRecord(value);
  if (!row || row.quantitative_use === true) return null;
  const rawCategories = asRecord(row.categories);
  const normalizedCategories: Partial<Record<ResearchContextCategory, YouCategoryContext>> = {};
  for (const category of categories) {
    const normalized = normalizeYouCategory(rawCategories?.[category], category);
    if (normalized) normalizedCategories[category] = normalized;
  }
  return {
    status: typeof row.status === "string" ? row.status : undefined,
    completion_status: typeof row.completion_status === "string" ? row.completion_status : undefined,
    provider: typeof row.provider === "string" ? row.provider : undefined,
    as_of: typeof row.as_of === "string" ? row.as_of : undefined,
    retrieved_at: typeof row.retrieved_at === "string" ? row.retrieved_at : undefined,
    quantitative_use: false,
    scope: typeof row.scope === "string" ? row.scope : undefined,
    source_policy: Array.isArray(row.source_policy)
      ? row.source_policy.filter((item): item is string => typeof item === "string")
      : undefined,
    categories: normalizedCategories,
  };
}

export function getYouCategory(
  payload: SnapshotPayload | null | undefined,
  category: ResearchContextCategory,
): YouCategoryContext {
  return normalizeYouContext(payload?.you_context)?.categories[category] ?? { records: [] };
}

export function getYouCategoryStatus(
  payload: SnapshotPayload | null | undefined,
  category: ResearchContextCategory,
): DataStatus {
  const context = normalizeYouContext(payload?.you_context);
  const entry = context?.categories[category];
  if (entry?.records.length) return "READY_WITH_GAPS";
  if (normalizeDataStatus(entry?.status) === "FAILED") return "FAILED";
  return "DATA_GAP";
}
export function shortenEvidence(value: string | undefined, max = 220): string {
  const text = (value ?? "").replace(/\s+/g, " ").trim();
  if (!text) return "No source summary was returned.";
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}
