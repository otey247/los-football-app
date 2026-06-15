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

// ---- Recommendations API ---------------------------------------------------

export interface CoachFeature {
  key: string
  title: string
  description: string
  per_team: boolean
}

export interface CoachTeam {
  roster_id: number
  display_name: string
  avatar: string | null
}

export interface StartSitCall {
  slot: string
  start: string
  start_proj: number
  sit: string
  sit_proj: number
  delta: number
  confidence: string
}

export interface StartSitResponse {
  roster_id: number
  team: string
  week: number
  projected_total: number
  starters: {
    slot: string
    player_id: string
    name: string
    position: string
    proj: number
    status: string | null
  }[]
  bench: {
    player_id: string
    name: string
    position: string
    proj: number
    status: string | null
  }[]
  calls: StartSitCall[]
  note: string
}

export interface WaiverSuggestion {
  player_id: string
  name: string
  position: string
  team: string | null
  status: string | null
  trending_adds: number
  recent_ppg: number
  fills_need: boolean
  score: number
}

export interface WaiverResponse {
  roster_id: number
  team: string
  week: number
  needs: { position: string; gap: number }[]
  suggestions: WaiverSuggestion[]
  drop_candidates: {
    player_id: string
    name: string
    position: string
    recent_ppg: number
    status: string | null
  }[]
  note: string
}

export interface TradeSuggestion {
  partner_roster_id: number
  partner: string
  acquire_position: string
  target_player: string
  target_ppg: number
  offer_position: string | null
  offer_player: string | null
  offer_ppg: number | null
  ppg_gap: number | null
}

export interface TradeResponse {
  roster_id: number
  team: string
  week: number
  needs: string[]
  surplus: string[]
  suggestions: TradeSuggestion[]
  note: string
}

export interface LineupNudge {
  roster_id: number
  team: string
  projected_total: number
  issues: string[]
}

export interface LineupNudgesResponse {
  week: number
  nudges: LineupNudge[]
  note: string
}

export interface RosGame {
  week: number
  opponent: string
  opponent_avg: number
  win_probability: number
  swing: boolean
}

export interface RosTeam {
  roster_id: number
  team: string
  avatar: string | null
  current_wins: number
  avg_points: number
  remaining_games: number
  strength_of_schedule: number
  sos_vs_league: number
  projected_added_wins: number
  projected_final_wins: number
  playoff_probability_pct: number
  schedule: RosGame[]
  swing_matchups: RosGame[]
}

export interface RosResponse {
  week: number
  teams: RosTeam[]
  note: string
}

export interface MustWinFlag {
  roster_id: number
  team: string
  week: number
  opponent: string
  playoff_probability_pct: number
  swing_pct: number
  level: string
}

export interface MustWinResponse {
  week: number
  flags: MustWinFlag[]
  note: string
}

export interface RegressionWarning {
  roster_id: number
  team: string
  avatar: string | null
  type: string
  emoji: string
  luck_delta: number
  actual_wins: number
  expected_wins: number
  all_play_win_pct: number
  detail: string
}

export interface RegressionResponse {
  week: number
  warnings: RegressionWarning[]
  note: string
}

export interface Rivalry {
  teams: string[]
  roster_ids: number[]
  meetings: number
  series: string
  avg_margin: number
  closest_margin: number
  rivalry_index: number
  grudge_match: boolean
  grudge_week: number | null
}

export interface RivalryResponse {
  week: number
  rivalries: Rivalry[]
  trash_talk: string
  ai_enabled: boolean
  ai_generated: boolean
}

export interface CommitteeRow {
  roster_id: number
  team: string
  avatar: string | null
  power_score: number
  all_play_win_pct: number
  record: string
  points_for: number
  model_rank: number
  crowd_rank: number | null
  crowd_avg_rank: number | null
  disagreement: number
  blended_rank: number
}

export interface CommitteeResponse {
  week: number
  voter_count: number
  has_votes: boolean
  rankings: CommitteeRow[]
  model: CommitteeRow[]
  note: string
}

function coachParams(
  leagueId?: string,
  week?: number,
  extra?: Record<string, string | number>,
): Record<string, string | number> {
  const params: Record<string, string | number> = { ...extra }
  if (leagueId) params.league_id = leagueId
  if (week) params.week = week
  return params
}

export const RecommendationsService = {
  async getMeta(): Promise<{ features: CoachFeature[] }> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/recommendations/meta`)
    return res.data
  },

  async getTeams(leagueId?: string): Promise<CoachTeam[]> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/teams`,
      {
        params: coachParams(leagueId),
      },
    )
    return res.data
  },

  async getStartSit(
    rosterId: number,
    leagueId?: string,
    week?: number,
  ): Promise<StartSitResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/start-sit`,
      { params: coachParams(leagueId, week, { roster_id: rosterId }) },
    )
    return res.data
  },

  async getWaivers(
    rosterId: number,
    leagueId?: string,
    week?: number,
  ): Promise<WaiverResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/waivers`,
      { params: coachParams(leagueId, week, { roster_id: rosterId }) },
    )
    return res.data
  },

  async getTradeTargets(
    rosterId: number,
    leagueId?: string,
    week?: number,
  ): Promise<TradeResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/trade-targets`,
      { params: coachParams(leagueId, week, { roster_id: rosterId }) },
    )
    return res.data
  },

  async getLineupNudges(
    leagueId?: string,
    week?: number,
  ): Promise<LineupNudgesResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/lineup-nudges`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async getRestOfSeason(
    leagueId?: string,
    week?: number,
  ): Promise<RosResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/rest-of-season`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async getMustWin(leagueId?: string, week?: number): Promise<MustWinResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/must-win`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async getRegression(
    leagueId?: string,
    week?: number,
  ): Promise<RegressionResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/regression`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async getRivalries(
    leagueId?: string,
    week?: number,
  ): Promise<RivalryResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/rivalries`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async getCommittee(
    leagueId?: string,
    week?: number,
  ): Promise<CommitteeResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/recommendations/committee`,
      { params: coachParams(leagueId, week) },
    )
    return res.data
  },

  async submitCommitteeVote(
    leagueId: string | undefined,
    week: number | undefined,
    rankings: { roster_id: number; rank: number }[],
  ): Promise<CommitteeResponse> {
    const headers = await getAuthHeaders()
    const res = await axios.post(
      `${getBaseUrl()}/api/v1/recommendations/committee/vote`,
      { league_id: leagueId ?? "", week: week ?? null, rankings },
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
