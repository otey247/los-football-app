// Normalized league context + small helpers shared by every analysis recipe.
// Build this once per request, then pass it everywhere instead of re-deriving maps.

export type SleeperLeagueContext = {
  league: any;
  users: any[];
  rosters: any[];
  playersById: Record<string, any>;
  usersById: Record<string, any>;
  rostersById: Record<number, any>;
  ownersByRosterId: Record<number, any>;
  currentState: any;
};

export function buildLeagueContext({
  league,
  users,
  rosters,
  playersById,
  currentState,
}: {
  league: any;
  users: any[];
  rosters: any[];
  playersById: Record<string, any>;
  currentState: any;
}): SleeperLeagueContext {
  const usersById = Object.fromEntries(users.map((u) => [u.user_id, u]));
  const rostersById = Object.fromEntries(rosters.map((r) => [r.roster_id, r]));
  const ownersByRosterId = Object.fromEntries(
    rosters.map((r) => [r.roster_id, usersById[r.owner_id] ?? null]),
  );

  return {
    league,
    users,
    rosters,
    playersById,
    usersById,
    rostersById,
    ownersByRosterId,
    currentState,
  };
}

// Always convert player IDs to names in user-facing output.
export function getPlayerDisplayName(
  playerId: string,
  playersById: Record<string, any>,
): string {
  const player = playersById[playerId];
  if (!player) return playerId; // cache miss — surface the raw id, flag staleness
  if (player.full_name) return player.full_name;
  const name = `${player.first_name ?? ""} ${player.last_name ?? ""}`.trim();
  return name || playerId;
}

// Sleeper returns one matchup row per roster; the two rows sharing a
// matchup_id are opponents.
export function pairMatchups(matchups: any[]) {
  const groups = new Map<number, any[]>();
  for (const m of matchups) {
    if (!groups.has(m.matchup_id)) groups.set(m.matchup_id, []);
    groups.get(m.matchup_id)!.push(m);
  }
  return [...groups.entries()].map(([matchupId, teams]) => ({ matchupId, teams }));
}

// Bench is derived: players that are not in the starters list.
export function getBenchPlayerIds(matchup: any): string[] {
  const starters = new Set(matchup.starters ?? []);
  return (matchup.players ?? []).filter((id: string) => !starters.has(id));
}

// Availability is inferred: a player is free if no roster lists them.
export function getRosteredPlayerIds(rosters: any[]): Set<string> {
  const ids = new Set<string>();
  for (const roster of rosters) {
    for (const id of roster.players ?? []) ids.add(id);
  }
  return ids;
}

export function filterTrendingAvailable({
  trending,
  playersById,
  rosteredIds,
  positions,
}: {
  trending: { player_id: string; count: number }[];
  playersById: Record<string, any>;
  rosteredIds: Set<string>;
  positions?: string[];
}) {
  return trending
    .filter((t) => !rosteredIds.has(t.player_id))
    .map((t) => ({
      playerId: t.player_id,
      count: t.count,
      player: playersById[t.player_id],
    }))
    .filter((item) => !positions?.length || positions.includes(item.player?.position));
}
