# Example: Dynasty Trade Analysis

Superflex dynasty. A win-now team trades youth + picks for a veteran QB.

## Build steps
1. League context + `scoring_settings` (confirm superflex via `roster_positions`).
2. `GET /league/{id}/traded_picks` for pick ownership.
3. Map roster_ids to owners; resolve player names from cache.

## Output

# Sleeper Trade Analysis

## League Context
- Scoring / Roster: Superflex, TE-premium, dynasty
- League type: dynasty

## Trade
| Side | Assets |
|---|---|
| Contenders (mike) | gets Joe Burrow |
| Rebuilders (dana) | gets 2026 1st, 2027 1st, Jaylen Wright |

## Team Context
| Team | Needs | Depth | Window |
|---|---|---|---|
| Contenders | QB2 for superflex | strong WR | win-now |
| Rebuilders | youth + picks | aging | rebuild |

## Analysis
- In superflex, an every-week QB1 is premium; Contenders fill a real hole.
- Rebuilders bank two firsts + a young RB — sound for their window.

## Recommendation
Depends — fair for both given opposite windows.

## Confidence
Medium

## Assumptions
- Valuation uses superflex dynasty ADP (external, labeled), not Sleeper data.
- Pick values assume mid-round 1sts.
