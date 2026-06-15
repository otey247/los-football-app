// Minimal, read-only client for the Sleeper Fantasy Football API.
//
// The public API requires no authentication. Keep `players/nfl` calls to once
// per day and stay under ~1,000 requests/minute. This client adds timeouts and
// abort handling; layer caching on top (see references/player-cache-strategy.md).

type Params = Record<string, string | number>;

type SleeperClientOptions = {
  baseUrl?: string;
  timeoutMs?: number;
};

export class SleeperClient {
  private baseUrl: string;
  private timeoutMs: number;

  constructor(options: SleeperClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? "https://api.sleeper.app/v1";
    this.timeoutMs = options.timeoutMs ?? 20_000;
  }

  private async get<T>(path: string, params?: Params): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        url.searchParams.set(key, String(value));
      }
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(
          `Sleeper API error ${response.status}: ${await response.text()}`,
        );
      }
      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }

  // Users & leagues
  getUser(usernameOrUserId: string) {
    return this.get(`/user/${usernameOrUserId}`);
  }
  getUserLeagues(userId: string, season: string, sport = "nfl") {
    return this.get(`/user/${userId}/leagues/${sport}/${season}`);
  }
  getLeague(leagueId: string) {
    return this.get(`/league/${leagueId}`);
  }
  getRosters(leagueId: string) {
    return this.get(`/league/${leagueId}/rosters`);
  }
  getLeagueUsers(leagueId: string) {
    return this.get(`/league/${leagueId}/users`);
  }

  // Matchups, transactions, picks, brackets
  getMatchups(leagueId: string, week: number) {
    return this.get(`/league/${leagueId}/matchups/${week}`);
  }
  getTransactions(leagueId: string, week: number) {
    return this.get(`/league/${leagueId}/transactions/${week}`);
  }
  getTradedPicks(leagueId: string) {
    return this.get(`/league/${leagueId}/traded_picks`);
  }
  getWinnersBracket(leagueId: string) {
    return this.get(`/league/${leagueId}/winners_bracket`);
  }
  getLosersBracket(leagueId: string) {
    return this.get(`/league/${leagueId}/losers_bracket`);
  }

  // State & drafts
  getNflState() {
    return this.get(`/state/nfl`);
  }
  getLeagueDrafts(leagueId: string) {
    return this.get(`/league/${leagueId}/drafts`);
  }
  getDraft(draftId: string) {
    return this.get(`/draft/${draftId}`);
  }
  getDraftPicks(draftId: string) {
    return this.get(`/draft/${draftId}/picks`);
  }
  getDraftTradedPicks(draftId: string) {
    return this.get(`/draft/${draftId}/traded_picks`);
  }

  // Players — getPlayers is large; cache daily.
  getPlayers(sport = "nfl") {
    return this.get(`/players/${sport}`);
  }
  getTrendingPlayers(
    type: "add" | "drop",
    lookbackHours = 24,
    limit = 25,
    sport = "nfl",
  ) {
    return this.get(`/players/${sport}/trending/${type}`, {
      lookback_hours: lookbackHours,
      limit,
    });
  }
}
