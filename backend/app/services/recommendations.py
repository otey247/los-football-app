"""Actionable, predictive, and social recommendation engine for the league.

This service powers the "coaching" surface of the app (TODO items 92-100):

* Actionable recommendations — start/sit (#92), waiver pickups (#93),
  trade targets (#94), and optimal-lineup nudges (#95).
* Predictive & strategic insights — rest-of-season outlook (#96), must-win
  flags (#97), and regression / luck warnings (#98).
* Social & community insights — a rivalry / trash-talk index (#99) and the
  power-ranking committee model used by the vote-blending endpoint (#100).

Everything is grounded in Sleeper data and the league's own scoring: per-player
points come from the league-scored ``players_points`` on each matchup, so
projections respect PPR / superflex / TE-premium settings automatically. The
app exposes no external projection feed, so "projected" values here are a
trailing-production proxy and are labelled as such in the UI.
"""

import random
from typing import Any

from app.services import narrative as nar
from app.services import sleeper as svc

# Default look-back window (completed weeks) used as a production proxy.
_LOOKBACK = 4

# Bench-style slots that never count as a starting position.
_BENCH_SLOTS = {"BN", "IR", "TAXI", "RESERVE"}

# The fantasy base positions we track for needs/surplus analysis.
_BASE_POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]

# Injury / availability statuses that knock a player's effective projection out.
_OUT_STATUSES = {"Out", "IR", "PUP", "Sus", "DNR", "NA"}

# Roster slot -> set of eligible base positions.
_SLOT_ELIGIBILITY: dict[str, set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "DL": {"DL"},
    "LB": {"LB"},
    "DB": {"DB"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "WRRB_WRT": {"RB", "WR", "TE"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "IDP_FLEX": {"DL", "LB", "DB"},
}


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


def _eligible(slot: str) -> set[str]:
    """Base positions eligible for a roster slot."""
    return _SLOT_ELIGIBILITY.get(slot, {slot})


def _starting_slots(league: dict[str, Any]) -> list[str]:
    """Ordered list of starting slots (bench/IR/taxi removed)."""
    positions = league.get("roster_positions") or []
    return [p for p in positions if p not in _BENCH_SLOTS]


def _global_player_points(
    league_id: str, current_week: int
) -> dict[str, dict[int, float]]:
    """{player_id: {week: league_scored_points}} across every completed week."""
    all_matchups = svc._collect_all_matchups(league_id, current_week)
    tw = svc._team_week_table(all_matchups)
    points: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            points.setdefault(str(pid), {})[row["week"]] = float(pts)
    return points


def _candidate(
    pid: str,
    players_db: dict[str, Any],
    points: dict[str, dict[int, float]],
    current_week: int,
    lookback: int = _LOOKBACK,
) -> dict[str, Any]:
    """Build a projection candidate for one player from trailing production."""
    info = players_db.get(pid) or {}
    positions = set(info.get("fantasy_positions") or [])
    if not positions and info.get("position"):
        positions = {info["position"]}
    name = info.get("full_name") or info.get("last_name") or ""
    if not name:
        # Team defenses are keyed by team abbreviation with no full_name.
        name = f"{pid} D/ST" if "DEF" in positions else f"Player {pid}"

    history = points.get(pid, {})
    recent_weeks = sorted(w for w in history if w <= current_week)[-lookback:]
    recent = [history[w] for w in recent_weeks]
    avg = round(sum(recent) / len(recent), 2) if recent else 0.0
    last = round(recent[-1], 2) if recent else 0.0

    status = info.get("injury_status") or None
    out = bool(status) and status in _OUT_STATUSES
    effective = 0.0 if out else avg

    return {
        "player_id": pid,
        "name": name,
        "positions": positions,
        "position": "/".join(sorted(positions)) or "?",
        "team": info.get("team"),
        "proj": round(effective, 2),
        "raw_proj": avg,
        "last": last,
        "games": len(recent),
        "status": status,
        "out": out,
    }


def _fill_lineup(
    slots: list[str], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any] | None], list[dict[str, Any]]]:
    """Greedily build the optimal lineup, filling most-restrictive slots first.

    Returns ``(chosen_per_slot, bench)`` where ``chosen_per_slot[i]`` is the
    player assigned to ``slots[i]`` (or ``None`` if no eligible player exists).
    """
    order = sorted(range(len(slots)), key=lambda i: len(_eligible(slots[i])))
    chosen: list[dict[str, Any] | None] = [None] * len(slots)
    used: set[str] = set()
    for i in order:
        elig = _eligible(slots[i])
        best: dict[str, Any] | None = None
        for c in candidates:
            if c["player_id"] in used or not (c["positions"] & elig):
                continue
            if best is None or c["proj"] > best["proj"]:
                best = c
        if best is not None:
            chosen[i] = best
            used.add(best["player_id"])
    bench = [c for c in candidates if c["player_id"] not in used]
    return chosen, bench


def _confidence(delta: float) -> str:
    if delta >= 5:
        return "high"
    if delta >= 2:
        return "medium"
    return "low"


def _position_demand(slots: list[str]) -> dict[str, int]:
    """How many starting slots each base position is eligible for (flex counts)."""
    demand = dict.fromkeys(_BASE_POSITIONS, 0)
    for s in slots:
        for p in _eligible(s):
            if p in demand:
                demand[p] += 1
    return demand


def _roster_candidates(
    roster: dict[str, Any],
    players_db: dict[str, Any],
    points: dict[str, dict[int, float]],
    current_week: int,
) -> list[dict[str, Any]]:
    return [
        _candidate(str(pid), players_db, points, current_week)
        for pid in (roster.get("players") or [])
    ]


def _positional_strength(
    rosters: list[dict[str, Any]],
    players_db: dict[str, Any],
    points: dict[str, dict[int, float]],
    current_week: int,
    demand: dict[str, int],
) -> dict[int, dict[str, float]]:
    """{roster_id: {position: summed projection of its best `demand` players}}."""
    strength: dict[int, dict[str, float]] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        cands = _roster_candidates(r, players_db, points, current_week)
        per_pos: dict[str, float] = {}
        for pos in _BASE_POSITIONS:
            depth = max(demand.get(pos, 0), 1)
            projs = sorted(
                (c["raw_proj"] for c in cands if pos in c["positions"]),
                reverse=True,
            )
            per_pos[pos] = round(sum(projs[:depth]), 2)
        strength[rid] = per_pos
    return strength


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _get_roster(rosters: list[dict[str, Any]], roster_id: int) -> dict[str, Any]:
    roster = next(
        (r for r in rosters if int(r["roster_id"]) == roster_id), None
    )
    if roster is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail=f"Roster {roster_id} not found in league"
        )
    return roster


def list_teams(league_id: str) -> list[dict[str, Any]]:
    """Roster_id + display name list, for team pickers on the frontend."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    teams = []
    for r in rosters:
        rid = int(r["roster_id"])
        user = rum.get(rid, {})
        teams.append(
            {
                "roster_id": rid,
                "display_name": user.get("display_name", f"Team {rid}"),
                "avatar": user.get("avatar"),
            }
        )
    teams.sort(key=lambda t: t["display_name"].lower())
    return teams


# ---------------------------------------------------------------------------
# #92 Start/Sit recommendations
# ---------------------------------------------------------------------------


def start_sit_recommendations(
    league_id: str, roster_id: int, current_week: int
) -> dict[str, Any]:
    """Recommend the optimal lineup and surface the closest start/sit calls."""
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    players_db = svc.get_nfl_players()
    points = _global_player_points(league_id, current_week)

    roster = _get_roster(rosters, roster_id)
    slots = _starting_slots(league)
    cands = _roster_candidates(roster, players_db, points, current_week)
    chosen, bench = _fill_lineup(slots, cands)

    starters = [
        {
            "slot": slots[i],
            "player_id": c["player_id"],
            "name": c["name"],
            "position": c["position"],
            "proj": c["proj"],
            "status": c["status"],
        }
        for i, c in enumerate(chosen)
        if c is not None
    ]
    bench_out = sorted(
        (
            {
                "player_id": c["player_id"],
                "name": c["name"],
                "position": c["position"],
                "proj": c["proj"],
                "status": c["status"],
            }
            for c in bench
        ),
        key=lambda c: c["proj"],
        reverse=True,
    )

    # Closest calls: weakest starter in each slot vs the best eligible benched
    # alternative. Smaller deltas = tougher (lower-confidence) decisions.
    calls: list[dict[str, Any]] = []
    for i, c in enumerate(chosen):
        if c is None:
            continue
        elig = _eligible(slots[i])
        alt = max(
            (b for b in bench if b["positions"] & elig),
            key=lambda b: b["proj"],
            default=None,
        )
        if alt is None:
            continue
        delta = round(c["proj"] - alt["proj"], 2)
        calls.append(
            {
                "slot": slots[i],
                "start": c["name"],
                "start_proj": c["proj"],
                "sit": alt["name"],
                "sit_proj": alt["proj"],
                "delta": delta,
                "confidence": _confidence(delta),
            }
        )
    calls.sort(key=lambda x: x["delta"])

    return {
        "roster_id": roster_id,
        "team": rum.get(roster_id, {}).get("display_name", f"Team {roster_id}"),
        "week": current_week,
        "projected_total": round(sum(s["proj"] for s in starters), 2),
        "starters": starters,
        "bench": bench_out,
        "calls": calls[:6],
        "note": (
            "Projections are a trailing-average proxy from this league's scored "
            "results — not an external projection feed."
        ),
    }


# ---------------------------------------------------------------------------
# #93 Waiver-wire pickup suggestions
# ---------------------------------------------------------------------------


def waiver_suggestions(
    league_id: str, roster_id: int, current_week: int, limit: int = 15
) -> dict[str, Any]:
    """Rank available trending adds by this team's positional need + opportunity."""
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    players_db = svc.get_nfl_players()
    points = _global_player_points(league_id, current_week)
    slots = _starting_slots(league)
    demand = _position_demand(slots)

    _get_roster(rosters, roster_id)

    rostered: set[str] = set()
    for r in rosters:
        rostered.update(str(p) for p in (r.get("players") or []))

    strength = _positional_strength(
        rosters, players_db, points, current_week, demand
    )
    me = strength.get(roster_id, {})
    # Need per position: how far below the league median this team sits.
    need: dict[str, float] = {}
    for pos in _BASE_POSITIONS:
        if not demand.get(pos):
            continue
        league_values = [s.get(pos, 0.0) for s in strength.values()]
        med = _median(league_values)
        need[pos] = max(0.0, med - me.get(pos, 0.0))
    max_need = max(need.values(), default=0.0)

    trending = svc.get_trending_players("add", lookback_hours=48, limit=200)
    max_count = max((t.get("count", 0) for t in trending), default=1) or 1

    suggestions: list[dict[str, Any]] = []
    for t in trending:
        pid = str(t.get("player_id"))
        if pid in rostered:
            continue
        cand = _candidate(pid, players_db, points, current_week)
        cand_positions = cand["positions"] & set(_BASE_POSITIONS)
        if not cand_positions:
            continue
        # Best matching need across the player's eligible positions.
        pos_need = max((need.get(p, 0.0) for p in cand_positions), default=0.0)
        need_factor = (pos_need / max_need) if max_need else 0.0
        opportunity = t.get("count", 0) / max_count
        production = cand["raw_proj"]
        # Blend: market opportunity + team need, lightly boosted by prior output.
        score = round(
            opportunity * 0.5 + need_factor * 0.4 + min(production / 25.0, 1.0) * 0.1,
            4,
        )
        suggestions.append(
            {
                "player_id": pid,
                "name": cand["name"],
                "position": cand["position"],
                "team": cand["team"],
                "status": cand["status"],
                "trending_adds": t.get("count", 0),
                "recent_ppg": cand["raw_proj"],
                "fills_need": bool(pos_need > 0),
                "score": score,
            }
        )

    suggestions.sort(key=lambda x: x["score"], reverse=True)

    # Drop candidates: this team's lowest-projected, non-injured depth pieces.
    roster = _get_roster(rosters, roster_id)
    my_cands = _roster_candidates(roster, players_db, points, current_week)
    drop_candidates = sorted(my_cands, key=lambda c: c["proj"])[:5]
    drops = [
        {
            "player_id": c["player_id"],
            "name": c["name"],
            "position": c["position"],
            "recent_ppg": c["raw_proj"],
            "status": c["status"],
        }
        for c in drop_candidates
    ]

    top_needs = sorted(
        ((p, round(v, 2)) for p, v in need.items() if v > 0),
        key=lambda x: x[1],
        reverse=True,
    )

    return {
        "roster_id": roster_id,
        "team": rum.get(roster_id, {}).get("display_name", f"Team {roster_id}"),
        "week": current_week,
        "needs": [{"position": p, "gap": v} for p, v in top_needs],
        "suggestions": suggestions[:limit],
        "drop_candidates": drops,
        "note": (
            "Trending counts are market activity (adds across all Sleeper "
            "leagues), not projections. Availability is checked against this "
            "league's rosters."
        ),
    }


# ---------------------------------------------------------------------------
# #94 Trade target suggestions
# ---------------------------------------------------------------------------


def trade_targets(
    league_id: str, roster_id: int, current_week: int
) -> dict[str, Any]:
    """Suggest trade partners that are deep where this team is thin (and vice-versa)."""
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    players_db = svc.get_nfl_players()
    points = _global_player_points(league_id, current_week)
    slots = _starting_slots(league)
    demand = _position_demand(slots)

    _get_roster(rosters, roster_id)
    strength = _positional_strength(
        rosters, players_db, points, current_week, demand
    )
    me = strength.get(roster_id, {})

    medians = {
        pos: _median([s.get(pos, 0.0) for s in strength.values()])
        for pos in _BASE_POSITIONS
        if demand.get(pos)
    }
    my_needs = sorted(
        (p for p in medians if me.get(p, 0.0) < medians[p]),
        key=lambda p: me.get(p, 0.0) - medians[p],
    )
    my_surplus = sorted(
        (p for p in medians if me.get(p, 0.0) > medians[p]),
        key=lambda p: me.get(p, 0.0) - medians[p],
        reverse=True,
    )

    def best_at(rid: int, pos: str, skip: set[str]) -> dict[str, Any] | None:
        roster = next((r for r in rosters if int(r["roster_id"]) == rid), None)
        if roster is None:
            return None
        cands = [
            c
            for c in _roster_candidates(roster, players_db, points, current_week)
            if pos in c["positions"] and c["player_id"] not in skip
        ]
        return max(cands, key=lambda c: c["raw_proj"], default=None)

    suggestions: list[dict[str, Any]] = []
    for r in rosters:
        rid = int(r["roster_id"])
        if rid == roster_id:
            continue
        their = strength.get(rid, {})
        # Positions where they're strong and I'm weak -> I want to acquire.
        for need_pos in my_needs:
            if their.get(need_pos, 0.0) <= medians.get(need_pos, 0.0):
                continue
            target = best_at(rid, need_pos, set())
            if target is None:
                continue
            # What I can offer: a surplus player at a position THEY are thin in.
            offer = None
            offer_pos = None
            for surplus_pos in my_surplus:
                if their.get(surplus_pos, 0.0) >= medians.get(surplus_pos, 0.0):
                    continue
                offer = best_at(roster_id, surplus_pos, set())
                if offer is not None:
                    offer_pos = surplus_pos
                    break
            fairness = (
                round((offer["raw_proj"] - target["raw_proj"]), 2)
                if offer
                else None
            )
            suggestions.append(
                {
                    "partner_roster_id": rid,
                    "partner": rum.get(rid, {}).get(
                        "display_name", f"Team {rid}"
                    ),
                    "acquire_position": need_pos,
                    "target_player": target["name"],
                    "target_ppg": target["raw_proj"],
                    "offer_position": offer_pos,
                    "offer_player": offer["name"] if offer else None,
                    "offer_ppg": offer["raw_proj"] if offer else None,
                    "ppg_gap": fairness,
                }
            )

    # Prioritise targets at the position of greatest need.
    need_rank = {p: i for i, p in enumerate(my_needs)}
    suggestions.sort(
        key=lambda s: (
            need_rank.get(s["acquire_position"], 99),
            -s["target_ppg"],
        )
    )

    return {
        "roster_id": roster_id,
        "team": rum.get(roster_id, {}).get("display_name", f"Team {roster_id}"),
        "week": current_week,
        "needs": my_needs,
        "surplus": my_surplus,
        "suggestions": suggestions[:12],
        "note": (
            "Suggestions weigh each team's positional surplus against your needs "
            "using trailing production; confirm fit with current scoring and bye "
            "weeks before offering."
        ),
    }


# ---------------------------------------------------------------------------
# #95 Optimal-lineup nudges (pre-lock)
# ---------------------------------------------------------------------------


def lineup_nudges(league_id: str, current_week: int) -> dict[str, Any]:
    """Flag rosters whose best lineup is at risk (injured/empty/low slots).

    Intended to drive a pre-lock reminder. Delivery (push/email) is left to the
    notification layer; this returns the per-team content to send.
    """
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    players_db = svc.get_nfl_players()
    points = _global_player_points(league_id, current_week)
    slots = _starting_slots(league)

    nudges: list[dict[str, Any]] = []
    for r in rosters:
        rid = int(r["roster_id"])
        cands = _roster_candidates(r, players_db, points, current_week)
        chosen, bench = _fill_lineup(slots, cands)
        issues: list[str] = []

        empty = sum(1 for c in chosen if c is None)
        if empty:
            issues.append(f"{empty} starting slot(s) have no eligible player")

        injured_starters = [
            c["name"] for c in chosen if c is not None and c["out"]
        ]
        for name in injured_starters:
            issues.append(f"{name} is ruled out but slotted to start")

        # A clearly better bench option than a projected starter in its slot.
        for i, c in enumerate(chosen):
            if c is None:
                continue
            elig = _eligible(slots[i])
            alt = max(
                (b for b in bench if (b["positions"] & elig) and not b["out"]),
                key=lambda b: b["proj"],
                default=None,
            )
            if alt is not None and alt["proj"] - c["proj"] >= 3:
                issues.append(
                    f"Consider {alt['name']} ({alt['proj']}) over "
                    f"{c['name']} ({c['proj']}) at {slots[i]}"
                )

        if issues:
            nudges.append(
                {
                    "roster_id": rid,
                    "team": rum.get(rid, {}).get(
                        "display_name", f"Team {rid}"
                    ),
                    "projected_total": round(
                        sum(c["proj"] for c in chosen if c is not None), 2
                    ),
                    "issues": issues,
                }
            )

    nudges.sort(key=lambda n: len(n["issues"]), reverse=True)
    return {
        "week": current_week,
        "nudges": nudges,
        "note": (
            "Nudges are generated from trailing production and injury status. "
            "Wire these to push/email before lineup lock to remind managers."
        ),
    }


# ---------------------------------------------------------------------------
# Season simulation (shared by ROS outlook & must-win flags)
# ---------------------------------------------------------------------------


def _team_strength(
    league_id: str, current_week: int
) -> tuple[dict[int, float], dict[int, float]]:
    """Per-roster mean and standard deviation of weekly scores."""
    all_matchups = svc._collect_all_matchups(league_id, current_week)
    tw = svc._team_week_table(all_matchups)
    scores: dict[int, list[float]] = {}
    for row in tw:
        scores.setdefault(row["roster_id"], []).append(row["points"])
    avg: dict[int, float] = {}
    std: dict[int, float] = {}
    for rid, pts in scores.items():
        if pts:
            mean = sum(pts) / len(pts)
            avg[rid] = mean
            std[rid] = (
                (sum((p - mean) ** 2 for p in pts) / len(pts)) ** 0.5
                if len(pts) > 1
                else 20.0
            )
        else:
            avg[rid] = 100.0
            std[rid] = 20.0
    return avg, std


def _remaining_schedule(
    league_id: str, current_week: int, last_reg_week: int
) -> dict[int, list[tuple[int, int]]]:
    """{week: [(roster_a, roster_b), ...]} for unplayed regular-season weeks."""
    schedule: dict[int, list[tuple[int, int]]] = {}
    for w in range(current_week + 1, last_reg_week + 1):
        try:
            week_matchups = svc.get_matchups(league_id, w)
        except Exception:  # noqa: BLE001
            continue
        by_mid: dict[Any, list[int]] = {}
        for m in week_matchups:
            if m.get("roster_id") is None:
                continue
            by_mid.setdefault(m.get("matchup_id"), []).append(int(m["roster_id"]))
        pairs = [
            (rids[0], rids[1])
            for mid, rids in by_mid.items()
            if mid is not None and len(rids) >= 2
        ]
        if pairs:
            schedule[w] = pairs
    return schedule


def _current_wins_points(
    league_id: str, current_week: int
) -> tuple[dict[int, int], dict[int, float]]:
    all_matchups = svc._collect_all_matchups(league_id, current_week)
    tw = svc._team_week_table(all_matchups)
    wins: dict[int, int] = {}
    pts: dict[int, float] = {}
    for week in all_matchups:
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            rid = row["roster_id"]
            pts[rid] = pts.get(rid, 0.0) + row["points"]
            wins.setdefault(rid, 0)
            if svc._resolve_result(
                rid, row["matchup_id"], row["points"], week_rows
            ) == "W":
                wins[rid] += 1
    return wins, pts


def _simulate(
    league_id: str, current_week: int, n_sims: int = 1500
) -> dict[str, Any]:
    """Monte-Carlo the rest of the regular season on the real remaining schedule.

    Returns playoff odds, next-game win sensitivity, and the remaining schedule.
    """
    league = svc.get_league(league_id)
    rosters = svc.get_rosters(league_id)
    rids = [int(r["roster_id"]) for r in rosters]
    settings = league.get("settings", {})
    last_reg_week = int(settings.get("playoff_week_start", 15)) - 1
    playoff_teams = int(settings.get("playoff_teams", 6))

    avg, std = _team_strength(league_id, current_week)
    base_wins, base_pts = _current_wins_points(league_id, current_week)
    schedule = _remaining_schedule(league_id, current_week, last_reg_week)

    # Each team's next remaining game (earliest week they appear).
    next_game: dict[int, tuple[int, int]] = {}
    for w in sorted(schedule):
        for a, b in schedule[w]:
            next_game.setdefault(a, (w, b))
            next_game.setdefault(b, (w, a))

    playoff_count = dict.fromkeys(rids, 0)
    won_next = dict.fromkeys(rids, 0)
    made_given_won = dict.fromkeys(rids, 0)
    lost_next = dict.fromkeys(rids, 0)
    made_given_lost = dict.fromkeys(rids, 0)

    for _ in range(n_sims):
        wins = {rid: base_wins.get(rid, 0) for rid in rids}
        pts = {rid: base_pts.get(rid, 0.0) for rid in rids}
        next_result: dict[int, bool] = {}
        for w in sorted(schedule):
            for a, b in schedule[w]:
                sa = max(0.0, random.gauss(avg.get(a, 100), std.get(a, 20)))
                sb = max(0.0, random.gauss(avg.get(b, 100), std.get(b, 20)))
                pts[a] += sa
                pts[b] += sb
                a_won = sa >= sb
                if a_won:
                    wins[a] += 1
                else:
                    wins[b] += 1
                if next_game.get(a) == (w, b):
                    next_result[a] = a_won
                if next_game.get(b) == (w, a):
                    next_result[b] = not a_won
        ranked = sorted(rids, key=lambda r: (wins[r], pts[r]), reverse=True)
        made = set(ranked[:playoff_teams])
        for rid in rids:
            if rid in made:
                playoff_count[rid] += 1
            res = next_result.get(rid)
            if res is True:
                won_next[rid] += 1
                if rid in made:
                    made_given_won[rid] += 1
            elif res is False:
                lost_next[rid] += 1
                if rid in made:
                    made_given_lost[rid] += 1

    odds = {rid: playoff_count[rid] / n_sims for rid in rids}
    sensitivity: dict[int, float] = {}
    for rid in rids:
        p_win = (
            made_given_won[rid] / won_next[rid]
            if won_next[rid]
            else odds[rid]
        )
        p_lose = (
            made_given_lost[rid] / lost_next[rid]
            if lost_next[rid]
            else odds[rid]
        )
        sensitivity[rid] = p_win - p_lose

    return {
        "odds": odds,
        "sensitivity": sensitivity,
        "schedule": schedule,
        "next_game": next_game,
        "avg": avg,
        "std": std,
        "base_wins": base_wins,
        "last_reg_week": last_reg_week,
        "playoff_teams": playoff_teams,
    }


def _win_probability(avg_a: float, std_a: float, avg_b: float, std_b: float) -> float:
    """P(team A outscores team B) under a normal-difference approximation."""
    import math

    mean = avg_a - avg_b
    var = std_a**2 + std_b**2
    if var <= 0:
        return 0.5 if mean == 0 else (1.0 if mean > 0 else 0.0)
    z = mean / math.sqrt(var)
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ---------------------------------------------------------------------------
# #96 Rest-of-season outlook
# ---------------------------------------------------------------------------


def rest_of_season_outlook(
    league_id: str, current_week: int
) -> dict[str, Any]:
    """Remaining schedule strength, projected wins, and swing matchups per team."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)

    sim = _simulate(league_id, current_week)
    avg, std = sim["avg"], sim["std"]
    schedule = sim["schedule"]
    base_wins = sim["base_wins"]
    odds = sim["odds"]

    # Per-team remaining opponents.
    remaining: dict[int, list[tuple[int, int]]] = {}
    for w in sorted(schedule):
        for a, b in schedule[w]:
            remaining.setdefault(a, []).append((w, b))
            remaining.setdefault(b, []).append((w, a))

    league_avg = (
        sum(avg.values()) / len(avg) if avg else 100.0
    )

    teams: list[dict[str, Any]] = []
    for r in rosters:
        rid = int(r["roster_id"])
        games = remaining.get(rid, [])
        game_rows = []
        proj_added_wins = 0.0
        opp_strengths: list[float] = []
        for w, opp in games:
            wp = _win_probability(
                avg.get(rid, 100), std.get(rid, 20), avg.get(opp, 100), std.get(opp, 20)
            )
            proj_added_wins += wp
            opp_strengths.append(avg.get(opp, 100))
            game_rows.append(
                {
                    "week": w,
                    "opponent": rum.get(opp, {}).get(
                        "display_name", f"Team {opp}"
                    ),
                    "opponent_avg": round(avg.get(opp, 100), 1),
                    "win_probability": round(wp * 100, 1),
                    "swing": 0.4 <= wp <= 0.6,
                }
            )
        sos = (
            round(sum(opp_strengths) / len(opp_strengths), 1)
            if opp_strengths
            else 0.0
        )
        teams.append(
            {
                "roster_id": rid,
                "team": rum.get(rid, {}).get("display_name", f"Team {rid}"),
                "avatar": rum.get(rid, {}).get("avatar"),
                "current_wins": base_wins.get(rid, 0),
                "avg_points": round(avg.get(rid, 0), 1),
                "remaining_games": len(games),
                "strength_of_schedule": sos,
                "sos_vs_league": round(sos - league_avg, 1),
                "projected_added_wins": round(proj_added_wins, 1),
                "projected_final_wins": round(
                    base_wins.get(rid, 0) + proj_added_wins, 1
                ),
                "playoff_probability_pct": round(odds.get(rid, 0) * 100, 1),
                "schedule": game_rows,
                "swing_matchups": [g for g in game_rows if g["swing"]],
            }
        )

    teams.sort(key=lambda t: t["projected_final_wins"], reverse=True)
    return {
        "week": current_week,
        "teams": teams,
        "note": (
            "Projections use each team's scoring mean/variance over completed "
            "weeks across the actual remaining schedule."
        ),
    }


# ---------------------------------------------------------------------------
# #97 Must-win flags
# ---------------------------------------------------------------------------


def must_win_flags(league_id: str, current_week: int) -> dict[str, Any]:
    """Flag upcoming games whose result most swings a team's playoff odds."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)

    sim = _simulate(league_id, current_week)
    sensitivity = sim["sensitivity"]
    odds = sim["odds"]
    next_game = sim["next_game"]

    flags: list[dict[str, Any]] = []
    for rid, (week, opp) in next_game.items():
        swing = sensitivity.get(rid, 0.0)
        if swing < 0.2:
            continue
        if swing >= 0.4:
            level = "must-win"
        else:
            level = "pivotal"
        flags.append(
            {
                "roster_id": rid,
                "team": rum.get(rid, {}).get("display_name", f"Team {rid}"),
                "week": week,
                "opponent": rum.get(opp, {}).get(
                    "display_name", f"Team {opp}"
                ),
                "playoff_probability_pct": round(odds.get(rid, 0) * 100, 1),
                "swing_pct": round(swing * 100, 1),
                "level": level,
            }
        )

    flags.sort(key=lambda f: f["swing_pct"], reverse=True)
    return {
        "week": current_week,
        "flags": flags,
        "note": (
            "Swing = P(make playoffs | win next) − P(make playoffs | lose next), "
            "from a Monte-Carlo simulation of the remaining schedule."
        ),
    }


# ---------------------------------------------------------------------------
# #98 Regression / luck warnings
# ---------------------------------------------------------------------------


def regression_warnings(
    league_id: str, current_week: int
) -> dict[str, Any]:
    """Flag teams whose record is out of step with their underlying scoring."""
    luck_rows = svc.stat_luck_adjusted_standings(league_id, current_week)
    allplay_rows = svc.stat_all_play_record(league_id, current_week)
    allplay_by_rid = {int(r["roster_id"]): r for r in allplay_rows}

    warnings: list[dict[str, Any]] = []
    for row in luck_rows:
        rid = int(row["roster_id"])
        actual = float(row["actual_wins"])
        expected = float(row["expected_wins"])
        luck = round(actual - expected, 2)

        ap = allplay_by_rid.get(rid, {})
        ap_w = ap.get("all_play_wins", 0)
        ap_l = ap.get("all_play_losses", 0)
        ap_total = ap_w + ap_l
        ap_pct = round(ap_w / ap_total * 100, 1) if ap_total else 0.0

        if luck >= 1.5:
            warnings.append(
                {
                    "roster_id": rid,
                    "team": row["display_name"],
                    "avatar": row.get("avatar"),
                    "type": "overperforming",
                    "emoji": "⚠️",
                    "luck_delta": luck,
                    "actual_wins": actual,
                    "expected_wins": expected,
                    "all_play_win_pct": ap_pct,
                    "detail": (
                        f"{row['display_name']} has {luck} more wins than their "
                        f"scoring suggests (all-play {ap_pct}%). Due for negative "
                        "regression."
                    ),
                }
            )
        elif luck <= -1.5:
            warnings.append(
                {
                    "roster_id": rid,
                    "team": row["display_name"],
                    "avatar": row.get("avatar"),
                    "type": "underperforming",
                    "emoji": "📈",
                    "luck_delta": luck,
                    "actual_wins": actual,
                    "expected_wins": expected,
                    "all_play_win_pct": ap_pct,
                    "detail": (
                        f"{row['display_name']} has {abs(luck)} fewer wins than "
                        f"their scoring suggests (all-play {ap_pct}%). Positive "
                        "regression is likely."
                    ),
                }
            )

    warnings.sort(key=lambda w: abs(w["luck_delta"]), reverse=True)
    return {
        "week": current_week,
        "warnings": warnings,
        "note": (
            "Compares actual wins to expected wins (from weekly scoring rank) and "
            "all-play win rate to spot lucky/unlucky records."
        ),
    }


# ---------------------------------------------------------------------------
# #99 Rivalry / trash-talk index
# ---------------------------------------------------------------------------


def rivalry_index(league_id: str, current_week: int) -> dict[str, Any]:
    """Score head-to-head rivalries and surface grudge matches & trash talk."""
    results, rum = nar._team_results(league_id, current_week)

    # Deduplicate games into unordered head-to-head pairs.
    seen: set[tuple[int, int, int]] = set()
    pair_stats: dict[tuple[int, int], dict[str, Any]] = {}
    for rid, history in results.items():
        for h in history:
            if h["opponent"] is None or h["opponent_points"] is None:
                continue
            # Find the opponent roster_id by name (results keyed by rid).
            opp_rid = next(
                (
                    orid
                    for orid in results
                    if nar._name(rum, orid) == h["opponent"]
                ),
                None,
            )
            if opp_rid is None:
                continue
            key = (min(rid, opp_rid), max(rid, opp_rid))
            dedupe = (key[0], key[1], h["week"])
            if dedupe in seen:
                continue
            seen.add(dedupe)
            margin = abs(h["points"] - h["opponent_points"])
            stat = pair_stats.setdefault(
                key,
                {
                    "meetings": 0,
                    "margins": [],
                    "wins": {key[0]: 0, key[1]: 0},
                    "last_week": 0,
                },
            )
            stat["meetings"] += 1
            stat["margins"].append(margin)
            stat["last_week"] = max(stat["last_week"], h["week"])
            winner = rid if h["points"] >= h["opponent_points"] else opp_rid
            stat["wins"][winner] += 1

    # Upcoming-week rematches become grudge matches.
    upcoming_week = current_week + 1
    upcoming_pairs: set[tuple[int, int]] = set()
    try:
        upcoming = svc.get_matchups(league_id, upcoming_week)
        by_mid: dict[Any, list[int]] = {}
        for m in upcoming:
            if m.get("roster_id") is None:
                continue
            by_mid.setdefault(m.get("matchup_id"), []).append(int(m["roster_id"]))
        for mid, rids in by_mid.items():
            if mid is not None and len(rids) >= 2:
                upcoming_pairs.add((min(rids[0], rids[1]), max(rids[0], rids[1])))
    except Exception:  # noqa: BLE001
        pass

    rivalries: list[dict[str, Any]] = []
    for (a, b), stat in pair_stats.items():
        meetings = stat["meetings"]
        avg_margin = sum(stat["margins"]) / len(stat["margins"])
        min_margin = min(stat["margins"])
        # Closer + more frequent + more recent = hotter rivalry.
        closeness = max(0.0, 30.0 - avg_margin)
        index = round(
            meetings * 10 + closeness + max(0.0, 20.0 - min_margin), 1
        )
        is_grudge = (a, b) in upcoming_pairs
        if is_grudge:
            index += 25
        wins_a, wins_b = stat["wins"][a], stat["wins"][b]
        name_a, name_b = nar._name(rum, a), nar._name(rum, b)
        if wins_a == wins_b:
            series = "dead even"
        elif wins_a > wins_b:
            series = f"{name_a} leads {wins_a}-{wins_b}"
        else:
            series = f"{name_b} leads {wins_b}-{wins_a}"
        rivalries.append(
            {
                "teams": [name_a, name_b],
                "roster_ids": [a, b],
                "meetings": meetings,
                "series": series,
                "avg_margin": round(avg_margin, 1),
                "closest_margin": round(min_margin, 1),
                "rivalry_index": round(index, 1),
                "grudge_match": is_grudge,
                "grudge_week": upcoming_week if is_grudge else None,
            }
        )

    rivalries.sort(key=lambda r: r["rivalry_index"], reverse=True)
    rivalries = rivalries[:12]

    trash_talk, ai_generated = _rivalry_trash_talk(rivalries)

    return {
        "week": current_week,
        "rivalries": rivalries,
        "trash_talk": trash_talk,
        "ai_enabled": nar.ai_enabled(),
        "ai_generated": ai_generated,
    }


def _rivalry_trash_talk(
    rivalries: list[dict[str, Any]],
) -> tuple[str, bool]:
    """A spicy blurb for the top rivalries (Claude when available)."""
    if not rivalries:
        return "No rivalries have formed yet — give it a few weeks.", False
    import json

    top = rivalries[:4]
    prompt = (
        "Write a short, spicy 'rivalry watch' segment for a fantasy football "
        "league. One or two sentences per rivalry, leaning into grudge matches. "
        "Facts as JSON:\n\n" + json.dumps(top, indent=2)
    )
    text = nar._generate_text(nar._RECAP_SYSTEM, prompt, max_tokens=600)
    if text:
        return text, True
    lines = []
    for r in top:
        line = (
            f"{r['teams'][0]} vs {r['teams'][1]} — {r['series']}, "
            f"closest decided by {r['closest_margin']}."
        )
        if r["grudge_match"]:
            line += f" They run it back in Week {r['grudge_week']}!"
        lines.append(line)
    return "\n".join(lines), False


# ---------------------------------------------------------------------------
# #100 Power-ranking committee — the model side
# ---------------------------------------------------------------------------


def power_ranking_model(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """Composite model power ranking (all-play %, expected wins, points-for)."""
    allplay = svc.stat_all_play_record(league_id, current_week)
    luck = svc.stat_luck_adjusted_standings(league_id, current_week)
    standings = nar._standings(league_id, current_week)

    ap_by_rid = {int(r["roster_id"]): r for r in allplay}
    exp_by_rid = {
        int(r["roster_id"]): float(r["expected_wins"]) for r in luck
    }

    max_exp = max(exp_by_rid.values(), default=1.0) or 1.0
    pts_values = [v["points_for"] for v in standings.values()]
    max_pts = max(pts_values, default=1.0) or 1.0

    scored: list[dict[str, Any]] = []
    for rid, st in standings.items():
        ap = ap_by_rid.get(rid, {})
        ap_w = ap.get("all_play_wins", 0)
        ap_l = ap.get("all_play_losses", 0)
        ap_total = ap_w + ap_l
        ap_pct = ap_w / ap_total if ap_total else 0.0
        exp_norm = exp_by_rid.get(rid, 0.0) / max_exp
        pts_norm = st["points_for"] / max_pts
        score = round(ap_pct * 0.4 + exp_norm * 0.3 + pts_norm * 0.3, 4)
        scored.append(
            {
                "roster_id": rid,
                "team": st["name"],
                "avatar": ap.get("avatar"),
                "power_score": score,
                "all_play_win_pct": round(ap_pct * 100, 1),
                "record": f"{st['wins']}-{st['losses']}"
                + (f"-{st['ties']}" if st["ties"] else ""),
                "points_for": st["points_for"],
            }
        )

    scored.sort(key=lambda x: x["power_score"], reverse=True)
    for i, row in enumerate(scored, start=1):
        row["model_rank"] = i
    return scored
