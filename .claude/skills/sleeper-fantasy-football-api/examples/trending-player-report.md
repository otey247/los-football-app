# Example: Trending Player Report

League-agnostic market snapshot, then filtered for one league's availability.

## Build steps
1. `GET /players/nfl/trending/add?lookback_hours=24&limit=25`
2. `GET /players/nfl/trending/drop?lookback_hours=24&limit=25`
3. Enrich with cached players; optionally cross-reference a league's rosters.

## Output

# Trending Player Report (last 24h)

## Trending Adds
| Player | Pos | Team | Status | Add Count |
|---|---|---|---|---:|
| Jaylen Wright | RB | MIA | Active | 41,233 |
| Demario Douglas | WR | NE | Active | 18,902 |
| ... | ... | ... | ... | ... |

## Trending Drops
| Player | Pos | Team | Status | Drop Count |
|---|---|---|---|---:|
| Gus Edwards | RB | LAC | Active | 22,114 |
| ... | ... | ... | ... | ... |

## League Availability (Dynasty Degens)
- Jaylen Wright: **available** → recommend
- Demario Douglas: already rostered

## Cautions
- Counts are market activity across all Sleeper leagues, not projections.
- Roster fit/scoring still decide whether an add is right for you.
