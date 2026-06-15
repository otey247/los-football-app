"""Sleeper Fantasy Football API service with in-memory caching."""

import time
from collections import OrderedDict
from typing import Any

import httpx

SLEEPER_BASE_URL = "https://api.sleeper.app/v1"
# Cache TTL in seconds: player list gets a long TTL; matchups/rosters get shorter ones
_CACHE: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_PLAYERS_TTL = 3600  # 1 hour – Sleeper recommends calling /players sparingly
_DEFAULT_TTL = 300   # 5 minutes
_MAX_CACHE_SIZE = 1024


def _purge_expired(now: float) -> None:
    """Remove expired cache entries."""
    expired_urls = [
        cached_url
        for cached_url, (expires_at, _) in _CACHE.items()
        if expires_at <= now
    ]
    for cached_url in expired_urls:
        _CACHE.pop(cached_url, None)


def _get(url: str, ttl: int = _DEFAULT_TTL) -> Any:
    """Fetch *url* from Sleeper API, returning a cached response when fresh."""
    now = time.monotonic()
    _purge_expired(now)

    if url in _CACHE:
        expires_at, data = _CACHE[url]
        if now < expires_at:
            _CACHE.move_to_end(url)
            return data
        _CACHE.pop(url, None)

    with httpx.Client(timeout=15) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    _CACHE[url] = (now + ttl, data)
    _CACHE.move_to_end(url)
    if len(_CACHE) > _MAX_CACHE_SIZE:
        _CACHE.popitem(last=False)
    return data


# ---------------------------------------------------------------------------
# Low-level API helpers
# ---------------------------------------------------------------------------

def get_league(league_id: str) -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}")


def get_users(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/users")


def get_rosters(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/rosters")


def get_matchups(league_id: str, week: int) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/matchups/{week}")


def get_transactions(league_id: str, week: int) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/transactions/{week}")


def get_drafts(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/drafts")


def get_draft_picks(draft_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/draft/{draft_id}/picks")


def get_traded_picks(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/traded_picks")


def get_winners_bracket(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/winners_bracket")


def get_losers_bracket(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/losers_bracket")


def get_nfl_players() -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/players/nfl", ttl=_PLAYERS_TTL)


def get_player_stats(season: str, week: int, season_type: str = "regular") -> dict[str, Any]:
    return _get(
        f"{SLEEPER_BASE_URL}/stats/nfl/player/{season_type}/{season}/{week}",
        ttl=_DEFAULT_TTL,
    )


def get_nfl_state() -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/state/nfl", ttl=60)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _build_user_map(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map roster_id -> user info for a league (users list contains roster_id)."""
    return {str(u["user_id"]): u for u in users}


def _roster_user_map(
    rosters: list[dict[str, Any]], users: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    """Map roster_id (int) -> user info."""
    uid_to_user = {str(u["user_id"]): u for u in users}
    result: dict[int, dict[str, Any]] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        uid = str(r["owner_id"]) if r.get("owner_id") else None
        result[rid] = uid_to_user.get(uid, {"display_name": f"Team {rid}", "user_id": uid})
    return result


# ---------------------------------------------------------------------------
# Stats calculators
# ---------------------------------------------------------------------------

def _collect_all_matchups(
    league_id: str, current_week: int
) -> dict[int, list[dict[str, Any]]]:
    """Return {week: [matchup_row, ...]} for weeks 1..current_week."""
    all_matchups: dict[int, list[dict[str, Any]]] = {}
    for w in range(1, current_week + 1):
        try:
            all_matchups[w] = get_matchups(league_id, w)
        except httpx.HTTPError:
            pass
    return all_matchups


def _team_week_table(
    all_matchups: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """
    Build a flat team-week fact table from raw matchup data.

    Each row: {week, roster_id, matchup_id, points, starters, players}
    """
    rows: list[dict[str, Any]] = []
    for week, week_matchups in all_matchups.items():
        for m in week_matchups:
            if m.get("roster_id") is None:
                continue
            rows.append(
                {
                    "week": week,
                    "roster_id": int(m["roster_id"]),
                    "matchup_id": m.get("matchup_id"),
                    "points": float(m.get("points") or 0),
                    "starters": m.get("starters") or [],
                    "players": m.get("players") or [],
                    "starters_points": m.get("starters_points") or [],
                    "players_points": m.get("players_points") or {},
                }
            )
    return rows


def _resolve_result(
    roster_id: int,
    matchup_id: int | None,
    points: float,
    week_rows: list[dict[str, Any]],
) -> str:
    """Return 'W', 'L', or 'T' for a team in a given week."""
    if matchup_id is None:
        return "T"
    opponent = next(
        (
            r
            for r in week_rows
            if r["matchup_id"] == matchup_id and r["roster_id"] != roster_id
        ),
        None,
    )
    if opponent is None:
        return "T"
    opp_pts = opponent["points"]
    if points > opp_pts:
        return "W"
    if points < opp_pts:
        return "L"
    return "T"


# ---------------------------------------------------------------------------
# Public stat functions (each returns a JSON-serialisable payload)
# ---------------------------------------------------------------------------

def stat_all_play_record(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#1 All-Play Record – virtual W/L against every opponent each week."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    totals: dict[int, dict[str, Any]] = {}
    for rid in rum:
        totals[rid] = {"roster_id": rid, "all_play_wins": 0, "all_play_losses": 0, "all_play_ties": 0}

    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        scores = [(r["roster_id"], r["points"]) for r in week_rows]
        for rid, pts in scores:
            for opp_rid, opp_pts in scores:
                if opp_rid == rid:
                    continue
                if pts > opp_pts:
                    totals[rid]["all_play_wins"] += 1
                elif pts < opp_pts:
                    totals[rid]["all_play_losses"] += 1
                else:
                    totals[rid]["all_play_ties"] += 1

    result = []
    for rid, data in sorted(totals.items(), key=lambda x: x[1]["all_play_wins"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            **data,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_expected_wins(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#2 Expected Wins – wins based on weekly score rank."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    n_teams = len(rosters)

    expected: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for week in all_matchups:
        week_rows = sorted(
            [r for r in tw if r["week"] == week],
            key=lambda x: x["points"],
        )
        for rank, row in enumerate(week_rows):
            expected[row["roster_id"]] += rank / max(n_teams - 1, 1)

    result = []
    for rid, exp in sorted(expected.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "expected_wins": round(exp, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_luck_adjusted_standings(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#3 Luck-Adjusted Standings – actual wins vs expected wins."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    n_teams = len(rosters)

    actual_wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    expected: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        sorted_rows = sorted(week_rows, key=lambda x: x["points"])
        for rank, row in enumerate(sorted_rows):
            expected[row["roster_id"]] += rank / max(n_teams - 1, 1)
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                actual_wins[row["roster_id"]] += 1

    result = []
    for rid in actual_wins:
        user = rum.get(rid, {})
        luck = round(actual_wins[rid] - expected[rid], 2)
        result.append({
            "roster_id": rid,
            "actual_wins": actual_wins[rid],
            "expected_wins": round(expected[rid], 2),
            "luck_delta": luck,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["luck_delta"], reverse=True)
    return result


def stat_schedule_luck_index(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#4 Schedule Luck Index – average points scored against each team."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    opp_totals: dict[int, list[float]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        mid_map: dict[int, list[dict[str, Any]]] = {}
        for row in week_rows:
            mid = row["matchup_id"]
            if mid is None:
                continue
            mid_map.setdefault(mid, []).append(row)
        for _mid, pair in mid_map.items():
            if len(pair) == 2:
                opp_totals[pair[0]["roster_id"]].append(pair[1]["points"])
                opp_totals[pair[1]["roster_id"]].append(pair[0]["points"])

    result = []
    for rid, opp_scores in opp_totals.items():
        user = rum.get(rid, {})
        avg_opp = round(sum(opp_scores) / len(opp_scores), 2) if opp_scores else 0.0
        result.append({
            "roster_id": rid,
            "avg_opponent_score": avg_opp,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["avg_opponent_score"], reverse=True)
    return result


def stat_bad_beat_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#5 Bad Beats – losses where team scored in the top half of the league."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    bad_beats: dict[int, list[dict[str, Any]]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        n = len(week_rows)
        median = sorted(week_rows, key=lambda x: x["points"])[n // 2]["points"] if n else 0
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "L" and row["points"] >= median:
                bad_beats[row["roster_id"]].append(
                    {"week": week, "points": row["points"]}
                )

    result = []
    for rid, beats in bad_beats.items():
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "bad_beat_count": len(beats),
            "instances": beats,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["bad_beat_count"], reverse=True)
    return result


def stat_fraud_win_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#6 Fraud Wins – wins where team scored in the bottom half."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    fraud_wins: dict[int, list[dict[str, Any]]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        n = len(week_rows)
        median = sorted(week_rows, key=lambda x: x["points"])[n // 2]["points"] if n else 0
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W" and row["points"] < median:
                fraud_wins[row["roster_id"]].append(
                    {"week": week, "points": row["points"]}
                )

    result = []
    for rid, wins in fraud_wins.items():
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "fraud_win_count": len(wins),
            "instances": wins,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["fraud_win_count"], reverse=True)
    return result


def _optimal_score(
    starters: list[str],
    players: list[str],
    players_points: dict[str, float],
) -> float:
    """Calculate optimal lineup score given roster slot requirements."""
    # Simplified: take the top N players by points where N = len(starters)
    n_starters = len(starters)
    if n_starters == 0:
        return 0.0
    all_scores = [float(players_points.get(p, 0)) for p in players]
    all_scores.sort(reverse=True)
    return sum(all_scores[:n_starters])


def stat_points_left_on_bench(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#7 Points Left on Bench – total missed optimal points per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    bench_loss: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        bench_loss[rid] += max(0.0, optimal - actual)

    result = []
    for rid, loss in sorted(bench_loss.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_bench_points_lost": round(loss, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_manager_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#8 Manager Efficiency – actual / optimal score."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    data: dict[int, dict[str, float]] = {
        r["roster_id"]: {"actual": 0.0, "optimal": 0.0} for r in rosters
    }
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        data[rid]["actual"] += actual
        data[rid]["optimal"] += optimal

    result = []
    for rid, d in data.items():
        user = rum.get(rid, {})
        efficiency = round(d["actual"] / d["optimal"] * 100, 1) if d["optimal"] > 0 else 0.0
        result.append({
            "roster_id": rid,
            "total_actual_points": round(d["actual"], 2),
            "total_optimal_points": round(d["optimal"], 2),
            "efficiency_pct": efficiency,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["efficiency_pct"], reverse=True)
    return result


def stat_optimal_lineup_score(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#9 Optimal Lineup Score – best possible weekly scores per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    totals: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        totals[rid] += _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )

    result = []
    for rid, pts in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_optimal_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_bench_blunder_award(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#10 Bench Blunder Award – single worst lineup decision per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    worst: dict[int, dict[str, Any]] = {}
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        gap = max(0.0, optimal - actual)
        if rid not in worst or gap > worst[rid]["bench_blunder_points"]:
            worst[rid] = {"week": row["week"], "bench_blunder_points": round(gap, 2)}

    result = []
    for rid, blunder in sorted(worst.items(), key=lambda x: x[1]["bench_blunder_points"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            **blunder,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_dead_lineup_penalty(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#11 Dead Lineup Penalty – points lost from starting zero-point players."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    penalty: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        pp = row["players_points"]
        starters = row["starters"]
        bench = [p for p in row["players"] if p not in starters]
        # For each zero-point starter see if a bench player would have done better
        for starter in starters:
            s_pts = float(pp.get(starter, 0))
            if s_pts == 0:
                best_bench = max((float(pp.get(b, 0)) for b in bench), default=0.0)
                penalty[rid] += best_bench

    result = []
    for rid, pen in sorted(penalty.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "dead_lineup_penalty": round(pen, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def _collect_all_transactions(league_id: str, current_week: int) -> list[dict[str, Any]]:
    txns: list[dict[str, Any]] = []
    for w in range(1, current_week + 1):
        try:
            txns.extend(get_transactions(league_id, w))
        except httpx.HTTPError:
            pass
    return txns


def stat_waiver_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#12 Waiver ROI – fantasy points gained from waiver/FA adds."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    # Build player -> points per week lookup
    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    roi: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            roi[rid] = roi.get(rid, 0.0) + future_pts

    result = []
    for rid, pts in sorted(roi.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "waiver_roi_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_faab_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#13 FAAB Efficiency – points per FAAB dollar spent."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    faab_spent: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    faab_pts: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "waiver":
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            faab_spent[rid] = faab_spent.get(rid, 0.0) + bid
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            faab_pts[rid] = faab_pts.get(rid, 0.0) + future_pts

    result = []
    for rid in faab_spent:
        user = rum.get(rid, {})
        spent = faab_spent[rid]
        pts = faab_pts[rid]
        efficiency = round(pts / spent, 2) if spent > 0 else None
        result.append({
            "roster_id": rid,
            "faab_spent": round(spent, 2),
            "faab_points_gained": round(pts, 2),
            "points_per_dollar": efficiency,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: (x["points_per_dollar"] or 0), reverse=True)
    return result


def stat_drop_regret_index(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#14 Drop Regret Index – points scored after a manager dropped a player."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    regret: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        drops = txn.get("drops") or {}
        for pid, rid in drops.items():
            week_dropped = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w > week_dropped
            )
            regret[rid] = regret.get(rid, 0.0) + future_pts

    result = []
    for rid, pts in sorted(regret.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "drop_regret_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_free_agent_steal(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#15 Free Agent Steal of the Year – best $0 or low-cost pickup."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    steals: list[dict[str, Any]] = []
    nfl_players = get_nfl_players()

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        if bid > 10:
            continue
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            player_info = nfl_players.get(pid, {})
            player_name = player_info.get("full_name", f"Player {pid}")
            user = rum.get(rid, {})
            steals.append({
                "roster_id": rid,
                "player_id": pid,
                "player_name": player_name,
                "faab_bid": bid,
                "points_after_add": round(future_pts, 2),
                "week_added": week_added,
                "display_name": user.get("display_name", f"Team {rid}"),
            })

    steals.sort(key=lambda x: x["points_after_add"], reverse=True)
    return steals[:25]


def stat_transaction_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#16 Transaction ROI – net value from all adds minus all drops."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    net_roi: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        week_txn = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w >= week_txn
            )
            net_roi[rid] = net_roi.get(rid, 0.0) + pts
        for pid, rid in (txn.get("drops") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w >= week_txn
            )
            net_roi[rid] = net_roi.get(rid, 0.0) - pts

    result = []
    for rid, roi in sorted(net_roi.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "transaction_roi": round(roi, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_draft_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#17 Draft ROI – actual season points vs expected value at draft slot."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        # Simple expected value: inverse of pick number scaled
        # Round 1 pick #1 is worth most; exponential decay
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
        })

    # Aggregate by roster
    by_roster: dict[int, dict[str, Any]] = {}
    for row in pick_data:
        rid = row["roster_id"]
        if rid not in by_roster:
            by_roster[rid] = {"total_surplus": 0.0, "picks": []}
        by_roster[rid]["total_surplus"] += row["surplus"]
        by_roster[rid]["picks"].append(row)

    result = []
    for rid, d in sorted(by_roster.items(), key=lambda x: x[1]["total_surplus"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_surplus": round(d["total_surplus"], 2),
            "pick_count": len(d["picks"]),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_best_draft_pick(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#18 Best Draft Pick – individual picks with highest surplus value."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        user = rum.get(roster_id, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
            "display_name": user.get("display_name", f"Team {roster_id}"),
        })

    pick_data.sort(key=lambda x: x["surplus"], reverse=True)
    return pick_data[:20]


def stat_worst_draft_pick(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#19 Worst Draft Pick – individual picks with the lowest surplus."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        user = rum.get(roster_id, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
            "display_name": user.get("display_name", f"Team {roster_id}"),
        })

    pick_data.sort(key=lambda x: x["surplus"])
    return pick_data[:20]


def stat_draft_capital_retention(
    league_id: str, current_week: int  # noqa: ARG001
) -> list[dict[str, Any]]:
    """#20 Draft Capital Retention – % of drafted players still on original roster."""
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)

    # Build current roster player map
    current_roster: dict[int, set[str]] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        current_roster[rid] = set(r.get("players") or [])

    drafted_by: dict[int, list[str]] = {}
    for pick in picks:
        pid = pick.get("player_id")
        rid = int(pick.get("roster_id", 0))
        if pid:
            drafted_by.setdefault(rid, []).append(pid)

    result = []
    for rid, drafted in drafted_by.items():
        user = rum.get(rid, {})
        n_drafted = len(drafted)
        n_retained = sum(1 for p in drafted if p in current_roster.get(rid, set()))
        pct = round(n_retained / n_drafted * 100, 1) if n_drafted > 0 else 0.0
        result.append({
            "roster_id": rid,
            "drafted_count": n_drafted,
            "retained_count": n_retained,
            "retention_pct": pct,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["retention_pct"], reverse=True)
    return result


def stat_trade_value(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#21 Trade Value Won/Lost – rest-of-season points from traded assets."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    trade_net: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        # adds = players received
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            trade_net[rid] = trade_net.get(rid, 0.0) + pts
        # drops = players sent away
        for pid, rid in (txn.get("drops") or {}).items():
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            trade_net[rid] = trade_net.get(rid, 0.0) - pts

    result = []
    for rid, net in sorted(trade_net.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "trade_value_net": round(net, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_immediate_trade_impact(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#22 Immediate Trade Impact – points from traded players in first 3 weeks."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    immediate: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items()
                if week_trade < w <= week_trade + 3
            )
            immediate[rid] = immediate.get(rid, 0.0) + pts

    result = []
    for rid, pts in sorted(immediate.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "immediate_trade_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_trade_regret_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#23 Trade Regret Tracker – trades where one side clearly lost value."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    regrets: list[dict[str, Any]] = []
    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        adds = txn.get("adds") or {}
        drops = txn.get("drops") or {}
        # Collect sides
        sides: dict[int, dict[str, float]] = {}
        for pid, rid in adds.items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            sides[rid]["received"] += pts
        for pid, rid in drops.items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            sides[rid]["sent"] += pts

        if len(sides) < 2:
            continue
        roster_ids = list(sides.keys())
        for rid in roster_ids:
            user = rum.get(rid, {})
            net = sides[rid]["received"] - sides[rid]["sent"]
            regrets.append({
                "week": week_trade,
                "roster_id": rid,
                "received_points": round(sides[rid]["received"], 2),
                "sent_points": round(sides[rid]["sent"], 2),
                "net": round(net, 2),
                "display_name": user.get("display_name", f"Team {rid}"),
            })

    # Show the biggest losers (most negative net)
    regrets.sort(key=lambda x: x["net"])
    return regrets[:20]


def stat_playoff_odds(
    league_id: str, current_week: int, simulations: int = 1000
) -> list[dict[str, Any]]:
    """#24 Playoff Odds Simulator – Monte Carlo simulation of playoff chances."""
    import random

    league = get_league(league_id)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    total_weeks = int(league.get("settings", {}).get("playoff_week_start", 15)) - 1
    playoff_teams = int(league.get("settings", {}).get("playoff_teams", 6))

    # Calculate team strengths (average weekly score)
    team_scores: dict[int, list[float]] = {}
    for row in tw:
        team_scores.setdefault(row["roster_id"], []).append(row["points"])

    team_avg: dict[int, float] = {
        rid: sum(pts) / len(pts) if pts else 0.0
        for rid, pts in team_scores.items()
    }
    team_std: dict[int, float] = {}
    for rid, pts in team_scores.items():
        if len(pts) > 1:
            mean = team_avg[rid]
            team_std[rid] = (sum((p - mean) ** 2 for p in pts) / len(pts)) ** 0.5
        else:
            team_std[rid] = 20.0

    # Current standings
    actual_wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                actual_wins[row["roster_id"]] += 1

    # Build remaining schedule (pair teams by matchup_id pattern)
    remaining_weeks = max(0, total_weeks - current_week)
    roster_ids = [r["roster_id"] for r in rosters]

    playoff_counts: dict[int, int] = dict.fromkeys(roster_ids, 0)

    for _ in range(simulations):
        sim_wins = dict(actual_wins)
        for _ in range(remaining_weeks):
            random.shuffle(roster_ids)
            for i in range(0, len(roster_ids) - 1, 2):
                a = roster_ids[i]
                b = roster_ids[i + 1]
                score_a = max(0, random.gauss(team_avg.get(a, 100), team_std.get(a, 20)))
                score_b = max(0, random.gauss(team_avg.get(b, 100), team_std.get(b, 20)))
                if score_a > score_b:
                    sim_wins[a] = sim_wins.get(a, 0) + 1
                else:
                    sim_wins[b] = sim_wins.get(b, 0) + 1
        # Top N by wins make playoffs
        sorted_by_wins = sorted(sim_wins.items(), key=lambda x: x[1], reverse=True)
        for rid, _ in sorted_by_wins[:playoff_teams]:
            playoff_counts[rid] += 1

    result = []
    for rid in roster_ids:
        user = rum.get(rid, {})
        odds = round(playoff_counts.get(rid, 0) / simulations * 100, 1)
        result.append({
            "roster_id": rid,
            "current_wins": actual_wins.get(rid, 0),
            "avg_score": round(team_avg.get(rid, 0), 2),
            "playoff_probability_pct": odds,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["playoff_probability_pct"], reverse=True)
    return result


def stat_dynasty_legacy_score(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #25 Dynasty Legacy Score – season composite:
    wins (30%), total points (30%), playoff appearance (20%),
    manager efficiency (10%), waiver ROI (10%).
    """
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    # wins
    wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    total_pts: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            total_pts[row["roster_id"]] += row["points"]
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                wins[row["roster_id"]] += 1

    max_wins = max(wins.values(), default=1)
    max_pts = max(total_pts.values(), default=1)

    # playoff appearance from winners bracket
    try:
        bracket = get_winners_bracket(league_id)
        playoff_rids = {
            match.get("t1") for match in bracket if match.get("t1")
        } | {match.get("t2") for match in bracket if match.get("t2")}
    except Exception:
        playoff_rids = set()

    # manager efficiency (reuse calculation)
    eff_data: dict[int, dict[str, float]] = {
        r["roster_id"]: {"actual": 0.0, "optimal": 0.0} for r in rosters
    }
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(row["starters"], row["players"], row["players_points"])
        eff_data[rid]["actual"] += actual
        eff_data[rid]["optimal"] += optimal

    try:
        waiver_rows = stat_waiver_roi(league_id, current_week)
        waiver_roi = {
            int(row["roster_id"]): float(row["waiver_roi_points"])
            for row in waiver_rows
        }
    except Exception:
        waiver_roi = dict.fromkeys(wins, 0.0)
    max_waiver_roi = max(waiver_roi.values(), default=0.0)

    result = []
    for rid in wins:
        user = rum.get(rid, {})
        win_score = wins[rid] / max_wins
        pts_score = total_pts[rid] / max_pts
        playoff_score = 1.0 if rid in playoff_rids else 0.0
        eff = eff_data[rid]
        eff_score = eff["actual"] / eff["optimal"] if eff["optimal"] > 0 else 0.0
        waiver_points = waiver_roi.get(rid, 0.0)
        waiver_score = waiver_points / max_waiver_roi if max_waiver_roi > 0 else 0.0

        legacy = round(
            win_score * 0.30
            + pts_score * 0.30
            + playoff_score * 0.20
            + eff_score * 0.10
            + waiver_score * 0.10,
            4,
        )
        result.append({
            "roster_id": rid,
            "legacy_score": legacy,
            "wins": wins[rid],
            "total_points": round(total_pts[rid], 2),
            "waiver_roi_points": round(waiver_points, 2),
            "made_playoffs": rid in playoff_rids,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["legacy_score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 2.1 Team & League Performance (TODO #41–#50)
# ---------------------------------------------------------------------------


def _regular_season_end(league: dict[str, Any]) -> int:
    """Last regular-season week (the week before playoffs begin)."""
    settings = league.get("settings") or {}
    playoff_start = int(settings.get("playoff_week_start", 15) or 15)
    return max(1, playoff_start - 1)


def _weekly_scores(tw: list[dict[str, Any]]) -> dict[int, dict[int, float]]:
    """Map roster_id -> {week: points}."""
    scores: dict[int, dict[int, float]] = {}
    for row in tw:
        scores.setdefault(row["roster_id"], {})[row["week"]] = row["points"]
    return scores


def _opponent_map(
    tw: list[dict[str, Any]],
) -> dict[int, dict[int, int]]:
    """Map roster_id -> {week: opponent_roster_id} from paired matchups."""
    by_week: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for row in tw:
        mid = row["matchup_id"]
        if mid is None:
            continue
        by_week.setdefault(row["week"], {}).setdefault(mid, []).append(row)
    opponents: dict[int, dict[int, int]] = {}
    for week, mid_map in by_week.items():
        for pair in mid_map.values():
            if len(pair) == 2:
                a, b = pair[0]["roster_id"], pair[1]["roster_id"]
                opponents.setdefault(a, {})[week] = b
                opponents.setdefault(b, {})[week] = a
    return opponents


def _pstdev(values: list[float]) -> float:
    """Population standard deviation (0.0 for fewer than 2 samples)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return float(variance**0.5)


def stat_power_ranking_trend(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#41 Power Ranking Trend – each team's rank movement week over week.

    A weekly power score blends cumulative all-play win % (65%) with
    normalized average points (35%), then teams are ranked each week so the
    full trajectory can be drawn as a trend line.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    weeks = sorted(all_matchups.keys())

    cum_ap_wins: dict[int, float] = dict.fromkeys(rum, 0.0)
    cum_ap_games: dict[int, int] = dict.fromkeys(rum, 0)
    cum_points: dict[int, float] = dict.fromkeys(rum, 0.0)
    cum_games: dict[int, int] = dict.fromkeys(rum, 0)
    series: dict[int, list[dict[str, Any]]] = {rid: [] for rid in rum}

    for week in weeks:
        scores = [
            (r["roster_id"], r["points"]) for r in tw if r["week"] == week
        ]
        for rid, pts in scores:
            cum_points[rid] += pts
            cum_games[rid] += 1
            for opp_rid, opp_pts in scores:
                if opp_rid == rid:
                    continue
                cum_ap_games[rid] += 1
                if pts > opp_pts:
                    cum_ap_wins[rid] += 1.0
                elif pts == opp_pts:
                    cum_ap_wins[rid] += 0.5

        max_avg = max(
            (cum_points[rid] / cum_games[rid] for rid in rum if cum_games[rid]),
            default=1.0,
        ) or 1.0
        power: dict[int, float] = {}
        for rid in rum:
            ap_pct = (
                cum_ap_wins[rid] / cum_ap_games[rid] if cum_ap_games[rid] else 0.0
            )
            avg_pts = cum_points[rid] / cum_games[rid] if cum_games[rid] else 0.0
            power[rid] = 0.65 * ap_pct + 0.35 * (avg_pts / max_avg)

        ranking = sorted(rum, key=lambda r: power[r], reverse=True)
        for rank, rid in enumerate(ranking, start=1):
            series[rid].append(
                {"week": week, "rank": rank, "power_score": round(power[rid], 4)}
            )

    result = []
    for rid in rum:
        user = rum.get(rid, {})
        team_series = series[rid]
        current_rank = team_series[-1]["rank"] if team_series else 0
        previous_rank = (
            team_series[-2]["rank"] if len(team_series) >= 2 else current_rank
        )
        result.append({
            "roster_id": rid,
            "current_rank": current_rank,
            "previous_rank": previous_rank,
            "rank_delta": previous_rank - current_rank,
            "power_score": team_series[-1]["power_score"] if team_series else 0.0,
            "series": team_series,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["current_rank"] or 999)
    return result


def stat_expected_vs_actual_wins(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#42 Expected Wins vs Actual Wins – luck-adjusted record per team.

    Expected wins come from each week's scoring rank; the gap versus the
    real win total is the team's luck.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    n_teams = len(rosters)

    actual_wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    actual_losses: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    expected: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    games: dict[int, int] = {r["roster_id"]: 0 for r in rosters}

    for week in all_matchups:
        week_rows = [r for r in tw if r["week"] == week]
        for rank, row in enumerate(sorted(week_rows, key=lambda x: x["points"])):
            expected[row["roster_id"]] += rank / max(n_teams - 1, 1)
        for row in week_rows:
            games[row["roster_id"]] += 1
            res = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if res == "W":
                actual_wins[row["roster_id"]] += 1
            elif res == "L":
                actual_losses[row["roster_id"]] += 1

    result = []
    for rid in actual_wins:
        user = rum.get(rid, {})
        exp_w = round(expected[rid], 2)
        exp_l = round(games[rid] - expected[rid], 2)
        result.append({
            "roster_id": rid,
            "actual_wins": actual_wins[rid],
            "actual_losses": actual_losses[rid],
            "expected_wins": exp_w,
            "expected_losses": exp_l,
            "luck_delta": round(actual_wins[rid] - expected[rid], 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["luck_delta"], reverse=True)
    return result


def stat_points_for_against(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#43 Points For / Points Against – scatter data with quadrant labels.

    Each team is placed relative to the league median for points scored and
    points allowed, yielding four quadrants (Contender, Unlucky, Lucky,
    Rebuilding).
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    opponents = _opponent_map(tw)
    weekly = _weekly_scores(tw)

    points_for: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    points_against: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    games: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    for rid, week_pts in weekly.items():
        for week, pts in week_pts.items():
            points_for[rid] = points_for.get(rid, 0.0) + pts
            games[rid] = games.get(rid, 0) + 1
            opp = opponents.get(rid, {}).get(week)
            if opp is not None:
                points_against[rid] = points_against.get(rid, 0.0) + weekly.get(
                    opp, {}
                ).get(week, 0.0)

    pf_values = sorted(points_for.values())
    pa_values = sorted(points_against.values())

    def _median(vals: list[float]) -> float:
        if not vals:
            return 0.0
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2

    median_pf = round(_median(pf_values), 2)
    median_pa = round(_median(pa_values), 2)

    result = []
    for rid in points_for:
        user = rum.get(rid, {})
        pf = points_for[rid]
        pa = points_against[rid]
        high_pf = pf >= median_pf
        low_pa = pa <= median_pa
        if high_pf and low_pa:
            quadrant = "Contender"
        elif high_pf and not low_pa:
            quadrant = "Unlucky"
        elif not high_pf and low_pa:
            quadrant = "Lucky"
        else:
            quadrant = "Rebuilding"
        result.append({
            "roster_id": rid,
            "points_for": round(pf, 2),
            "points_against": round(pa, 2),
            "avg_for": round(pf / games[rid], 2) if games[rid] else 0.0,
            "avg_against": round(pa / games[rid], 2) if games[rid] else 0.0,
            "quadrant": quadrant,
            "median_for": median_pf,
            "median_against": median_pa,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["points_for"], reverse=True)
    return result


def stat_strength_of_schedule(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#44 Strength of Schedule – past and remaining difficulty per team.

    Difficulty is the average season scoring rate of the opponents a team has
    faced (past) and is scheduled to face (remaining).
    """
    league = get_league(league_id)
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    weekly = _weekly_scores(tw)
    past_opponents = _opponent_map(tw)

    # Season scoring rate per team (points per game so far).
    team_avg: dict[int, float] = {}
    for rid in rum:
        pts = list(weekly.get(rid, {}).values())
        team_avg[rid] = sum(pts) / len(pts) if pts else 0.0

    # Remaining schedule: scheduled matchups from next week to season end.
    season_end = _regular_season_end(league)
    future: dict[int, list[int]] = {rid: [] for rid in rum}
    for week in range(current_week + 1, season_end + 1):
        try:
            week_matchups = get_matchups(league_id, week)
        except httpx.HTTPError:
            continue
        mid_map: dict[int, list[int]] = {}
        for m in week_matchups:
            if m.get("roster_id") is None or m.get("matchup_id") is None:
                continue
            mid_map.setdefault(int(m["matchup_id"]), []).append(int(m["roster_id"]))
        for pair in mid_map.values():
            if len(pair) == 2:
                future.setdefault(pair[0], []).append(pair[1])
                future.setdefault(pair[1], []).append(pair[0])

    result = []
    for rid in rum:
        user = rum.get(rid, {})
        past_opps = list(past_opponents.get(rid, {}).values())
        past_vals = [team_avg.get(o, 0.0) for o in past_opps]
        future_opps = future.get(rid, [])
        future_vals = [team_avg.get(o, 0.0) for o in future_opps]
        all_vals = past_vals + future_vals
        result.append({
            "roster_id": rid,
            "past_sos": round(sum(past_vals) / len(past_vals), 2)
            if past_vals
            else 0.0,
            "remaining_sos": round(sum(future_vals) / len(future_vals), 2)
            if future_vals
            else 0.0,
            "full_sos": round(sum(all_vals) / len(all_vals), 2)
            if all_vals
            else 0.0,
            "games_remaining": len(future_opps),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["remaining_sos"], reverse=True)
    return result


def stat_consistency_score(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#45 Consistency / Volatility – standard deviation of weekly scores."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    weekly = _weekly_scores(tw)

    result = []
    for rid in rum:
        user = rum.get(rid, {})
        scores = list(weekly.get(rid, {}).values())
        avg = sum(scores) / len(scores) if scores else 0.0
        std = _pstdev(scores)
        cv = round(std / avg * 100, 1) if avg else 0.0
        result.append({
            "roster_id": rid,
            "avg_score": round(avg, 2),
            "std_dev": round(std, 2),
            "coefficient_of_variation": cv,
            "floor": round(min(scores), 2) if scores else 0.0,
            "ceiling": round(max(scores), 2) if scores else 0.0,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    # Most consistent first (lowest volatility).
    result.sort(key=lambda x: x["std_dev"])
    return result


def stat_all_play_standings(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#46 All-Play Standings – record vs every team each week, with win %."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    wins: dict[int, int] = dict.fromkeys(rum, 0)
    losses: dict[int, int] = dict.fromkeys(rum, 0)
    ties: dict[int, int] = dict.fromkeys(rum, 0)
    for week in all_matchups:
        scores = [
            (r["roster_id"], r["points"]) for r in tw if r["week"] == week
        ]
        for rid, pts in scores:
            for opp_rid, opp_pts in scores:
                if opp_rid == rid:
                    continue
                if pts > opp_pts:
                    wins[rid] += 1
                elif pts < opp_pts:
                    losses[rid] += 1
                else:
                    ties[rid] += 1

    result = []
    for rid in rum:
        user = rum.get(rid, {})
        total = wins[rid] + losses[rid] + ties[rid]
        win_pct = round((wins[rid] + 0.5 * ties[rid]) / total * 100, 1) if total else 0.0
        result.append({
            "roster_id": rid,
            "all_play_wins": wins[rid],
            "all_play_losses": losses[rid],
            "all_play_ties": ties[rid],
            "win_pct": win_pct,
            "record": f"{wins[rid]}-{losses[rid]}-{ties[rid]}",
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["win_pct"], reverse=True)
    return result


def stat_roster_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#47 Roster Efficiency – actual vs optimal lineup points, per week."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    by_roster: dict[int, dict[str, Any]] = {
        rid: {"actual": 0.0, "optimal": 0.0, "series": []} for rid in rum
    }
    for row in sorted(tw, key=lambda r: (r["roster_id"], r["week"])):
        rid = row["roster_id"]
        if rid not in by_roster:
            continue
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        eff = round(actual / optimal * 100, 1) if optimal > 0 else 0.0
        by_roster[rid]["actual"] += actual
        by_roster[rid]["optimal"] += optimal
        by_roster[rid]["series"].append({
            "week": row["week"],
            "actual": round(actual, 2),
            "optimal": round(optimal, 2),
            "efficiency": eff,
        })

    result = []
    for rid, d in by_roster.items():
        user = rum.get(rid, {})
        efficiency = (
            round(d["actual"] / d["optimal"] * 100, 1) if d["optimal"] > 0 else 0.0
        )
        result.append({
            "roster_id": rid,
            "efficiency_pct": efficiency,
            "total_actual_points": round(d["actual"], 2),
            "total_optimal_points": round(d["optimal"], 2),
            "series": d["series"],
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["efficiency_pct"], reverse=True)
    return result


def stat_bench_points_ranking(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#48 Bench Points Left on the Table – ranked across the league."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    by_roster: dict[int, dict[str, Any]] = {
        rid: {"total": 0.0, "series": [], "worst_week": None, "worst": 0.0}
        for rid in rum
    }
    for row in sorted(tw, key=lambda r: (r["roster_id"], r["week"])):
        rid = row["roster_id"]
        if rid not in by_roster:
            continue
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        lost = max(0.0, optimal - row["points"])
        by_roster[rid]["total"] += lost
        by_roster[rid]["series"].append(
            {"week": row["week"], "bench_points": round(lost, 2)}
        )
        if lost > by_roster[rid]["worst"]:
            by_roster[rid]["worst"] = lost
            by_roster[rid]["worst_week"] = row["week"]

    result = []
    for rid, d in by_roster.items():
        user = rum.get(rid, {})
        n_weeks = len(d["series"])
        result.append({
            "roster_id": rid,
            "total_bench_points": round(d["total"], 2),
            "avg_bench_points": round(d["total"] / n_weeks, 2) if n_weeks else 0.0,
            "worst_week": d["worst_week"],
            "worst_week_points": round(d["worst"], 2),
            "series": d["series"],
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["total_bench_points"], reverse=True)
    return result


def stat_margin_of_victory(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#49 Margin of Victory – blowout vs nailbiter distribution per team.

    A blowout is a margin of 40+ points; a nailbiter is a margin of 5 or
    fewer points.
    """
    blowout_threshold = 40.0
    nailbiter_threshold = 5.0

    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    weekly = _weekly_scores(tw)
    opponents = _opponent_map(tw)

    by_roster: dict[int, dict[str, Any]] = {
        rid: {
            "margins": [],
            "biggest_win": 0.0,
            "worst_loss": 0.0,
            "blowout_wins": 0,
            "blowout_losses": 0,
            "nailbiters": 0,
        }
        for rid in rum
    }
    for rid, week_pts in weekly.items():
        if rid not in by_roster:
            continue
        for week, pts in week_pts.items():
            opp = opponents.get(rid, {}).get(week)
            if opp is None:
                continue
            margin = pts - weekly.get(opp, {}).get(week, 0.0)
            by_roster[rid]["margins"].append(round(margin, 2))
            if margin > by_roster[rid]["biggest_win"]:
                by_roster[rid]["biggest_win"] = margin
            if margin < by_roster[rid]["worst_loss"]:
                by_roster[rid]["worst_loss"] = margin
            if abs(margin) <= nailbiter_threshold:
                by_roster[rid]["nailbiters"] += 1
            elif margin >= blowout_threshold:
                by_roster[rid]["blowout_wins"] += 1
            elif margin <= -blowout_threshold:
                by_roster[rid]["blowout_losses"] += 1

    result = []
    for rid, d in by_roster.items():
        user = rum.get(rid, {})
        margins = d["margins"]
        avg_margin = round(sum(margins) / len(margins), 2) if margins else 0.0
        result.append({
            "roster_id": rid,
            "avg_margin": avg_margin,
            "biggest_win": round(d["biggest_win"], 2),
            "worst_loss": round(d["worst_loss"], 2),
            "blowout_wins": d["blowout_wins"],
            "blowout_losses": d["blowout_losses"],
            "nailbiters": d["nailbiters"],
            "margins": margins,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["avg_margin"], reverse=True)
    return result


def stat_cumulative_points_race(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#50 Cumulative Points Race – running points total over the season."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    weekly = _weekly_scores(tw)
    weeks = sorted(all_matchups.keys())

    result = []
    for rid in rum:
        user = rum.get(rid, {})
        running = 0.0
        series: list[dict[str, Any]] = []
        for week in weeks:
            running += weekly.get(rid, {}).get(week, 0.0)
            series.append({"week": week, "cumulative_points": round(running, 2)})
        result.append({
            "roster_id": rid,
            "total_points": round(running, 2),
            "series": series,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["total_points"], reverse=True)
    return result
