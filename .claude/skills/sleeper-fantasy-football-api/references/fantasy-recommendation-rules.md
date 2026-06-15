# Fantasy Recommendation Rules

Recommendations must be **league-aware**. When a league is provided, read its
settings before recommending anything.

## Read from `scoring_settings` / `settings` / `roster_positions`

- PPR / half-PPR / standard (`rec` value) — drives RB/WR/TE flex value.
- Superflex / 2QB (a `QB`/`SUPER_FLEX` slot in `roster_positions`) — QBs jump in value.
- TE premium (elevated `rec_te` / `bonus_rec_te`) — boosts pass-catching TEs.
- Passing TD value (`pass_td`), turnover penalties (`int`, `fum_lost`).
- Yardage bonuses, big-play bonuses.
- IDP scoring (defensive player slots and stats).
- Kicker / team-defense settings.
- Taxi / reserve (IR) slots — affects roster flexibility and stash value.

## How settings change advice

| Setting | Effect |
|---|---|
| Full PPR | Volume pass-catchers (RB/WR) rise; TD-dependent backs fall |
| Superflex / 2QB | QBs become premium; a backup QB has real value |
| TE premium | Target-earning TEs rise sharply |
| Dynasty | Age and draft capital dominate; win-now vs rebuild matters |
| IDP | Defensive players need their own ranking lens |

## Discipline

- Don't make generic recommendations when a league is provided — apply its scoring.
- Trending adds reflect market activity, not projection quality.
- Don't overstate certainty; give a confidence level and assumptions.
- Don't claim real-time injury/projection/depth-chart/betting data unless it comes
  from a separate, current source — and label that source.
