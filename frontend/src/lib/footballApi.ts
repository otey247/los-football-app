import axios from "axios"
import { OpenAPI } from "@/client/core/OpenAPI"

// ---- Types ----------------------------------------------------------------

export interface SleeperStatMeta {
  key: string
  title: string
  description: string
  category: string
}

export interface SleeperLeagueInfo {
  league: Record<string, unknown>
  users: Record<string, unknown>[]
  rosters: Record<string, unknown>[]
  nfl_state: Record<string, unknown>
}

export interface BlogPost {
  id: string
  title: string
  slug: string
  content: string
  excerpt: string | null
  published: boolean
  created_at: string | null
  updated_at: string | null
  author_id: string
  author_name: string | null
}

export interface BlogPostSummary {
  id: string
  title: string
  slug: string
  excerpt: string | null
  published: boolean
  created_at: string | null
  updated_at: string | null
  author_id: string
  author_name: string | null
}

export interface BlogPostsPublic {
  data: BlogPost[]
  count: number
}

export interface BlogPostListPublic {
  data: BlogPostSummary[]
  count: number
}

export interface BlogPostCreate {
  title: string
  slug: string
  content: string
  excerpt?: string | null
  published: boolean
}

export interface BlogPostUpdate {
  title?: string | null
  slug?: string | null
  content?: string | null
  excerpt?: string | null
  published?: boolean | null
}

// ---- Helpers ---------------------------------------------------------------

function getBaseUrl(): string {
  return (OpenAPI.BASE as string) || ""
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const token =
    typeof OpenAPI.TOKEN === "function"
      ? await OpenAPI.TOKEN({} as never)
      : OpenAPI.TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ---- Sleeper API -----------------------------------------------------------

export const SleeperService = {
  async getStatsMeta(): Promise<SleeperStatMeta[]> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/sleeper/meta`)
    return res.data
  },

  async getLeagueInfo(leagueId?: string): Promise<SleeperLeagueInfo> {
    const params = leagueId ? { league_id: leagueId } : {}
    const res = await axios.get(`${getBaseUrl()}/api/v1/sleeper/league-info`, {
      params,
    })
    return res.data
  },

  async getStat(
    statKey: string,
    leagueId?: string,
    week?: number,
    startWeek?: number,
  ): Promise<unknown[]> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    if (startWeek) params.start_week = startWeek
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/sleeper/stats/${statKey}`,
      { params },
    )
    return res.data
  },

  // #75 Download a stat card/table as CSV or JSON.
  async exportStat(
    statKey: string,
    format: "csv" | "json",
    leagueId?: string,
    week?: number,
    startWeek?: number,
  ): Promise<void> {
    const params: Record<string, string | number> = { format }
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    if (startWeek) params.start_week = startWeek
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/sleeper/stats/${statKey}/export`,
      { params, responseType: "blob" },
    )
    const url = URL.createObjectURL(res.data as Blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `${statKey}.${format}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
}

// ---- Insights API ----------------------------------------------------------

export interface InsightsMeta {
  ai_enabled: boolean
  features: { key: string; title: string; description: string }[]
}

export interface WeeklyAward {
  award: string
  emoji: string
  team: string
  detail: string
}

export interface NarrativeResponse {
  week?: number
  through_week?: number
  ai_enabled: boolean
  // True only when Claude actually generated this narrative (not a fallback).
  ai_generated: boolean
  narrative: string
  facts?: Record<string, unknown>
  awards?: WeeklyAward[]
}

export interface Storyline {
  type: string
  emoji: string
  title: string
  detail: string
  teams: string[]
}

export interface AskResponse {
  question: string
  answer: string
  ai_enabled: boolean
  ai_generated: boolean
}

export interface PublishRecapResponse {
  id: string
  slug: string
  title: string
  published: boolean
}

export const InsightsService = {
  async getMeta(): Promise<InsightsMeta> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/insights/meta`)
    return res.data
  },

  async getWeeklyRecap(
    leagueId?: string,
    week?: number,
  ): Promise<NarrativeResponse> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/insights/weekly-recap`,
      {
        params,
      },
    )
    return res.data
  },

  async publishRecap(
    leagueId: string | undefined,
    week: number | undefined,
    publish: boolean,
  ): Promise<PublishRecapResponse> {
    const headers = await getAuthHeaders()
    const res = await axios.post(
      `${getBaseUrl()}/api/v1/insights/weekly-recap/publish`,
      { league_id: leagueId ?? "", week: week ?? null, publish },
      { headers },
    )
    return res.data
  },

  async getMatchupPreviews(
    leagueId?: string,
    week?: number,
  ): Promise<NarrativeResponse> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/insights/matchup-previews`,
      { params },
    )
    return res.data
  },

  async getWeeklyAwards(
    leagueId?: string,
    week?: number,
  ): Promise<NarrativeResponse> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/insights/weekly-awards`,
      { params },
    )
    return res.data
  },

  async getSeasonYearbook(leagueId?: string): Promise<NarrativeResponse> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/insights/season-yearbook`,
      { params },
    )
    return res.data
  },

  async getStorylines(
    leagueId?: string,
    week?: number,
  ): Promise<{ week: number; storylines: Storyline[] }> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    const res = await axios.get(`${getBaseUrl()}/api/v1/insights/storylines`, {
      params,
    })
    return res.data
  },

  async ask(question: string, leagueId?: string): Promise<AskResponse> {
    const res = await axios.post(`${getBaseUrl()}/api/v1/insights/ask`, {
      question,
      league_id: leagueId ?? "",
    })
    return res.data
  },
}

// ---- Reporting API ---------------------------------------------------------

export interface ReportingFeature {
  key: string
  title: string
  description: string
}

export interface ReportingMeta {
  emails_enabled: boolean
  features: ReportingFeature[]
}

export interface SeasonStanding {
  roster_id: number
  user_id: string
  name: string
  wins: number
  losses: number
  ties: number
  points_for: number
  points_against: number
  champion: boolean
}

export interface ArchivedSeason {
  league_id: string
  name: string | null
  season: string | null
  status: string | null
  total_rosters: number | null
  champion: string | null
  standings: SeasonStanding[]
}

export interface AllTimeRecord {
  user_id: string
  name: string
  seasons: number
  wins: number
  losses: number
  ties: number
  points_for: number
  championships: number
  best_season_points: number
}

export interface SeasonArchive {
  season_count: number
  seasons: ArchivedSeason[]
  all_time_records: AllTimeRecord[]
}

export interface ScoringHighlight {
  key: string
  label: string
  value: number
}

export interface ScoringSettings {
  league_id: string
  name: string | null
  season: string | null
  scoring_format: string
  starter_slots: number
  roster_composition: Record<string, number>
  scoring_highlights: ScoringHighlight[]
  scoring_settings: Record<string, number>
  roster_positions: string[]
}

export interface MultiLeagueRow {
  league_id: string
  name: string | null
  season: string | null
  total_rosters: number | null
  rank: number
  wins: number
  losses: number
  ties: number
  points_for: number
}

export interface MultiLeagueDashboard {
  username: string
  user_id?: string
  display_name?: string | null
  season: string
  leagues: MultiLeagueRow[]
  totals: {
    league_count: number
    wins: number
    losses: number
    ties: number
    points_for: number
    avg_rank: number | null
  }
}

export interface CacheStats {
  cache_entries: number
  max_cache_size: number
  hits: number
  misses: number
  errors: number
  total_lookups: number
  hit_rate_pct: number
  network_calls: number
  calls_last_minute: number
  rate_limit_per_minute: number
  rate_limit_used_pct: number
  rate_limit_headroom: number
}

export interface EndpointHealth {
  endpoint: string
  success_count: number
  error_count: number
  last_success_age_seconds: number | null
  last_error_age_seconds: number | null
  last_error_message: string | null
}

export interface HealthAlert {
  level: string
  endpoint: string
  message: string
}

export interface HealthReport {
  status: string
  season: string | null
  week: number | null
  season_type: string | null
  endpoints: EndpointHealth[]
  metrics: CacheStats
  alerts: HealthAlert[]
}

export interface BenchmarkMetric {
  key: string
  label: string
  team_value: number
  league_avg: number
  delta: number
  percentile: number
  higher_is_better: boolean
}

export interface Benchmark {
  roster_id: number
  name: string
  avatar: string | null
  through_week: number
  metrics: BenchmarkMetric[]
  historical_avg_points: number | null
  avg_points_vs_history: number | null
}

export interface CorrelationPair {
  x_key: string
  x_label: string
  y_key: string
  y_label: string
  correlation: number | null
  n: number
  strength: string | null
  direction: string | null
}

export interface CorrelationReport {
  through_week: number
  team_count: number
  pairs: CorrelationPair[]
}

export interface ScheduledReport {
  id: string
  name: string
  league_id: string
  stat_keys: string
  recipient_email: string
  frequency: string
  enabled: boolean
  last_sent_at: string | null
  created_at: string | null
  updated_at: string | null
  owner_id: string
}

export interface ScheduledReportsPublic {
  data: ScheduledReport[]
  count: number
}

export interface ScheduledReportCreate {
  name: string
  league_id: string
  stat_keys: string
  recipient_email: string
  frequency: string
  enabled: boolean
}

export interface UsageSummary {
  total_events: number
  rows: { event_type: string; target: string; count: number }[]
}

export const ReportingService = {
  async getMeta(): Promise<ReportingMeta> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/reporting/meta`)
    return res.data
  },

  async getSeasonArchive(leagueId?: string): Promise<SeasonArchive> {
    const params = leagueId ? { league_id: leagueId } : {}
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/reporting/season-archive`,
      { params },
    )
    return res.data
  },

  async getScoringSettings(leagueId?: string): Promise<ScoringSettings> {
    const params = leagueId ? { league_id: leagueId } : {}
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/reporting/scoring-settings`,
      { params },
    )
    return res.data
  },

  async getMultiLeague(
    username: string,
    season?: string,
  ): Promise<MultiLeagueDashboard> {
    const params: Record<string, string> = { username }
    if (season) params.season = season
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/reporting/multi-league`,
      { params },
    )
    return res.data
  },

  async getCacheStats(): Promise<CacheStats> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/reporting/cache-stats`)
    return res.data
  },

  async getHealth(): Promise<HealthReport> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/reporting/health`)
    return res.data
  },

  async getBenchmark(
    rosterId: number,
    leagueId?: string,
    week?: number,
    startWeek?: number,
  ): Promise<Benchmark> {
    const params: Record<string, string | number> = { roster_id: rosterId }
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    if (startWeek) params.start_week = startWeek
    const res = await axios.get(`${getBaseUrl()}/api/v1/reporting/benchmark`, {
      params,
    })
    return res.data
  },

  async getCorrelations(
    leagueId?: string,
    week?: number,
    startWeek?: number,
  ): Promise<CorrelationReport> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    if (startWeek) params.start_week = startWeek
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/reporting/correlations`,
      { params },
    )
    return res.data
  },

  // #79 Fire-and-forget product usage tracking.
  async recordUsage(
    eventType: string,
    target: string,
    path?: string,
  ): Promise<void> {
    try {
      const headers = await getAuthHeaders()
      if (!headers.Authorization) return
      await axios.post(
        `${getBaseUrl()}/api/v1/reporting/usage`,
        { event_type: eventType, target, path: path ?? null },
        { headers },
      )
    } catch {
      // Usage tracking must never disrupt the UX.
    }
  },

  async getUsageSummary(): Promise<UsageSummary> {
    const headers = await getAuthHeaders()
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/reporting/usage/summary`,
      { headers },
    )
    return res.data
  },

  async listReports(): Promise<ScheduledReportsPublic> {
    const headers = await getAuthHeaders()
    const res = await axios.get(`${getBaseUrl()}/api/v1/reporting/reports`, {
      headers,
    })
    return res.data
  },

  async createReport(data: ScheduledReportCreate): Promise<ScheduledReport> {
    const headers = await getAuthHeaders()
    const res = await axios.post(
      `${getBaseUrl()}/api/v1/reporting/reports`,
      data,
      { headers },
    )
    return res.data
  },

  async deleteReport(id: string): Promise<void> {
    const headers = await getAuthHeaders()
    await axios.delete(`${getBaseUrl()}/api/v1/reporting/reports/${id}`, {
      headers,
    })
  },

  async sendReport(
    id: string,
  ): Promise<{ sent: boolean; reason?: string; recipient?: string }> {
    const headers = await getAuthHeaders()
    const res = await axios.post(
      `${getBaseUrl()}/api/v1/reporting/reports/${id}/send`,
      {},
      { headers },
    )
    return res.data
  },
}

// ---- Blog API -------------------------------------------------------------

export const BlogService = {
  async getPosts(): Promise<BlogPostListPublic> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/blog/`)
    return res.data
  },

  async getAllPostsAdmin(): Promise<BlogPostsPublic> {
    const headers = await getAuthHeaders()
    const res = await axios.get(`${getBaseUrl()}/api/v1/blog/admin`, {
      headers,
    })
    return res.data
  },

  async getPost(id: string): Promise<BlogPost> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/blog/${id}`)
    return res.data
  },

  async createPost(data: BlogPostCreate): Promise<BlogPost> {
    const headers = await getAuthHeaders()
    const res = await axios.post(`${getBaseUrl()}/api/v1/blog/`, data, {
      headers,
    })
    return res.data
  },

  async updatePost(id: string, data: BlogPostUpdate): Promise<BlogPost> {
    const headers = await getAuthHeaders()
    const res = await axios.put(`${getBaseUrl()}/api/v1/blog/${id}`, data, {
      headers,
    })
    return res.data
  },

  async deletePost(id: string): Promise<void> {
    const headers = await getAuthHeaders()
    await axios.delete(`${getBaseUrl()}/api/v1/blog/${id}`, { headers })
  },
}
