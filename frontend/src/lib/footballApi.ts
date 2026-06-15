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

// ---- Matchup & Win Probability API ----------------------------------------

export interface MatchupFeature {
  key: string
  title: string
  description: string
}

export interface TeamRef {
  roster_id: number
  display_name: string
  avatar?: string | null
}

export interface WinProbTeam extends TeamRef {
  projected_points: number
  std?: number
  win_probability: number
}

export interface WinProbMatchup {
  matchup: WinProbTeam[]
  favorite_roster_id?: number
  spread?: number
}

export interface WinProbResponse {
  week: number
  matchups: WinProbMatchup[]
}

export interface LiveWinProbTeam extends TeamRef {
  current_points: number
  projected_points: number
  starters_yet_to_play: number
  win_probability: number
}

export interface LiveWinProbResponse {
  week: number
  matchups: { matchup: LiveWinProbTeam[] }[]
}

export interface ProjectionAccuracyResponse {
  through_week: number
  overall: {
    mae: number | null
    rmse: number | null
    bias: number | null
    pick_accuracy: number | null
    picks_correct: number
    picks_total: number
    scored_samples: number
  }
  by_week: { week: number; mae: number; samples: number }[]
}

export interface LineupPlayer {
  player_id: string
  name: string
  position?: string | null
  team?: string | null
  projected_points: number
}

export interface LineupOptionsResponse extends TeamRef {
  week: number
  starters: LineupPlayer[]
  bench: LineupPlayer[]
}

export interface WhatIfResponse extends TeamRef {
  week: number
  swap_out: { player_id: string; name: string; projected_points: number }
  swap_in: { player_id: string; name: string; projected_points: number }
  current_projected_total: number
  new_projected_total: number
  delta: number
  opponent?: TeamRef & { projected_points: number }
  win_probability_before?: number
  win_probability_after?: number
  win_probability_delta?: number
}

export interface ClinchTeam extends TeamRef {
  wins: number
  losses: number
  ties: number
  points_for: number
  games_remaining: number
  max_possible_wins: number
  status: "clinched" | "eliminated" | "in_contention"
  clinch_magic_number: number | null
}

export interface ClinchResponse {
  through_week: number
  playoff_teams: number
  playoff_start: number
  teams: ClinchTeam[]
}

export interface SeasonSimTeam extends TeamRef {
  current_wins: number
  current_losses: number
  points_for: number
  projected_wins: number
  projected_points: number
  playoff_probability: number
  avg_seed: number
  seed_distribution: number[]
}

export interface SeasonSimResponse {
  through_week: number
  simulations: number
  playoff_teams: number
  teams: SeasonSimTeam[]
}

export interface PlayoffOddsTeam extends TeamRef {
  current_wins: number
  current_losses: number
  points_for: number
  playoff_probability: number
  trend: { week: number; playoff_probability: number }[]
}

export interface PlayoffOddsResponse {
  through_week: number
  simulations: number
  playoff_teams: number
  teams: PlayoffOddsTeam[]
}

export interface ChampionshipTeam extends TeamRef {
  playoff_probability: number
  finals_probability: number
  championship_probability: number
  avg_seed: number
}

export interface BracketGame {
  high_seed: TeamRef & { seed: number | null }
  low_seed: TeamRef & { seed: number | null }
  favorite_roster_id: number
  favorite_win_probability: number
}

export interface BracketRound {
  round: number
  name: string
  games: BracketGame[]
}

export interface ChampionshipResponse {
  through_week: number
  simulations: number
  playoff_teams: number
  teams: ChampionshipTeam[]
  projected_bracket: BracketRound[]
}

function matchupParams(
  leagueId?: string,
  week?: number,
): Record<string, string | number> {
  const params: Record<string, string | number> = {}
  if (leagueId) params.league_id = leagueId
  if (week) params.week = week
  return params
}

export const MatchupService = {
  async getMeta(): Promise<{ features: MatchupFeature[] }> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/matchup/meta`)
    return res.data
  },

  async getWinProbability(
    leagueId?: string,
    week?: number,
  ): Promise<WinProbResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/win-probability`,
      { params: matchupParams(leagueId, week) },
    )
    return res.data
  },

  async getLiveWinProbability(
    leagueId?: string,
    week?: number,
  ): Promise<LiveWinProbResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/live-win-probability`,
      { params: matchupParams(leagueId, week) },
    )
    return res.data
  },

  async getProjectionAccuracy(
    leagueId?: string,
    week?: number,
  ): Promise<ProjectionAccuracyResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/projection-accuracy`,
      { params: matchupParams(leagueId, week) },
    )
    return res.data
  },

  async getLineupOptions(
    rosterId: number,
    leagueId?: string,
    week?: number,
  ): Promise<LineupOptionsResponse> {
    const params = { ...matchupParams(leagueId, week), roster_id: rosterId }
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/lineup-options`,
      { params },
    )
    return res.data
  },

  async postWhatIf(body: {
    leagueId?: string
    rosterId: number
    week?: number
    swapOut: string
    swapIn: string
  }): Promise<WhatIfResponse> {
    const res = await axios.post(`${getBaseUrl()}/api/v1/matchup/what-if`, {
      league_id: body.leagueId ?? "",
      roster_id: body.rosterId,
      week: body.week ?? null,
      swap_out: body.swapOut,
      swap_in: body.swapIn,
    })
    return res.data
  },

  async getClinchScenarios(
    leagueId?: string,
    week?: number,
  ): Promise<ClinchResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/clinch-scenarios`,
      { params: matchupParams(leagueId, week) },
    )
    return res.data
  },

  async getSeasonSimulation(
    leagueId?: string,
    week?: number,
  ): Promise<SeasonSimResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/season-simulation`,
      { params: matchupParams(leagueId, week) },
    )
    return res.data
  },

  async getPlayoffOdds(
    leagueId?: string,
    week?: number,
  ): Promise<PlayoffOddsResponse> {
    const res = await axios.get(`${getBaseUrl()}/api/v1/matchup/playoff-odds`, {
      params: matchupParams(leagueId, week),
    })
    return res.data
  },

  async getChampionshipOdds(
    leagueId?: string,
    week?: number,
  ): Promise<ChampionshipResponse> {
    const res = await axios.get(
      `${getBaseUrl()}/api/v1/matchup/championship-odds`,
      { params: matchupParams(leagueId, week) },
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
