export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(body.error?.message || "服务暂不可用，请检查后端连接");
  return body.data as T;
}
export type Competition = {
  id: string;
  name: string;
  edition: string | null;
  category: string | null;
  description: string | null;
  organizer: string | null;
  eligible_grades: string | null;
  eligible_majors: string | null;
  participation_type: string | null;
  team_size: string | null;
  registration_start: string | null;
  registration_deadline: string | null;
  registration_status: string;
  verification_status: string;
  last_verified_at: string;
  recommendation_reason: string;
  official_url: string | null;
  source_urls: string[];
  sources: {
    url: string;
    title: string;
    source_type: string;
    excerpt: string;
  }[];
  conflicts: string[];
  match_count: number;
  eligibility_match: string;
};
export type Event = {
  id: number;
  type: string;
  message: string;
  created_at: string;
  payload: {
    stage?: number;
    url?: string;
    title?: string;
    image?: string;
    step?: number;
  };
};
export type Task = {
  id: string;
  query: string;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
  result_count: number;
  results: Competition[];
  events: Event[];
  stats: {
    visited: number;
    candidates: number;
    verified: number;
    pending: number;
  };
};
export type Settings = {
  llm_provider: string;
  model: string;
  api_base_url: string;
  api_key_configured: boolean;
  max_steps: number;
  timeout_seconds: number;
  max_pages: number;
  default_count: number;
  headless: boolean;
  browser_mode: string;
};
