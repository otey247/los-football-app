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
  ): Promise<unknown[]> {
    const params: Record<string, string | number> = {}
    if (leagueId) params.league_id = leagueId
    if (week) params.week = week
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/sleeper/stats/${statKey}`,
      { params },
    )
    return res.data
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
