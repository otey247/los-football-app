# Example: Weekly Waiver Report

Full-PPR, week 10. Trending adds filtered to players available in this league.

## Build steps
1. League context (rosters → `rosteredIds`).
2. `GET /players/nfl/trending/add?lookback_hours=24&limit=50`.
3. `filterTrendingAvailable({ trending, playersById, rosteredIds, positions: ["RB","WR"] })`.

## Output

# Sleeper Waiver-Wire Report

## League Context
Dynasty Degens — Week 10 · Full PPR · 1 QB

## Top Available Trending Adds
| Player | Pos | Team | Trend Count | Why It Matters | Recommendation |
|---|---|---|---:|---|---|
| Jaylen Wright | RB | MIA | 41,233 | Lead-back role after injury ahead | High — bid 35% FAAB |
| Demario Douglas | WR | NE | 18,902 | Target share climbing | Medium — speculative |

## Trending Drops to Watch
| Player | Pos | Team | Drop Count | Concern |
|---|---|---|---:|---|
| Gus Edwards | RB | LAC | 22,114 | Lost early-down work |

## Team-Specific Needs
- You're thin at RB after two byes — prioritize Wright.

## Cautions
- Trend count = market activity, not a projection.
- Availability inferred from current rosters (no free-agent endpoint).
