"""Player-level analytics for the Sleeper fantasy football integration.

Covers TODO section 2.2 (#51–58): boom/bust classification, positional scoring
breakdown, usage trends, points-above-replacement, buy-low/sell-high flags,
injury impact, rookie/breakout watch, and streaming value.

All weekly fantasy points are taken from league-scored ``players_points`` on the
matchup rows so every metric already respects the league's scoring settings.
Raw box-score usage (targets, snaps, touches) comes from the public
``/stats/nfl/player`` feed and is handled defensively because field coverage
varies by season and player.
"""

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.services import sleeper as svc

# Positions we bucket scoring into. Anything else falls back to "FLEX".
_POSITION_GROUPS = ("QB", "RB", "WR", "TE", "K", "DEF")
# injury_status values that mean the player is not fully available right now.
_INJURY_FLAGS = {"Questionable", "Doubtful", "Out", "IR", "PUP", "Sus", "NA", "DNR"}
_MIN_GAMES = 3


# ---------------------------------------------------------------------------
# Shared league/player context
# ---------------------------------------------------------------------------

@dataclass
class _PlayerContext:
    tw: list[dict[str, Any]]
    rum: dict[int, dict[str, Any]]
    players_meta: dict[str, Any]
    player_week_pts: dict[str, dict[int, float]]
    owner_by_pid: dict[str, int]
    starts_by_pid: dict[str, set[int]] = field(default_factory=dict)


def _season(league_id: str) -> str:
    """Best-effort current season string (e.g. ``"2024"``)."""
    try:
        season = svc.get_league(league_id).get("season")
        if season:
            return str(season)
    except httpx.HTTPError:
        pass
    try:
        return str(svc.get_nfl_state().get("season") or "")
    except httpx.HTTPError:
        return ""


def _build_context(league_id: str, current_week: int) -> _PlayerContext:
    all_matchups = svc._collect_all_matchups(league_id, current_week)
    tw = svc._team_week_table(all_matchups)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    players_meta = svc.get_nfl_players()

    player_week_pts: dict[str, dict[int, float]] = {}
    starts_by_pid: dict[str, set[int]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)
        for pid in row["starters"]:
            starts_by_pid.setdefault(pid, set()).add(row["week"])

    owner_by_pid: dict[str, int] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        for pid in r.get("players") or []:
            owner_by_pid[str(pid)] = rid

    return _PlayerContext(
        tw=tw,
        rum=rum,
        players_meta=players_meta,
        player_week_pts=player_week_pts,
        owner_by_pid=owner_by_pid,
        starts_by_pid=starts_by_pid,
    )


def _player_meta(ctx: _PlayerContext, pid: str) -> tuple[str, str, str | None, dict[str, Any]]:
    """Return ``(name, position, team, raw)`` for a player id."""
    raw = ctx.players_meta.get(pid) or {}
    name = (
        raw.get("full_name")
        or f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip()
        or f"Player {pid}"
    )
    position = raw.get("position") or next(iter(raw.get("fantasy_positions") or []), "?")
    return name, str(position), raw.get("team"), raw


def _owner_name(ctx: _PlayerContext, pid: str) -> str:
    rid = ctx.owner_by_pid.get(pid)
    if rid is None:
        return "Free Agent"
    return str(ctx.rum.get(rid, {}).get("display_name", f"Team {rid}"))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return float((sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5)


def _ordered_scores(ctx: _PlayerContext, pid: str) -> list[float]:
    weeks = ctx.player_week_pts.get(pid, {})
    return [weeks[w] for w in sorted(weeks)]


# ---------------------------------------------------------------------------
# #51 — Player consistency vs boom/bust (floor / ceiling)
# ---------------------------------------------------------------------------

def player_consistency(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Floor/ceiling profile and boom-bust classification for rostered players."""
    ctx = _build_context(league_id, current_week)
    rows: list[dict[str, Any]] = []
    for pid in ctx.owner_by_pid:
        scores = _ordered_scores(ctx, pid)
        if len(scores) < _MIN_GAMES:
            continue
        avg = _mean(scores)
        if avg <= 0:
            continue
        sd = _stdev(scores)
        cv = sd / avg if avg else 0.0
        boom = sum(1 for s in scores if s >= avg * 1.5)
        bust = sum(1 for s in scores if s <= avg * 0.5)
        if cv >= 0.6:
            classification = "Boom/Bust"
        elif cv <= 0.35:
            classification = "Consistent"
        else:
            classification = "Balanced"
        name, position, team, _ = _player_meta(ctx, pid)
        rows.append({
            "player_id": pid,
            "player_name": name,
            "position": position,
            "team": team,
            "display_name": _owner_name(ctx, pid),
            "games": len(scores),
            "avg_points": round(avg, 2),
            "floor": round(min(scores), 2),
            "ceiling": round(max(scores), 2),
            "volatility": round(sd, 2),
            "boom_rate_pct": round(boom / len(scores) * 100, 1),
            "bust_rate_pct": round(bust / len(scores) * 100, 1),
            "classification": classification,
        })
    rows.sort(key=lambda r: r["avg_points"], reverse=True)
    return rows[:75]


# ---------------------------------------------------------------------------
# #52 — Positional scoring breakdown per team
# ---------------------------------------------------------------------------

def positional_breakdown(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Share of each team's starting points by position group."""
    ctx = _build_context(league_id, current_week)
    per_team: dict[int, dict[str, float]] = {
        rid: dict.fromkeys((*_POSITION_GROUPS, "FLEX"), 0.0) for rid in ctx.rum
    }
    for row in ctx.tw:
        rid = row["roster_id"]
        if rid not in per_team:
            continue
        pp = row["players_points"]
        for pid in row["starters"]:
            pts = float(pp.get(pid, 0) or 0)
            _, position, _, _ = _player_meta(ctx, pid)
            group = position if position in _POSITION_GROUPS else "FLEX"
            per_team[rid][group] += pts

    result: list[dict[str, Any]] = []
    for rid, groups in per_team.items():
        total = sum(groups.values())
        user = ctx.rum.get(rid, {})
        entry: dict[str, Any] = {
            "roster_id": rid,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
            "total_points": round(total, 2),
        }
        for grp, pts in groups.items():
            entry[f"{grp.lower()}_points"] = round(pts, 2)
            entry[f"{grp.lower()}_pct"] = round(pts / total * 100, 1) if total else 0.0
        result.append(entry)
    result.sort(key=lambda r: r["total_points"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# #53 — Target share, snap share & usage trends
# ---------------------------------------------------------------------------

def usage_trends(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Touch/target/snap usage and recent-vs-early trend for rostered players."""
    ctx = _build_context(league_id, current_week)
    season = _season(league_id)

    weekly_stats: dict[str, list[dict[str, Any]]] = {}
    if season:
        for week in range(1, current_week + 1):
            try:
                wk_stats = svc.get_player_stats(season, week)
            except httpx.HTTPError:
                continue
            for pid, stats in wk_stats.items():
                if pid in ctx.owner_by_pid and isinstance(stats, dict):
                    weekly_stats.setdefault(pid, []).append({"week": week, **stats})

    rows: list[dict[str, Any]] = []
    for pid, weeks in weekly_stats.items():
        weeks.sort(key=lambda w: w["week"])
        targets = [float(w.get("rec_tgt", 0) or 0) for w in weeks]
        carries = [float(w.get("rush_att", 0) or 0) for w in weeks]
        snaps = [float(w.get("off_snp", 0) or 0) for w in weeks]
        team_snaps = [float(w.get("tm_off_snp", 0) or 0) for w in weeks]
        touches = [t + c for t, c in zip(targets, carries, strict=True)]
        games = sum(1 for w in weeks if (w.get("off_snp") or w.get("rec_tgt") or w.get("rush_att")))
        if games < _MIN_GAMES:
            continue

        total_snaps = sum(snaps)
        total_team_snaps = sum(team_snaps)
        snap_share = (total_snaps / total_team_snaps * 100) if total_team_snaps else None
        early = _mean(touches[:3])
        recent = _mean(touches[-3:])
        name, position, team, _ = _player_meta(ctx, pid)
        rows.append({
            "player_id": pid,
            "player_name": name,
            "position": position,
            "team": team,
            "display_name": _owner_name(ctx, pid),
            "games": games,
            "avg_touches": round(_mean(touches), 2),
            "avg_targets": round(_mean(targets), 2),
            "avg_snaps": round(_mean(snaps), 1),
            "snap_share_pct": round(snap_share, 1) if snap_share is not None else None,
            "usage_trend": round(recent - early, 2),
        })
    rows.sort(key=lambda r: r["avg_touches"], reverse=True)
    return rows[:75]


# ---------------------------------------------------------------------------
# #54 — Points above replacement (VOR / VORP) by position
# ---------------------------------------------------------------------------

def points_above_replacement(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Season points above a positional replacement baseline."""
    ctx = _build_context(league_id, current_week)
    n_teams = len(ctx.rum) or 1
    try:
        roster_positions = svc.get_league(league_id).get("roster_positions") or []
    except httpx.HTTPError:
        roster_positions = []

    # Starting slots per position; flex slots widen the RB/WR/TE pool.
    slots: dict[str, int] = dict.fromkeys(_POSITION_GROUPS, 0)
    flex = 0
    for pos in roster_positions:
        if pos in slots:
            slots[pos] += 1
        elif pos in ("FLEX", "WRRB_FLEX", "REC_FLEX", "WRRB_WRT"):
            flex += 1
        elif pos == "SUPER_FLEX":
            slots["QB"] += 1

    # Default starting slots when the league config is unavailable.
    if not any(slots.values()):
        slots.update({"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1})

    by_pos: dict[str, list[tuple[str, float]]] = {}
    for pid in ctx.owner_by_pid:
        scores = _ordered_scores(ctx, pid)
        if not scores:
            continue
        _, position, _, _ = _player_meta(ctx, pid)
        by_pos.setdefault(position, []).append((pid, sum(scores)))

    replacement: dict[str, float] = {}
    for position, entries in by_pos.items():
        entries.sort(key=lambda e: e[1], reverse=True)
        flex_bonus = flex if position in ("RB", "WR", "TE") else 0
        rank = n_teams * (slots.get(position, 1) + flex_bonus)
        idx = min(max(rank, 1), len(entries)) - 1
        replacement[position] = entries[idx][1]

    rows: list[dict[str, Any]] = []
    for position, entries in by_pos.items():
        base = replacement.get(position, 0.0)
        for pid, total in entries:
            name, _, team, _ = _player_meta(ctx, pid)
            rows.append({
                "player_id": pid,
                "player_name": name,
                "position": position,
                "team": team,
                "display_name": _owner_name(ctx, pid),
                "total_points": round(total, 2),
                "replacement_points": round(base, 2),
                "vorp": round(total - base, 2),
            })
    rows.sort(key=lambda r: r["vorp"], reverse=True)
    return rows[:75]


# ---------------------------------------------------------------------------
# #55 — Buy-low / sell-high candidate flags
# ---------------------------------------------------------------------------

def buy_low_sell_high(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Flag rostered players whose recent form diverges from their season pace."""
    ctx = _build_context(league_id, current_week)
    rows: list[dict[str, Any]] = []
    for pid in ctx.owner_by_pid:
        scores = _ordered_scores(ctx, pid)
        if len(scores) < 4:
            continue
        season_avg = _mean(scores)
        if season_avg <= 0:
            continue
        recent_avg = _mean(scores[-3:])
        delta = recent_avg - season_avg
        threshold = max(season_avg * 0.3, 3.0)
        if delta <= -threshold:
            flag = "Buy Low"
        elif delta >= threshold:
            flag = "Sell High"
        else:
            continue
        name, position, team, _ = _player_meta(ctx, pid)
        rows.append({
            "player_id": pid,
            "player_name": name,
            "position": position,
            "team": team,
            "display_name": _owner_name(ctx, pid),
            "season_avg": round(season_avg, 2),
            "recent_avg": round(recent_avg, 2),
            "delta": round(delta, 2),
            "flag": flag,
        })
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows[:75]


# ---------------------------------------------------------------------------
# #56 — Injury status timeline & games-missed impact per roster
# ---------------------------------------------------------------------------

def injury_impact(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Per-roster injury exposure and estimated points lost to missed games."""
    ctx = _build_context(league_id, current_week)
    per_roster: dict[int, dict[str, Any]] = {
        rid: {"injured": [], "games_missed": 0, "points_lost": 0.0}
        for rid in ctx.rum
    }
    for pid, rid in ctx.owner_by_pid.items():
        if rid not in per_roster:
            continue
        weeks = ctx.player_week_pts.get(pid, {})
        active = [pts for pts in weeks.values() if pts > 0]
        games_missed = max(0, current_week - len(active))
        avg_when_active = _mean(active)
        points_lost = avg_when_active * games_missed
        name, position, _, raw = _player_meta(ctx, pid)
        status = raw.get("injury_status")
        if status in _INJURY_FLAGS:
            per_roster[rid]["injured"].append({
                "player_name": name,
                "position": position,
                "status": status,
            })
        if games_missed and avg_when_active > 0:
            per_roster[rid]["games_missed"] += games_missed
            per_roster[rid]["points_lost"] += points_lost

    result: list[dict[str, Any]] = []
    for rid, data in per_roster.items():
        user = ctx.rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
            "injured_count": len(data["injured"]),
            "games_missed": data["games_missed"],
            "est_points_lost": round(data["points_lost"], 2),
            "injured": data["injured"],
        })
    result.sort(key=lambda r: r["est_points_lost"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# #57 — Rookie / breakout watch with usage acceleration
# ---------------------------------------------------------------------------

def rookie_breakout_watch(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Surface rookies and young players whose production is accelerating."""
    ctx = _build_context(league_id, current_week)
    rows: list[dict[str, Any]] = []
    for pid in ctx.owner_by_pid:
        scores = _ordered_scores(ctx, pid)
        if len(scores) < _MIN_GAMES:
            continue
        name, position, team, raw = _player_meta(ctx, pid)
        years_exp = raw.get("years_exp")
        years_exp = int(years_exp) if isinstance(years_exp, (int, float)) else None
        early = _mean(scores[:3])
        recent = _mean(scores[-3:])
        acceleration = recent - early
        is_rookie = years_exp == 0
        is_young = years_exp is not None and years_exp <= 2
        if not (is_rookie or (is_young and acceleration >= 2.0)):
            continue
        rows.append({
            "player_id": pid,
            "player_name": name,
            "position": position,
            "team": team,
            "display_name": _owner_name(ctx, pid),
            "years_exp": years_exp,
            "early_avg": round(early, 2),
            "recent_avg": round(recent, 2),
            "acceleration": round(acceleration, 2),
            "flag": "Rookie" if is_rookie else "Breakout",
        })
    rows.sort(key=lambda r: r["acceleration"], reverse=True)
    return rows[:60]


# ---------------------------------------------------------------------------
# #58 — Streaming value tracker for DST / K / QB
# ---------------------------------------------------------------------------

def streaming_tracker(league_id: str, current_week: int) -> list[dict[str, Any]]:
    """Rank QB/K/DEF options for matchup-based streaming by recent form."""
    ctx = _build_context(league_id, current_week)
    stream_positions = {"QB", "K", "DEF"}
    rows: list[dict[str, Any]] = []
    for pid in ctx.player_week_pts:
        name, position, team, _ = _player_meta(ctx, pid)
        if position not in stream_positions:
            continue
        scores = _ordered_scores(ctx, pid)
        if len(scores) < _MIN_GAMES:
            continue
        season_avg = _mean(scores)
        recent_avg = _mean(scores[-3:])
        consistency = _stdev(scores)
        # Reward recent form, lean on the season floor, penalise volatility.
        streaming_score = recent_avg * 0.6 + season_avg * 0.4 - consistency * 0.1
        rows.append({
            "player_id": pid,
            "player_name": name,
            "position": position,
            "team": team,
            "display_name": _owner_name(ctx, pid),
            "season_avg": round(season_avg, 2),
            "recent_avg": round(recent_avg, 2),
            "consistency": round(consistency, 2),
            "streaming_score": round(streaming_score, 2),
        })
    rows.sort(key=lambda r: r["streaming_score"], reverse=True)
    return rows[:60]
