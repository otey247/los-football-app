# Waiver-Wire Analysis

## Inputs

League rosters, transactions for the week, trending adds/drops, and cached players.

## Availability is inferred

Sleeper's public API has **no** "free agents" endpoint. Derive availability by
subtracting all rostered player IDs from the player dictionary:

```ts
const rostered = getRosteredPlayerIds(rosters); // union of every roster.players
const isAvailable = (id) => !rostered.has(id);
```

## Trending, filtered to available

```ts
const adds = await client.getTrendingPlayers("add", 24, 50);
const candidates = filterTrendingAvailable({
  trending: adds, playersById, rosteredIds: rostered, positions: ["RB", "WR"],
});
```

> `count` from the trending endpoint is **market activity**, not a projection.
> Always contextualize it with: availability in this league, the asking team's
> need, scoring settings (PPR/superflex/TE-premium shift value), the player's
> role/depth-chart spot, and injury status.

## What to analyze

- Top available trending adds, with position/team/status and why they matter.
- Trending drops to watch (and whether they're already rostered here).
- Team-specific needs from roster construction vs `roster_positions`.
- Drop candidates on the asking roster (depth, bye, injury).
- FAAB context from transaction `waiver_budget`/`settings` when relevant.

## Output

Use `templates/waiver-report.md`. Never recommend a player without checking
availability in this specific league and applying its scoring. Label any
projection/news as coming from a separate source.
