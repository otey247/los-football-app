"""Matchup & win-probability analytics for the Sleeper-powered app.

Implements the "Matchup & Win Probability" analytics pillar (TODO #59-#66):

- #59 Pre-game win probability model for each weekly matchup
- #60 Live in-game win probability that updates as scores come in
- #61 Projected vs actual score accuracy tracking over the season
- #62 Matchup "what-if" simulator (swap a starter, see projected delta)
- #63 Tiebreaker and clinch/elimination scenario calculator
- #64 Monte Carlo season simulation for projected final standings
- #65 Playoff probability % per team, updated weekly
- #66 Championship odds and projected bracket paths

The models are powered entirely by Sleeper's read-only API via the cached client
in ``app.services.sleeper``. Per-team scoring distributions (mean + standard
deviation of weekly points) are the backbone: a head-to-head win probability is
the normal CDF of the projected scoring margin, and the season simulation samples
those distributions across the *real* remaining schedule (future-week pairings
are available from the matchups endpoint before the games are played).
"""

import math
import random
from typing import Any

import httpx

from app.services import sleeper as svc
from app.services.sleeper import (
    _collect_all_matchups,
    _resolve_result,
    _roster_user_map,
    _team_week_table,
)

# Fallbacks used before a team has enough games to estimate from.
_DEFAULT_MEAN = 100.0
_DEFAULT_STD = 25.0
_MIN_STD = 12.0


# ---------------------------------------------------------------------------
# Probability helpers
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _win_probability(
    mean_a: float, std_a: float, mean_b: float, std_b: float
) -> float:
    """Probability team A outscores team B given independent normal scores."""
    denom = math.sqrt(std_a * std_a + std_b * std_b)
    if denom <= 0:
        return 0.5
    return _normal_cdf((mean_a - mean_b) / denom)


# ---------------------------------------------------------------------------
# Shared league context
# ---------------------------------------------------------------------------

def _team_strength(
    tw: list[dict[str, Any]], roster_ids: list[int]
) -> tuple[dict[int, float], dict[int, float]]:
    """Return (mean, std) of weekly points for each roster from played weeks."""
    scores: dict[int, list[float]] = {rid: [] for rid in roster_ids}
    for row in tw:
        scores.setdefault(row["roster_id"], []).append(row["points"])

    mean: dict[int, float] = {}
    std: dict[int, float] = {}
    for rid in roster_ids:
        pts = [p for p in scores.get(rid, []) if p > 0]
        if not pts:
            mean[rid] = _DEFAULT_MEAN
            std[rid] = _DEFAULT_STD
            continue
        m = sum(pts) / len(pts)
        mean[rid] = m
        if len(pts) > 1:
            var = sum((p - m) ** 2 for p in pts) / (len(pts) - 1)
            std[rid] = max(_MIN_STD, math.sqrt(var))
        else:
            std[rid] = _DEFAULT_STD
    return mean, std


def _standings(
    all_matchups: dict[int, list[dict[str, Any]]],
    tw: list[dict[str, Any]],
    roster_ids: list[int],
) -> dict[int, dict[str, float]]:
    """Current wins/losses/ties and points-for per roster from played weeks."""
    table: dict[int, dict[str, float]] = {
        rid: {"wins": 0.0, "losses": 0.0, "ties": 0.0, "points_for": 0.0}
        for rid in roster_ids
    }
    for week in all_matchups:
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            rid = row["roster_id"]
            if rid not in table:
                continue
            table[rid]["points_for"] += row["points"]
            result = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result == "W":
                table[rid]["wins"] += 1
            elif result == "L":
                table[rid]["losses"] += 1
            else:
                table[rid]["ties"] += 1
    return table


def _pair_week(matchups: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Group a week's matchup rows into (roster_a, roster_b) opponent pairs."""
    by_mid: dict[Any, list[int]] = {}
    for m in matchups:
        if m.get("roster_id") is None or m.get("matchup_id") is None:
            continue
        by_mid.setdefault(m["matchup_id"], []).append(int(m["roster_id"]))
    pairs: list[tuple[int, int]] = []
    for rids in by_mid.values():
        if len(rids) == 2:
            pairs.append((rids[0], rids[1]))
    return pairs


def _playoff_settings(league: dict[str, Any]) -> tuple[int, int]:
    """Return (playoff_week_start, playoff_teams) with sensible defaults."""
    settings = league.get("settings", {}) or {}
    playoff_start = int(settings.get("playoff_week_start", 15) or 15)
    playoff_teams = int(settings.get("playoff_teams", 6) or 6)
    return playoff_start, playoff_teams


def _remaining_schedule(
    league_id: str, current_week: int, playoff_start: int
) -> dict[int, list[tuple[int, int]]]:
    """Real remaining regular-season pairings for weeks after ``current_week``.

    Sleeper exposes future-week matchup pairings (with zero points) before the
    games are played, so the simulation can use the true schedule rather than
    random pairings.
    """
    remaining: dict[int, list[tuple[int, int]]] = {}
    for week in range(current_week + 1, playoff_start):
        try:
            pairs = _pair_week(svc.get_matchups(league_id, week))
        except httpx.HTTPError:
            pairs = []
        if pairs:
            remaining[week] = pairs
    return remaining


def _player_week_points(tw: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """player_id -> {week: points} from the team-week fact table."""
    out: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            out.setdefault(pid, {})[row["week"]] = float(pts)
    return out


def _name(rum: dict[int, dict[str, Any]], rid: int) -> dict[str, Any]:
    user = rum.get(rid, {})
    return {
        "roster_id": rid,
        "display_name": user.get("display_name", f"Team {rid}"),
        "avatar": user.get("avatar"),
    }


# ---------------------------------------------------------------------------
# #59 Pre-game win probability
# ---------------------------------------------------------------------------

def pregame_win_probability(
    league_id: str, week: int
) -> dict[str, Any]:
    """#59 Win probability for each matchup in ``week`` using team strengths."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    roster_ids = [int(r["roster_id"]) for r in rosters]

    # Strength is estimated from all completed weeks before the target week.
    history = _collect_all_matchups(league_id, max(week - 1, 0))
    tw = _team_week_table(history)
    mean, std = _team_strength(tw, roster_ids)

    try:
        week_matchups = svc.get_matchups(league_id, week)
    except httpx.HTTPError:
        week_matchups = []
    pairs = _pair_week(week_matchups)

    matchups: list[dict[str, Any]] = []
    for a, b in pairs:
        wp_a = _win_probability(mean[a], std[a], mean[b], std[b])
        spread = round(mean[a] - mean[b], 2)
        matchups.append({
            "matchup": [
                {
                    **_name(rum, a),
                    "projected_points": round(mean[a], 2),
                    "std": round(std[a], 2),
                    "win_probability": round(wp_a * 100, 1),
                },
                {
                    **_name(rum, b),
                    "projected_points": round(mean[b], 2),
                    "std": round(std[b], 2),
                    "win_probability": round((1 - wp_a) * 100, 1),
                },
            ],
            "favorite_roster_id": a if wp_a >= 0.5 else b,
            "spread": abs(spread),
        })
    matchups.sort(key=lambda m: max(
        m["matchup"][0]["win_probability"], m["matchup"][1]["win_probability"]
    ))
    return {"week": week, "matchups": matchups}


# ---------------------------------------------------------------------------
# #60 Live in-game win probability
# ---------------------------------------------------------------------------

def live_win_probability(
    league_id: str, week: int
) -> dict[str, Any]:
    """#60 Live win probability blending current points with projected rest.

    A starter still showing zero points is treated as "yet to play" and expected
    to add the team's average points-per-starter; remaining uncertainty shrinks
    as more of the lineup posts a score.
    """
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    roster_ids = [int(r["roster_id"]) for r in rosters]

    history = _collect_all_matchups(league_id, max(week - 1, 0))
    tw = _team_week_table(history)
    mean, std = _team_strength(tw, roster_ids)

    try:
        week_matchups = svc.get_matchups(league_id, week)
    except httpx.HTTPError:
        week_matchups = []
    rows = {int(m["roster_id"]): m for m in week_matchups if m.get("roster_id") is not None}
    pairs = _pair_week(week_matchups)

    def _projection(rid: int) -> tuple[float, float, float, int]:
        row = rows.get(rid, {})
        current = float(row.get("points") or 0)
        starters = row.get("starters") or []
        pp = row.get("players_points") or {}
        n_start = len(starters)
        yet_to_play = sum(1 for s in starters if float(pp.get(s, 0) or 0) == 0)
        per_slot = mean[rid] / n_start if n_start else 0.0
        remaining = per_slot * yet_to_play
        projected = current + remaining
        frac = (yet_to_play / n_start) if n_start else 1.0
        live_std = max(_MIN_STD * 0.5, std[rid] * math.sqrt(frac))
        return current, projected, live_std, yet_to_play

    matchups: list[dict[str, Any]] = []
    for a, b in pairs:
        cur_a, proj_a, std_a, ytp_a = _projection(a)
        cur_b, proj_b, std_b, ytp_b = _projection(b)
        wp_a = _win_probability(proj_a, std_a, proj_b, std_b)
        matchups.append({
            "matchup": [
                {
                    **_name(rum, a),
                    "current_points": round(cur_a, 2),
                    "projected_points": round(proj_a, 2),
                    "starters_yet_to_play": ytp_a,
                    "win_probability": round(wp_a * 100, 1),
                },
                {
                    **_name(rum, b),
                    "current_points": round(cur_b, 2),
                    "projected_points": round(proj_b, 2),
                    "starters_yet_to_play": ytp_b,
                    "win_probability": round((1 - wp_a) * 100, 1),
                },
            ],
        })
    return {"week": week, "matchups": matchups}


# ---------------------------------------------------------------------------
# #61 Projected vs actual accuracy
# ---------------------------------------------------------------------------

def projection_accuracy(
    league_id: str, current_week: int
) -> dict[str, Any]:
    """#61 Backtest projection accuracy week over week.

    For each completed week, the projection is each team's average score over the
    *prior* weeks; we compare that against the actual result and track absolute
    error, bias and how often the higher-projected team actually won.
    """
    rosters = svc.get_rosters(league_id)
    roster_ids = [int(r["roster_id"]) for r in rosters]
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    prior_scores: dict[int, list[float]] = {rid: [] for rid in roster_ids}
    by_week: list[dict[str, Any]] = []
    abs_errors: list[float] = []
    signed_errors: list[float] = []
    picks_correct = 0
    picks_total = 0

    for week in sorted(all_matchups):
        week_rows = [r for r in tw if r["week"] == week]
        proj = {
            rid: (sum(s) / len(s) if s else _DEFAULT_MEAN)
            for rid, s in prior_scores.items()
        }
        has_prior = any(prior_scores[rid] for rid in roster_ids)

        week_abs: list[float] = []
        if has_prior:
            for row in week_rows:
                rid = row["roster_id"]
                err = row["points"] - proj.get(rid, _DEFAULT_MEAN)
                abs_errors.append(abs(err))
                signed_errors.append(err)
                week_abs.append(abs(err))
            for a, b in _pair_week(all_matchups[week]):
                row_a = next((r for r in week_rows if r["roster_id"] == a), None)
                row_b = next((r for r in week_rows if r["roster_id"] == b), None)
                if not row_a or not row_b or row_a["points"] == row_b["points"]:
                    continue
                predicted = a if proj.get(a, 0) >= proj.get(b, 0) else b
                actual = a if row_a["points"] > row_b["points"] else b
                picks_total += 1
                if predicted == actual:
                    picks_correct += 1

            if week_abs:
                by_week.append({
                    "week": week,
                    "mae": round(sum(week_abs) / len(week_abs), 2),
                    "samples": len(week_abs),
                })

        # Roll this week's actuals into the history for the next projection.
        for row in week_rows:
            if row["points"] > 0:
                prior_scores.setdefault(row["roster_id"], []).append(row["points"])

    n = len(abs_errors)
    overall = {
        "mae": round(sum(abs_errors) / n, 2) if n else None,
        "rmse": round(math.sqrt(sum(e * e for e in signed_errors) / n), 2) if n else None,
        "bias": round(sum(signed_errors) / n, 2) if n else None,
        "pick_accuracy": round(picks_correct / picks_total * 100, 1) if picks_total else None,
        "picks_correct": picks_correct,
        "picks_total": picks_total,
        "scored_samples": n,
    }
    return {"through_week": current_week, "overall": overall, "by_week": by_week}


# ---------------------------------------------------------------------------
# #62 What-if simulator
# ---------------------------------------------------------------------------

def _player_projection(
    player_week_pts: dict[str, dict[int, float]], pid: str
) -> float:
    """A player's projected points = mean of their scored weeks."""
    weeks = [p for p in player_week_pts.get(pid, {}).values() if p != 0]
    if not weeks:
        return 0.0
    return sum(weeks) / len(weeks)


def lineup_options(
    league_id: str, roster_id: int, week: int
) -> dict[str, Any]:
    """#62 Starters and bench (with projections) for the what-if selector."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    players = svc.get_nfl_players()
    all_matchups = _collect_all_matchups(league_id, max(week - 1, 0))
    tw = _team_week_table(all_matchups)
    pwp = _player_week_points(tw)

    try:
        week_matchups = svc.get_matchups(league_id, week)
    except httpx.HTTPError:
        week_matchups = []
    row = next(
        (m for m in week_matchups if int(m.get("roster_id", -1)) == roster_id), None
    )
    if row is None:
        # Fall back to the season-long roster if the week has no matchup row yet.
        roster = next((r for r in rosters if int(r["roster_id"]) == roster_id), {})
        starters = roster.get("starters") or []
        all_players = roster.get("players") or []
    else:
        starters = row.get("starters") or []
        all_players = row.get("players") or []
    bench = [p for p in all_players if p not in starters]

    def _describe(pid: str) -> dict[str, Any]:
        info = players.get(pid, {})
        return {
            "player_id": pid,
            "name": info.get("full_name") or f"Player {pid}",
            "position": info.get("position"),
            "team": info.get("team"),
            "projected_points": round(_player_projection(pwp, pid), 2),
        }

    return {
        **_name(rum, roster_id),
        "week": week,
        "starters": [_describe(p) for p in starters if p],
        "bench": [_describe(p) for p in bench if p],
    }


def what_if(
    league_id: str,
    roster_id: int,
    week: int,
    swap_out: str,
    swap_in: str,
) -> dict[str, Any]:
    """#62 Project the point and win-probability delta from one lineup swap."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    players = svc.get_nfl_players()
    roster_ids = [int(r["roster_id"]) for r in rosters]
    history = _collect_all_matchups(league_id, max(week - 1, 0))
    tw = _team_week_table(history)
    pwp = _player_week_points(tw)
    _, std = _team_strength(tw, roster_ids)

    try:
        week_matchups = svc.get_matchups(league_id, week)
    except httpx.HTTPError:
        week_matchups = []
    rows = {int(m["roster_id"]): m for m in week_matchups if m.get("roster_id") is not None}
    row = rows.get(roster_id)
    if row is None:
        raise ValueError(f"No matchup found for roster {roster_id} in week {week}")
    starters = list(row.get("starters") or [])
    bench = [p for p in (row.get("players") or []) if p not in starters]

    if swap_out not in starters:
        raise ValueError("swap_out must be a current starter")
    if swap_in not in bench:
        raise ValueError("swap_in must be a current bench player")

    base_total = sum(_player_projection(pwp, p) for p in starters if p)
    new_total = base_total - _player_projection(pwp, swap_out) + _player_projection(pwp, swap_in)

    # Opponent projection for the win-probability comparison.
    opp_pairs = _pair_week(week_matchups)
    opponent = next(
        (b if a == roster_id else a for a, b in opp_pairs if roster_id in (a, b)),
        None,
    )
    result: dict[str, Any] = {
        **_name(rum, roster_id),
        "week": week,
        "swap_out": {
            "player_id": swap_out,
            "name": players.get(swap_out, {}).get("full_name") or f"Player {swap_out}",
            "projected_points": round(_player_projection(pwp, swap_out), 2),
        },
        "swap_in": {
            "player_id": swap_in,
            "name": players.get(swap_in, {}).get("full_name") or f"Player {swap_in}",
            "projected_points": round(_player_projection(pwp, swap_in), 2),
        },
        "current_projected_total": round(base_total, 2),
        "new_projected_total": round(new_total, 2),
        "delta": round(new_total - base_total, 2),
    }

    if opponent is not None:
        opp_row = rows.get(opponent, {})
        opp_starters = opp_row.get("starters") or []
        opp_total = sum(_player_projection(pwp, p) for p in opp_starters if p)
        std_self = std.get(roster_id, _DEFAULT_STD)
        std_opp = std.get(opponent, _DEFAULT_STD)
        wp_before = _win_probability(base_total, std_self, opp_total, std_opp)
        wp_after = _win_probability(new_total, std_self, opp_total, std_opp)
        result["opponent"] = {
            **_name(rum, opponent),
            "projected_points": round(opp_total, 2),
        }
        result["win_probability_before"] = round(wp_before * 100, 1)
        result["win_probability_after"] = round(wp_after * 100, 1)
        result["win_probability_delta"] = round((wp_after - wp_before) * 100, 1)
    return result


# ---------------------------------------------------------------------------
# Shared Monte Carlo season simulation (#64, #65, #66)
# ---------------------------------------------------------------------------

def _play_round(
    idxs: list[int], seeds: list[int], mean: dict[int, float], std: dict[int, float]
) -> list[int]:
    """Play one bracket round; ``idxs`` are seed indices (lower = better seed)."""
    ordered = sorted(idxs)
    winners: list[int] = []
    i, j = 0, len(ordered) - 1
    while i < j:
        ra, rb = seeds[ordered[i]], seeds[ordered[j]]
        sa = max(0.0, random.gauss(mean.get(ra, _DEFAULT_MEAN), std.get(ra, _DEFAULT_STD)))
        sb = max(0.0, random.gauss(mean.get(rb, _DEFAULT_MEAN), std.get(rb, _DEFAULT_STD)))
        winners.append(ordered[i] if sa >= sb else ordered[j])
        i += 1
        j -= 1
    if i == j:  # odd team out gets a bye into the next round
        winners.append(ordered[i])
    return winners


def _simulate_bracket(
    seeds: list[int], mean: dict[int, float], std: dict[int, float]
) -> tuple[int, int | None]:
    """Single-elimination re-seeded bracket; returns (champion, runner_up)."""
    n = len(seeds)
    if n == 0:
        return -1, None
    if n == 1:
        return seeds[0], None
    size = 1
    while size < n:
        size *= 2
    byes = size - n
    alive = list(range(n))
    bye_teams = alive[:byes]
    playing = alive[byes:]
    alive = sorted(bye_teams + (_play_round(playing, seeds, mean, std) if playing else []))

    runner_up: int | None = None
    while len(alive) > 1:
        if len(alive) == 2:
            a, b = alive
            ra, rb = seeds[a], seeds[b]
            sa = max(0.0, random.gauss(mean.get(ra, _DEFAULT_MEAN), std.get(ra, _DEFAULT_STD)))
            sb = max(0.0, random.gauss(mean.get(rb, _DEFAULT_MEAN), std.get(rb, _DEFAULT_STD)))
            winner, loser = (a, b) if sa >= sb else (b, a)
            runner_up = loser
            alive = [winner]
        else:
            alive = sorted(_play_round(alive, seeds, mean, std))
    return seeds[alive[0]], (seeds[runner_up] if runner_up is not None else None)


def _simulate_season(
    league_id: str,
    current_week: int,
    *,
    simulations: int = 2000,
    with_bracket: bool = False,
) -> dict[str, Any]:
    """Core Monte Carlo engine shared by #64, #65 and #66.

    Returns aggregate per-roster results: average final wins/points, playoff
    probability, the full final-seed distribution, and (optionally) championship
    and finals probabilities from a simulated playoff bracket.
    """
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    roster_ids = [int(r["roster_id"]) for r in rosters]
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    playoff_start, playoff_teams = _playoff_settings(league)
    playoff_teams = min(playoff_teams, len(roster_ids))
    mean, std = _team_strength(tw, roster_ids)
    standings = _standings(all_matchups, tw, roster_ids)
    remaining = _remaining_schedule(league_id, current_week, playoff_start)

    base_wins = {rid: standings[rid]["wins"] for rid in roster_ids}
    base_points = {rid: standings[rid]["points_for"] for rid in roster_ids}

    playoff_counts = dict.fromkeys(roster_ids, 0)
    champ_counts = dict.fromkeys(roster_ids, 0)
    finals_counts = dict.fromkeys(roster_ids, 0)
    seed_counts: dict[int, list[int]] = {rid: [0] * len(roster_ids) for rid in roster_ids}
    sum_wins = dict.fromkeys(roster_ids, 0.0)
    sum_points = dict.fromkeys(roster_ids, 0.0)

    sims = max(1, simulations)
    for _ in range(sims):
        wins = dict(base_wins)
        points = dict(base_points)
        for pairs in remaining.values():
            for a, b in pairs:
                sa = max(0.0, random.gauss(mean.get(a, _DEFAULT_MEAN), std.get(a, _DEFAULT_STD)))
                sb = max(0.0, random.gauss(mean.get(b, _DEFAULT_MEAN), std.get(b, _DEFAULT_STD)))
                points[a] += sa
                points[b] += sb
                if sa > sb:
                    wins[a] += 1
                elif sb > sa:
                    wins[b] += 1
                else:
                    winner = random.choice((a, b))
                    wins[winner] += 1
        order = sorted(roster_ids, key=lambda r: (wins[r], points[r]), reverse=True)
        for seed_idx, rid in enumerate(order):
            seed_counts[rid][seed_idx] += 1
            sum_wins[rid] += wins[rid]
            sum_points[rid] += points[rid]
        qualifiers = order[:playoff_teams]
        for rid in qualifiers:
            playoff_counts[rid] += 1
        if with_bracket and qualifiers:
            champ, runner = _simulate_bracket(qualifiers, mean, std)
            if champ in champ_counts:
                champ_counts[champ] += 1
                finals_counts[champ] += 1
            if runner is not None and runner in finals_counts:
                finals_counts[runner] += 1

    return {
        "playoff_start": playoff_start,
        "playoff_teams": playoff_teams,
        "roster_ids": roster_ids,
        "mean": mean,
        "std": std,
        "standings": standings,
        "remaining": remaining,
        "playoff_counts": playoff_counts,
        "champ_counts": champ_counts,
        "finals_counts": finals_counts,
        "seed_counts": seed_counts,
        "sum_wins": sum_wins,
        "sum_points": sum_points,
        "simulations": sims,
    }


# ---------------------------------------------------------------------------
# #64 Monte Carlo final standings
# ---------------------------------------------------------------------------

def season_simulation(
    league_id: str, current_week: int, simulations: int = 2000
) -> dict[str, Any]:
    """#64 Projected final standings from a Monte Carlo season simulation."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    sim = _simulate_season(league_id, current_week, simulations=simulations)
    sims = sim["simulations"]

    teams: list[dict[str, Any]] = []
    for rid in sim["roster_ids"]:
        st = sim["standings"][rid]
        seed_dist = sim["seed_counts"][rid]
        avg_seed = (
            sum((i + 1) * c for i, c in enumerate(seed_dist)) / sims
            if sims else 0.0
        )
        teams.append({
            **_name(rum, rid),
            "current_wins": int(st["wins"]),
            "current_losses": int(st["losses"]),
            "points_for": round(st["points_for"], 2),
            "projected_wins": round(sim["sum_wins"][rid] / sims, 1),
            "projected_points": round(sim["sum_points"][rid] / sims, 1),
            "playoff_probability": round(sim["playoff_counts"][rid] / sims * 100, 1),
            "avg_seed": round(avg_seed, 1),
            "seed_distribution": [round(c / sims * 100, 1) for c in seed_dist],
        })
    teams.sort(key=lambda t: t["projected_wins"], reverse=True)
    return {
        "through_week": current_week,
        "simulations": sims,
        "playoff_teams": sim["playoff_teams"],
        "teams": teams,
    }


# ---------------------------------------------------------------------------
# #65 Playoff probability (with weekly trend)
# ---------------------------------------------------------------------------

def playoff_odds(
    league_id: str,
    current_week: int,
    simulations: int = 2000,
    trend_simulations: int = 400,
) -> dict[str, Any]:
    """#65 Current playoff odds plus a week-by-week trend per team."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)

    sim = _simulate_season(league_id, current_week, simulations=simulations)
    sims = sim["simulations"]

    # Weekly trend: re-run a lighter simulation as of each completed week.
    trend: dict[int, dict[int, float]] = {rid: {} for rid in sim["roster_ids"]}
    for week in range(1, current_week + 1):
        snap = _simulate_season(league_id, week, simulations=trend_simulations)
        s_sims = snap["simulations"]
        for rid in snap["roster_ids"]:
            trend[rid][week] = round(snap["playoff_counts"][rid] / s_sims * 100, 1)

    teams: list[dict[str, Any]] = []
    for rid in sim["roster_ids"]:
        st = sim["standings"][rid]
        odds = round(sim["playoff_counts"][rid] / sims * 100, 1)
        history = [
            {"week": w, "playoff_probability": trend[rid][w]}
            for w in sorted(trend[rid])
        ]
        teams.append({
            **_name(rum, rid),
            "current_wins": int(st["wins"]),
            "current_losses": int(st["losses"]),
            "points_for": round(st["points_for"], 2),
            "playoff_probability": odds,
            "trend": history,
        })
    teams.sort(key=lambda t: t["playoff_probability"], reverse=True)
    return {
        "through_week": current_week,
        "simulations": sims,
        "playoff_teams": sim["playoff_teams"],
        "teams": teams,
    }


# ---------------------------------------------------------------------------
# #66 Championship odds & projected bracket
# ---------------------------------------------------------------------------

def championship_odds(
    league_id: str, current_week: int, simulations: int = 2000
) -> dict[str, Any]:
    """#66 Championship/finals odds plus a projected bracket from seeds."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)

    sim = _simulate_season(
        league_id, current_week, simulations=simulations, with_bracket=True
    )
    sims = sim["simulations"]
    mean, std = sim["mean"], sim["std"]

    teams: list[dict[str, Any]] = []
    for rid in sim["roster_ids"]:
        teams.append({
            **_name(rum, rid),
            "playoff_probability": round(sim["playoff_counts"][rid] / sims * 100, 1),
            "finals_probability": round(sim["finals_counts"][rid] / sims * 100, 1),
            "championship_probability": round(sim["champ_counts"][rid] / sims * 100, 1),
            "avg_seed": round(
                sum((i + 1) * c for i, c in enumerate(sim["seed_counts"][rid])) / sims, 1
            ) if sims else 0.0,
        })
    teams.sort(key=lambda t: t["championship_probability"], reverse=True)

    # Projected bracket: order teams by average simulated seed, then lay out a
    # re-seeded single-elimination bracket with the pre-game favorite per game.
    seeded = sorted(
        sim["roster_ids"],
        key=lambda r: sum((i + 1) * c for i, c in enumerate(sim["seed_counts"][r])),
    )[: sim["playoff_teams"]]

    bracket = _projected_bracket(seeded, mean, std, rum)
    return {
        "through_week": current_week,
        "simulations": sims,
        "playoff_teams": sim["playoff_teams"],
        "teams": teams,
        "projected_bracket": bracket,
    }


def _projected_bracket(
    seeded: list[int],
    mean: dict[int, float],
    std: dict[int, float],
    rum: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministic re-seeded bracket with the favored team per matchup."""
    rounds: list[dict[str, Any]] = []
    n = len(seeded)
    if n < 2:
        return rounds
    size = 1
    while size < n:
        size *= 2
    byes = size - n
    # seed index -> roster id
    seed_of = {rid: i + 1 for i, rid in enumerate(seeded)}

    alive = list(seeded)
    bye_teams = alive[:byes]
    playing = alive[byes:]

    def _matchup(a: int, b: int) -> dict[str, Any]:
        wp_a = _win_probability(mean[a], std[a], mean[b], std[b])
        favorite = a if wp_a >= 0.5 else b
        return {
            "high_seed": {**_name(rum, a), "seed": seed_of.get(a)},
            "low_seed": {**_name(rum, b), "seed": seed_of.get(b)},
            "favorite_roster_id": favorite,
            "favorite_win_probability": round(max(wp_a, 1 - wp_a) * 100, 1),
        }

    def _pair(teams: list[int]) -> tuple[list[dict[str, Any]], list[int]]:
        ordered = sorted(teams, key=lambda r: seed_of.get(r, 999))
        games: list[dict[str, Any]] = []
        winners: list[int] = []
        i, j = 0, len(ordered) - 1
        while i < j:
            a, b = ordered[i], ordered[j]
            games.append(_matchup(a, b))
            winners.append(a if mean[a] >= mean[b] else b)
            i += 1
            j -= 1
        if i == j:
            winners.append(ordered[i])
        return games, winners

    round_no = 1
    if playing:
        games, winners = _pair(playing)
        rounds.append({"round": round_no, "name": _round_name(size), "games": games})
        alive = sorted(bye_teams + winners, key=lambda r: seed_of.get(r, 999))
        round_no += 1
    else:
        alive = sorted(bye_teams, key=lambda r: seed_of.get(r, 999))

    while len(alive) > 1:
        games, winners = _pair(alive)
        rounds.append({"round": round_no, "name": _round_name(len(alive)), "games": games})
        alive = sorted(winners, key=lambda r: seed_of.get(r, 999))
        round_no += 1
    return rounds


def _round_name(n_teams: int) -> str:
    return {2: "Championship", 4: "Semifinals", 8: "Quarterfinals"}.get(
        n_teams, f"Round of {n_teams}"
    )


# ---------------------------------------------------------------------------
# #63 Tiebreaker / clinch / elimination scenarios
# ---------------------------------------------------------------------------

def clinch_scenarios(
    league_id: str, current_week: int
) -> dict[str, Any]:
    """#63 Clinch/elimination status, magic numbers and best/worst-case finishes."""
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = _roster_user_map(rosters, users)
    roster_ids = [int(r["roster_id"]) for r in rosters]
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    playoff_start, playoff_teams = _playoff_settings(league)
    playoff_teams = min(playoff_teams, len(roster_ids))
    standings = _standings(all_matchups, tw, roster_ids)
    remaining = _remaining_schedule(league_id, current_week, playoff_start)

    games_left = dict.fromkeys(roster_ids, 0)
    for pairs in remaining.values():
        for a, b in pairs:
            games_left[a] = games_left.get(a, 0) + 1
            games_left[b] = games_left.get(b, 0) + 1

    wins = {rid: standings[rid]["wins"] for rid in roster_ids}
    max_wins = {rid: wins[rid] + games_left[rid] for rid in roster_ids}

    def _status(rid: int, floor: float) -> str:
        # Clinched: fewer than playoff_teams other teams can reach this floor.
        threats = sum(1 for o in roster_ids if o != rid and max_wins[o] >= floor)
        if threats < playoff_teams:
            return "clinched"
        # Eliminated: at least playoff_teams teams are guaranteed above this team.
        locked_above = sum(
            1 for o in roster_ids if o != rid and wins[o] > max_wins[rid]
        )
        if locked_above >= playoff_teams:
            return "eliminated"
        return "in_contention"

    teams: list[dict[str, Any]] = []
    for rid in roster_ids:
        st = standings[rid]
        status = _status(rid, wins[rid])
        # Magic number: smallest extra wins that flip the team to "clinched".
        magic: int | None = None
        if status != "clinched":
            for extra in range(1, games_left[rid] + 1):
                if _status_with_floor(rid, wins[rid] + extra, roster_ids, max_wins, playoff_teams):
                    magic = extra
                    break
        teams.append({
            **_name(rum, rid),
            "wins": int(st["wins"]),
            "losses": int(st["losses"]),
            "ties": int(st["ties"]),
            "points_for": round(st["points_for"], 2),
            "games_remaining": games_left[rid],
            "max_possible_wins": int(max_wins[rid]),
            "status": status,
            "clinch_magic_number": magic,
        })
    teams.sort(key=lambda t: (t["wins"], t["points_for"]), reverse=True)
    return {
        "through_week": current_week,
        "playoff_teams": playoff_teams,
        "playoff_start": playoff_start,
        "teams": teams,
    }


def _status_with_floor(
    rid: int,
    floor: float,
    roster_ids: list[int],
    max_wins: dict[int, float],
    playoff_teams: int,
) -> bool:
    """True if a guaranteed win floor would clinch a playoff berth for ``rid``."""
    threats = sum(1 for o in roster_ids if o != rid and max_wins[o] >= floor)
    return threats < playoff_teams


# ---------------------------------------------------------------------------
# Feature metadata
# ---------------------------------------------------------------------------

FEATURES = [
    {"key": "win-probability", "title": "Pre-Game Win Probability", "description": "Model-based win odds for each of the week's matchups."},
    {"key": "live-win-probability", "title": "Live Win Probability", "description": "In-game odds that update as scores come in."},
    {"key": "projection-accuracy", "title": "Projection Accuracy", "description": "How close projections have tracked actual scores this season."},
    {"key": "what-if", "title": "What-If Simulator", "description": "Swap a starter and see the projected point and win-probability delta."},
    {"key": "clinch-scenarios", "title": "Clinch & Elimination", "description": "Tiebreaker, clinch, and elimination scenarios with magic numbers."},
    {"key": "season-simulation", "title": "Season Simulation", "description": "Monte Carlo projection of final regular-season standings."},
    {"key": "playoff-odds", "title": "Playoff Odds", "description": "Playoff probability per team, with a week-by-week trend."},
    {"key": "championship-odds", "title": "Championship Odds", "description": "Title odds and a projected playoff bracket."},
]
