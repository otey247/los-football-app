# Example: League Dashboard

A weekly snapshot of a 12-team half-PPR redraft league.

## Build steps
1. `GET /state/nfl` → season `2025`, week `10`.
2. `GET /league/{id}`, `/users`, `/rosters`.
3. Player dictionary from daily cache.
4. `GET /league/{id}/matchups/10`; pair by `matchup_id`.

## Output

# Sleeper League Analysis

## League
Sunday Funday Dynasty — 2025, half-PPR, 12 teams

## Context
- Season: 2025 · Week: 10 · Status: in_season
- Scoring: half-PPR (rec 0.5), 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX
- Roster: 16 spots, 1 IR

## Standings
| Team | Owner | Record | PF | PA |
|---|---|---:|---:|---:|
| Gridiron Gurus | mike | 8-1 | 1184.6 | 968.2 |
| Air Raid | dana | 7-2 | 1142.0 | 1010.4 |
| ... | ... | ... | ... | ... |

## Week 10 Matchups
| Matchup | Team A | Pts | Team B | Pts | Winner |
|---|---|---:|---|---:|---|
| 1 | Gridiron Gurus | 132.4 | Bye Week Blues | 98.1 | Gridiron Gurus |
| ... | ... | ... | ... | ... | ... |

## Key Takeaways
- Gridiron Gurus clinch a playoff berth.
- Air Raid left 41 bench points (CeeDee Lamb benched).

## Recommended Actions
- Bye Week Blues: stream a QB; their starter is on bye.

## Data Notes
- Per-player points present → bench totals are exact.
