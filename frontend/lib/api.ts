/**
 * Typed client for the CurricuAlign API.
 *
 * Response shapes are derived from lib/api-types.ts, which is generated from
 * the backend's OpenAPI schema. Regenerate after changing an endpoint:
 *
 *   npx openapi-typescript http://127.0.0.1:8000/openapi.json -o lib/api-types.ts
 */

import type { components } from "./api-types";

export type GapReport = components["schemas"]["GapReport"];
export type SkillGap = components["schemas"]["SkillGap"];
export type AugmentProposal = components["schemas"]["AugmentProposal"];
export type SkillTrend = components["schemas"]["SkillTrend"];
export type GapSeverity = components["schemas"]["GapSeverity"];

export interface CourseSummary {
  code: string;
  title: string;
  department: string;
  skills_taught: number;
  health_score: number | null;
  gap_count: number;
  critical_gaps: number;
}

export interface GraphNode {
  skill: string;
  category: string;
  demand: number;
  is_taught: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    skills: number;
    taught: number;
    gaps: number;
    edges: number;
  };
}

export interface MarketSummary {
  postings: number;
  skills_demanded: number;
  demands: number;
  earliest: string | null;
  latest: string | null;
}

export interface PrerequisiteChain {
  skill: string;
  total_prerequisites: number;
  max_depth: number;
  by_hop: { hops: number; prerequisites: string[] }[];
}

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Augmentation calls Claude, so the ceiling is generous but not infinite. */
const REQUEST_TIMEOUT_MS = 90_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Without an explicit timeout a blocked request hangs forever with no
  // error. A CORS mismatch did exactly that: the augmenter button sat on
  // "Generating..." indefinitely and the browser reported nothing.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw new ApiError(
        `Request timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`,
        408,
      );
    }
    throw new ApiError(
      `Could not reach the API at ${BASE_URL}. It may be down, or blocking this origin.`,
      0,
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Response body was not JSON. The status text is the best we have.
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  courses: () => request<CourseSummary[]>("/api/courses"),

  gaps: (courseCode: string) =>
    request<GapReport>(`/api/courses/${encodeURIComponent(courseCode)}/gaps`),

  augment: (courseCode: string) =>
    request<AugmentProposal>(
      `/api/augment/${encodeURIComponent(courseCode)}`,
      { method: "POST" },
    ),

  graph: (limit = 60) => request<GraphData>(`/api/graph?limit=${limit}`),

  prerequisites: (skill: string) =>
    request<PrerequisiteChain>(
      `/api/skills/${encodeURIComponent(skill)}/prerequisites`,
    ),

  trends: (limit = 20) =>
    request<SkillTrend[]>(`/api/market/trends?limit=${limit}`),

  marketSummary: () => request<MarketSummary>("/api/market/summary"),

  uploadSyllabus: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{
      course_code: string;
      title: string;
      characters_parsed: number;
    }>("/api/syllabi", { method: "POST", body });
  },
};

/** Health scores are the headline number, so their colour must be legible at a glance. */
export function healthTone(score: number | null): string {
  if (score === null) return "text-slate-400";
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-amber-400";
  return "text-rose-400";
}

export function severityTone(severity: string): {
  text: string;
  bg: string;
  border: string;
} {
  switch (severity) {
    case "critical":
      return {
        text: "text-rose-300",
        bg: "bg-rose-500/10",
        border: "border-rose-500/30",
      };
    case "high":
      return {
        text: "text-orange-300",
        bg: "bg-orange-500/10",
        border: "border-orange-500/30",
      };
    case "moderate":
      return {
        text: "text-amber-300",
        bg: "bg-amber-500/10",
        border: "border-amber-500/30",
      };
    default:
      return {
        text: "text-slate-300",
        bg: "bg-slate-500/10",
        border: "border-slate-500/30",
      };
  }
}
