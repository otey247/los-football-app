# Trade Analysis

## Inputs

Rosters, users, cached players, traded picks, league `scoring_settings` /
`roster_positions`, and transactions (for completed trades).

## What to analyze

- Each side's roster needs and positional depth.
- Age profile (critical in dynasty) and competitive window (contender vs rebuild).
- Draft-pick movement via `traded_picks` (see `dynasty-pick-tracking.md`).
- Scoring fit: a WR-heavy package is worth more in full PPR; a QB is worth far
  more in superflex/2QB; TEs gain value in TE-premium.

## Rules

- **Do not declare an objective trade winner** unless the valuation model and
  scoring context are explicit. State assumptions.
- Always anchor to league type: redraft vs keeper vs dynasty changes everything.
- If projections/rankings are needed for valuation, integrate and **label** a
  separate current source — the Sleeper API provides none.

## Output

Use `templates/trade-analysis.md`. Provide a recommendation
(accept / reject / counter / depends), a confidence level (High/Medium/Low), and
an explicit assumptions list. Show player and owner names, never raw IDs.
