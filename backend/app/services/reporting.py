"""Data, reporting & instrumentation layer for the league.

This service composes the read-only Sleeper data (via ``services.sleeper``) into
the higher-level reporting surfaces:

* season archive & cross-season records (walks ``previous_league_id``)
* a configurable scoring-settings reader
* a multi-league aggregate view for a single manager
* team benchmarking against league (and historical) averages
* a correlation explorer over team-level metrics

Cache/rate-limit and data-freshness instrumentation live in ``services.sleeper``
and are merely surfaced here for the dashboard.
"""

import math
from typing import Any

from app.services import sleeper as svc

# Cap how far back the previous_league_id chain is walked, to bound API calls.
_MAX_SEASONS = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _name(rum: dict[int, dict[str, Any]], rid: int) -> str:
    user = rum.get(rid, {})
    return user.get("display_name") or f"Team {rid}"


def _roster_points(roster: dict[str, Any]) -> float:
    """Combined fantasy points from a roster's ``settings`` block."""
    s = roster.get("settings") or {}
    return round(float(s.get("fpts", 0) or 0) + float(s.get("fpts_decimal", 0) or 0) / 100, 2)


def _roster_points_against(roster: dict[str, Any]) -> float:
    s = roster.get("settings") or {}
    return round(
        float(s.get("fpts_against", 0) or 0)
        + float(s.get("fpts_against_decimal", 0) or 0) / 100,
        2,
    )


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient, or ``None`` if undefined."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mx) ** 2 for x in xs)
    var_y = sum((y - my) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None
    return round(cov / denom, 3)


def _strength(corr: float) -> str:
    a = abs(corr)
    if a >= 0.7:
        return "strong"
    if a >= 0.4:
        return "moderate"
    if a >= 0.2:
        return "weak"
    return "negligible"


# ---------------------------------------------------------------------------
# #76 Historical season archive + cross-season records
# ---------------------------------------------------------------------------

def _champion_roster_id(league_id: str) -> int | None:
    """Winning roster_id from the league's playoff bracket, if decided."""
    try:
        bracket = svc.get_winners_bracket(league_id)
    except Exception:  # noqa: BLE001
        return None
    # The championship game carries p == 1; ``w`` is the winning roster_id.
    final = next((m for m in bracket if m.get("p") == 1), None)
    if final and final.get("w"):
        return int(final["w"])
    return None


def season_archive(league_id: str) -> dict[str, Any]:
    """Walk the previous_league_id chain into a per-season archive + records."""
    seasons: list[dict[str, Any]] = []
    # all-time records keyed by Sleeper user_id (stable across seasons).
    by_user: dict[str, dict[str, Any]] = {}

    current_id: str | None = league_id
    visited: set[str] = set()
    while current_id and current_id not in visited and len(seasons) < _MAX_SEASONS:
        visited.add(current_id)
        league = svc.get_league(current_id)
        rosters = svc.get_rosters(current_id)
        users = svc.get_users(current_id)
        rum = svc._roster_user_map(rosters, users)
        champ_rid = _champion_roster_id(current_id)

        standings: list[dict[str, Any]] = []
        for r in rosters:
            rid = int(r["roster_id"])
            s = r.get("settings") or {}
            wins = int(s.get("wins", 0) or 0)
            losses = int(s.get("losses", 0) or 0)
            ties = int(s.get("ties", 0) or 0)
            pf = _roster_points(r)
            user = rum.get(rid, {})
            uid = str(user.get("user_id") or f"roster-{rid}")
            is_champ = champ_rid is not None and rid == champ_rid
            standings.append(
                {
                    "roster_id": rid,
                    "user_id": uid,
                    "name": _name(rum, rid),
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "points_for": pf,
                    "points_against": _roster_points_against(r),
                    "champion": is_champ,
                }
            )

            agg = by_user.setdefault(
                uid,
                {
                    "user_id": uid,
                    "name": _name(rum, rid),
                    "seasons": 0,
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "points_for": 0.0,
                    "championships": 0,
                    "best_season_points": 0.0,
                },
            )
            agg["name"] = _name(rum, rid)
            agg["seasons"] += 1
            agg["wins"] += wins
            agg["losses"] += losses
            agg["ties"] += ties
            agg["points_for"] = round(agg["points_for"] + pf, 2)
            agg["best_season_points"] = round(max(agg["best_season_points"], pf), 2)
            if is_champ:
                agg["championships"] += 1

        standings.sort(key=lambda x: (x["wins"], x["points_for"]), reverse=True)
        seasons.append(
            {
                "league_id": current_id,
                "name": league.get("name"),
                "season": league.get("season"),
                "status": league.get("status"),
                "total_rosters": league.get("total_rosters"),
                "champion": next(
                    (s["name"] for s in standings if s["champion"]), None
                ),
                "standings": standings,
            }
        )
        current_id = league.get("previous_league_id") or None

    records = sorted(
        by_user.values(),
        key=lambda u: (u["championships"], u["wins"], u["points_for"]),
        reverse=True,
    )
    return {
        "season_count": len(seasons),
        "seasons": seasons,
        "all_time_records": records,
    }


# ---------------------------------------------------------------------------
# #80 Configurable scoring-settings reader
# ---------------------------------------------------------------------------

def scoring_settings_summary(league_id: str) -> dict[str, Any]:
    """Surface a league's scoring + roster rules so analytics respect them."""
    league = svc.get_league(league_id)
    scoring: dict[str, Any] = league.get("scoring_settings") or {}
    roster_positions: list[str] = league.get("roster_positions") or []

    rec = float(scoring.get("rec", 0) or 0)
    if rec >= 1.0:
        scoring_format = "PPR"
    elif rec >= 0.5:
        scoring_format = "Half-PPR"
    else:
        scoring_format = "Standard"

    # Roster composition (count each slot type, separating bench/IR).
    bench_slots = {"BN", "IR", "TAXI"}
    composition: dict[str, int] = {}
    starters = 0
    for pos in roster_positions:
        composition[pos] = composition.get(pos, 0) + 1
        if pos not in bench_slots:
            starters += 1

    highlight_keys = [
        ("pass_td", "Passing TD"),
        ("pass_yd", "Passing yard"),
        ("pass_int", "Interception"),
        ("rush_td", "Rushing TD"),
        ("rush_yd", "Rushing yard"),
        ("rec", "Reception"),
        ("rec_td", "Receiving TD"),
        ("rec_yd", "Receiving yard"),
        ("fum_lost", "Fumble lost"),
        ("bonus_rec_te", "TE reception bonus"),
    ]
    highlights = [
        {"key": key, "label": label, "value": float(scoring[key])}
        for key, label in highlight_keys
        if key in scoring
    ]

    return {
        "league_id": league_id,
        "name": league.get("name"),
        "season": league.get("season"),
        "scoring_format": scoring_format,
        "starter_slots": starters,
        "roster_composition": composition,
        "scoring_highlights": highlights,
        "scoring_settings": scoring,
        "roster_positions": roster_positions,
    }


# ---------------------------------------------------------------------------
# #81 Multi-league aggregate dashboard
# ---------------------------------------------------------------------------

def multi_league_dashboard(username: str, season: str) -> dict[str, Any]:
    """Aggregate a single manager's standing across all their leagues."""
    user = svc.get_user(username)
    if not user or not user.get("user_id"):
        return {"username": username, "season": season, "leagues": [], "totals": {}}
    user_id = str(user["user_id"])
    leagues = svc.get_user_leagues(user_id, season)

    rows: list[dict[str, Any]] = []
    tot_wins = tot_losses = tot_ties = 0
    tot_points = 0.0
    ranks: list[int] = []
    for league in leagues:
        lid = str(league.get("league_id"))
        try:
            rosters = svc.get_rosters(lid)
        except Exception:  # noqa: BLE001
            continue
        mine = next(
            (r for r in rosters if str(r.get("owner_id")) == user_id), None
        )
        if mine is None:
            continue
        # Rank by wins then points across the league.
        ordered = sorted(
            rosters,
            key=lambda r: (
                int((r.get("settings") or {}).get("wins", 0) or 0),
                _roster_points(r),
            ),
            reverse=True,
        )
        rank = next(
            (i + 1 for i, r in enumerate(ordered) if r is mine),
            len(ordered),
        )
        s = mine.get("settings") or {}
        wins = int(s.get("wins", 0) or 0)
        losses = int(s.get("losses", 0) or 0)
        ties = int(s.get("ties", 0) or 0)
        pf = _roster_points(mine)
        tot_wins += wins
        tot_losses += losses
        tot_ties += ties
        tot_points += pf
        ranks.append(rank)
        rows.append(
            {
                "league_id": lid,
                "name": league.get("name"),
                "season": league.get("season"),
                "total_rosters": league.get("total_rosters"),
                "rank": rank,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": pf,
            }
        )

    rows.sort(key=lambda r: r["rank"])
    totals = {
        "league_count": len(rows),
        "wins": tot_wins,
        "losses": tot_losses,
        "ties": tot_ties,
        "points_for": round(tot_points, 2),
        "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
    }
    return {
        "username": username,
        "user_id": user_id,
        "display_name": user.get("display_name"),
        "season": season,
        "leagues": rows,
        "totals": totals,
    }


# ---------------------------------------------------------------------------
# Shared team-level metric builder (benchmark + correlations)
# ---------------------------------------------------------------------------

def _team_metrics(league_id: str, through_week: int) -> list[dict[str, Any]]:
    """Per-team metric vectors used by benchmarking and correlation analysis."""
    all_matchups = svc._collect_all_matchups(league_id, through_week)
    tw = svc._team_week_table(all_matchups)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    n_teams = len(rosters)

    base: dict[int, dict[str, Any]] = {
        int(r["roster_id"]): {
            "roster_id": int(r["roster_id"]),
            "name": _name(rum, int(r["roster_id"])),
            "avatar": rum.get(int(r["roster_id"]), {}).get("avatar"),
            "games": 0,
            "total_points": 0.0,
            "optimal_points": 0.0,
            "wins": 0,
            "losses": 0,
            "bench_points_lost": 0.0,
            "_opp": [],
            "expected_wins": 0.0,
        }
        for r in rosters
    }

    for week in all_matchups:
        week_rows = [r for r in tw if r["week"] == week]
        ranked = sorted(week_rows, key=lambda x: x["points"])
        for rank, row in enumerate(ranked):
            rid = row["roster_id"]
            if rid in base:
                base[rid]["expected_wins"] += rank / max(n_teams - 1, 1)
        # opponents for points-against average
        by_mid: dict[Any, list[dict[str, Any]]] = {}
        for row in week_rows:
            if row["matchup_id"] is not None:
                by_mid.setdefault(row["matchup_id"], []).append(row)
        for pair in by_mid.values():
            if len(pair) == 2:
                a, b = pair
                if a["roster_id"] in base:
                    base[a["roster_id"]]["_opp"].append(b["points"])
                if b["roster_id"] in base:
                    base[b["roster_id"]]["_opp"].append(a["points"])
        for row in week_rows:
            rid = row["roster_id"]
            if rid not in base:
                continue
            base[rid]["games"] += 1
            base[rid]["total_points"] += row["points"]
            optimal = svc._optimal_score(
                row["starters"], row["players"], row["players_points"]
            )
            base[rid]["optimal_points"] += optimal
            base[rid]["bench_points_lost"] += max(0.0, optimal - row["points"])
            result = svc._resolve_result(
                rid, row["matchup_id"], row["points"], week_rows
            )
            if result == "W":
                base[rid]["wins"] += 1
            elif result == "L":
                base[rid]["losses"] += 1

    out: list[dict[str, Any]] = []
    for rid, d in base.items():
        games = d["games"] or 1
        opp = d.pop("_opp")
        out.append(
            {
                "roster_id": rid,
                "name": d["name"],
                "avatar": d["avatar"],
                "games": d["games"],
                "wins": d["wins"],
                "losses": d["losses"],
                "total_points": round(d["total_points"], 2),
                "avg_points": round(d["total_points"] / games, 2),
                "optimal_points": round(d["optimal_points"], 2),
                "manager_efficiency_pct": (
                    round(d["total_points"] / d["optimal_points"] * 100, 1)
                    if d["optimal_points"] > 0
                    else 0.0
                ),
                "bench_points_lost": round(d["bench_points_lost"], 2),
                "avg_opponent_points": round(sum(opp) / len(opp), 2) if opp else 0.0,
                "expected_wins": round(d["expected_wins"], 2),
            }
        )
    return out


# ---------------------------------------------------------------------------
# #84 Benchmarking against league (and historical) averages
# ---------------------------------------------------------------------------

_BENCHMARK_METRICS = [
    ("avg_points", "Avg points / week", True),
    ("total_points", "Total points", True),
    ("wins", "Wins", True),
    ("manager_efficiency_pct", "Manager efficiency %", True),
    ("bench_points_lost", "Bench points lost", False),
    ("avg_opponent_points", "Avg points against", False),
    ("expected_wins", "Expected wins", True),
]


def _historical_avg_points(league_id: str, user_id: str | None) -> float | None:
    """Average points-per-game for prior seasons (best-effort)."""
    if not user_id:
        return None
    try:
        archive = season_archive(league_id)
    except Exception:  # noqa: BLE001
        return None
    totals: list[float] = []
    for season in archive["seasons"][1:]:  # skip the current season
        for s in season["standings"]:
            if s["user_id"] == user_id:
                games = (s["wins"] + s["losses"] + s["ties"]) or 1
                totals.append(s["points_for"] / games)
    if not totals:
        return None
    return round(sum(totals) / len(totals), 2)


def benchmark(league_id: str, roster_id: int, through_week: int) -> dict[str, Any]:
    """Benchmark one team's metrics against the league average + percentile."""
    metrics = _team_metrics(league_id, through_week)
    target = next((m for m in metrics if m["roster_id"] == roster_id), None)
    if target is None:
        raise ValueError(f"roster_id {roster_id} not found in league")

    rows: list[dict[str, Any]] = []
    for key, label, higher_is_better in _BENCHMARK_METRICS:
        values = [float(m[key]) for m in metrics]
        league_avg = round(sum(values) / len(values), 2) if values else 0.0
        team_val = float(target[key])
        # Percentile = share of teams this team is at-or-better than.
        if higher_is_better:
            better_or_equal = sum(1 for v in values if team_val >= v)
        else:
            better_or_equal = sum(1 for v in values if team_val <= v)
        percentile = round(better_or_equal / len(values) * 100) if values else 0
        rows.append(
            {
                "key": key,
                "label": label,
                "team_value": round(team_val, 2),
                "league_avg": league_avg,
                "delta": round(team_val - league_avg, 2),
                "percentile": percentile,
                "higher_is_better": higher_is_better,
            }
        )

    # Historical comparison for the headline avg-points metric.
    users = svc.get_users(league_id)
    rosters = svc.get_rosters(league_id)
    rum = svc._roster_user_map(rosters, users)
    uid = str(rum.get(roster_id, {}).get("user_id") or "")
    historical_avg = _historical_avg_points(league_id, uid or None)

    return {
        "roster_id": roster_id,
        "name": target["name"],
        "avatar": target["avatar"],
        "through_week": through_week,
        "metrics": rows,
        "historical_avg_points": historical_avg,
        "avg_points_vs_history": (
            round(target["avg_points"] - historical_avg, 2)
            if historical_avg is not None
            else None
        ),
    }


# ---------------------------------------------------------------------------
# #85 Correlation explorer
# ---------------------------------------------------------------------------

_CORRELATION_PAIRS = [
    ("bench_points_lost", "Bench points lost", "wins", "Wins"),
    ("manager_efficiency_pct", "Manager efficiency %", "wins", "Wins"),
    ("avg_points", "Avg points / week", "wins", "Wins"),
    ("avg_opponent_points", "Avg points against", "wins", "Wins"),
    ("avg_points", "Avg points / week", "expected_wins", "Expected wins"),
    ("manager_efficiency_pct", "Manager efficiency %", "avg_points", "Avg points / week"),
]


def correlations(league_id: str, through_week: int) -> dict[str, Any]:
    """Pearson correlations between team-level metrics across the league."""
    metrics = _team_metrics(league_id, through_week)
    pairs: list[dict[str, Any]] = []
    for x_key, x_label, y_key, y_label in _CORRELATION_PAIRS:
        xs = [float(m[x_key]) for m in metrics]
        ys = [float(m[y_key]) for m in metrics]
        corr = _pearson(xs, ys)
        pairs.append(
            {
                "x_key": x_key,
                "x_label": x_label,
                "y_key": y_key,
                "y_label": y_label,
                "correlation": corr,
                "n": len(metrics),
                "strength": _strength(corr) if corr is not None else None,
                "direction": (
                    None
                    if corr is None
                    else "positive"
                    if corr > 0
                    else "negative"
                    if corr < 0
                    else "none"
                ),
            }
        )
    pairs.sort(
        key=lambda p: abs(p["correlation"]) if p["correlation"] is not None else -1,
        reverse=True,
    )
    return {"through_week": through_week, "team_count": len(metrics), "pairs": pairs}
