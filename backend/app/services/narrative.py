"""AI-powered narrative & storytelling layer for the league.

This service turns raw Sleeper data into the structured facts behind each
"storytelling" feature (weekly recaps, matchup previews, weekly awards,
season yearbook, auto-detected storylines, and natural-language Q&A) and then
renders those facts into prose.

Narrative prose is generated with Claude (Anthropic) when ``ANTHROPIC_API_KEY``
is configured. When it is not — or if the Claude call fails — every feature
gracefully falls back to a deterministic, template-based narrative so the app
keeps working without an API key.
"""

import json
import logging
from typing import Any

from app.core.config import settings
from app.services import sleeper as svc

logger = logging.getLogger(__name__)

# Max tokens for a narrative generation. Recaps/previews are a few paragraphs,
# comfortably under the streaming threshold so a plain create() call is fine.
_NARRATIVE_MAX_TOKENS = 1500
_ANSWER_MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Claude text generation (with graceful template fallback)
# ---------------------------------------------------------------------------

def ai_enabled() -> bool:
    """Whether Claude-backed narratives are available."""
    return settings.ai_insights_enabled


def _generate_text(system: str, prompt: str, max_tokens: int = _NARRATIVE_MAX_TOKENS) -> str | None:
    """Generate prose with Claude. Returns ``None`` when AI is unavailable.

    The import is lazy and wrapped in a broad ``except`` so a missing package,
    a missing key, or a transient API error never breaks the endpoint — callers
    fall back to a deterministic template instead.
    """
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        logger.warning("Claude narrative generation failed, using template: %s", exc)
        return None


_RECAP_SYSTEM = (
    "You are the commissioner and resident hype-writer for a fantasy football "
    "league. You write punchy, funny, slightly trash-talky recaps and previews "
    "that name managers by their team name. Keep it vivid but grounded in the "
    "numbers you are given — never invent stats. Use short paragraphs. Do not "
    "use markdown headers; write flowing prose with the occasional bold team "
    "name."
)

_QA_SYSTEM = (
    "You are a fantasy football analyst answering questions about a specific "
    "league. Answer ONLY from the league data provided in the prompt. If the "
    "data does not contain the answer, say so plainly. Be concise and cite the "
    "specific numbers (scores, records, names) that support your answer."
)


# ---------------------------------------------------------------------------
# Shared league context
# ---------------------------------------------------------------------------

def _name(rum: dict[int, dict[str, Any]], rid: int) -> str:
    user = rum.get(rid, {})
    return user.get("display_name") or f"Team {rid}"


def _matchup_pairs(
    week_matchups: list[dict[str, Any]], rum: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Group a week's matchup rows into head-to-head pairs."""
    by_mid: dict[Any, list[dict[str, Any]]] = {}
    for m in week_matchups:
        if m.get("roster_id") is None:
            continue
        by_mid.setdefault(m.get("matchup_id"), []).append(m)

    pairs: list[dict[str, Any]] = []
    for mid, rows in by_mid.items():
        if mid is None or len(rows) < 2:
            continue
        a, b = rows[0], rows[1]
        a_rid, b_rid = int(a["roster_id"]), int(b["roster_id"])
        a_pts = float(a.get("points") or 0)
        b_pts = float(b.get("points") or 0)
        if a_pts >= b_pts:
            win_rid, win_pts, lose_rid, lose_pts = a_rid, a_pts, b_rid, b_pts
        else:
            win_rid, win_pts, lose_rid, lose_pts = b_rid, b_pts, a_rid, a_pts
        pairs.append(
            {
                "matchup_id": mid,
                "winner": _name(rum, win_rid),
                "winner_points": round(win_pts, 2),
                "loser": _name(rum, lose_rid),
                "loser_points": round(lose_pts, 2),
                "margin": round(win_pts - lose_pts, 2),
                "tie": a_pts == b_pts,
            }
        )
    return pairs


def _standings(
    league_id: str, through_week: int
) -> dict[int, dict[str, Any]]:
    """Wins / losses / points-for per roster through ``through_week``."""
    all_matchups = svc._collect_all_matchups(league_id, through_week)
    tw = svc._team_week_table(all_matchups)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)

    table: dict[int, dict[str, Any]] = {
        r["roster_id"]: {
            "roster_id": r["roster_id"],
            "name": _name(rum, r["roster_id"]),
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
        }
        for r in rosters
    }
    for week in all_matchups:
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            rid = row["roster_id"]
            if rid not in table:
                continue
            table[rid]["points_for"] += row["points"]
            result = svc._resolve_result(
                rid, row["matchup_id"], row["points"], week_rows
            )
            if result == "W":
                table[rid]["wins"] += 1
            elif result == "L":
                table[rid]["losses"] += 1
            else:
                table[rid]["ties"] += 1
    for v in table.values():
        v["points_for"] = round(v["points_for"], 2)
    return table


def _team_results(
    league_id: str, through_week: int
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, dict[str, Any]]]:
    """Chronological per-team results plus the roster->user map."""
    all_matchups = svc._collect_all_matchups(league_id, through_week)
    tw = svc._team_week_table(all_matchups)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)

    results: dict[int, list[dict[str, Any]]] = {r["roster_id"]: [] for r in rosters}
    for week in sorted(all_matchups):
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            rid = row["roster_id"]
            if rid not in results:
                continue
            opponent = next(
                (
                    o
                    for o in week_rows
                    if o["matchup_id"] == row["matchup_id"] and o["roster_id"] != rid
                ),
                None,
            )
            results[rid].append(
                {
                    "week": week,
                    "points": round(row["points"], 2),
                    "result": svc._resolve_result(
                        rid, row["matchup_id"], row["points"], week_rows
                    ),
                    "opponent": _name(rum, opponent["roster_id"]) if opponent else None,
                    "opponent_points": round(opponent["points"], 2) if opponent else None,
                }
            )
    return results, rum


# ---------------------------------------------------------------------------
# Feature data builders (deterministic facts)
# ---------------------------------------------------------------------------

def weekly_recap_facts(league_id: str, week: int) -> dict[str, Any]:
    """#86 facts: every result, plus the week's superlative games."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    week_matchups = svc.get_matchups(league_id, week)
    pairs = _matchup_pairs(week_matchups, rum)

    scores: list[dict[str, Any]] = [
        {"name": _name(rum, int(m["roster_id"])), "points": round(float(m.get("points") or 0), 2)}
        for m in week_matchups
        if m.get("roster_id") is not None
    ]
    scores.sort(key=lambda x: x["points"], reverse=True)

    blowout = max(pairs, key=lambda p: p["margin"], default=None)
    nailbiter = min(
        (p for p in pairs if not p["tie"]), key=lambda p: p["margin"], default=None
    )

    return {
        "week": week,
        "matchups": pairs,
        "high_score": scores[0] if scores else None,
        "low_score": scores[-1] if scores else None,
        "biggest_blowout": blowout,
        "closest_game": nailbiter,
    }


def matchup_preview_facts(league_id: str, week: int) -> dict[str, Any]:
    """#87 facts: upcoming pairings with each team's form."""
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    week_matchups = svc.get_matchups(league_id, week)

    standings = _standings(league_id, max(week - 1, 1))
    results, _ = _team_results(league_id, max(week - 1, 1))

    def team_form(rid: int) -> dict[str, Any]:
        st = standings.get(rid, {})
        history = results.get(rid, [])
        played = [h for h in history if h["result"] in ("W", "L", "T")]
        avg = round(sum(h["points"] for h in played) / len(played), 2) if played else 0.0
        last3 = "".join(h["result"] for h in history[-3:]) or "—"
        return {
            "name": _name(rum, rid),
            "record": f"{st.get('wins', 0)}-{st.get('losses', 0)}",
            "avg_points": avg,
            "last3": last3,
        }

    by_mid: dict[Any, list[int]] = {}
    for m in week_matchups:
        if m.get("roster_id") is None:
            continue
        by_mid.setdefault(m.get("matchup_id"), []).append(int(m["roster_id"]))

    previews = []
    for mid, rids in by_mid.items():
        if mid is None or len(rids) < 2:
            continue
        previews.append({"home": team_form(rids[0]), "away": team_form(rids[1])})

    return {"week": week, "matchups": previews}


def weekly_awards_facts(league_id: str, week: int) -> list[dict[str, Any]]:
    """#88 facts: superlatives with narrative-ready blurbs."""
    recap = weekly_recap_facts(league_id, week)

    # Biggest bench blunder of the week (reuse optimal-score logic).
    week_matchups = svc.get_matchups(league_id, week)
    rosters = svc.get_rosters(league_id)
    users = svc.get_users(league_id)
    rum = svc._roster_user_map(rosters, users)
    worst_bench: dict[str, Any] | None = None
    for m in week_matchups:
        if m.get("roster_id") is None:
            continue
        rid = int(m["roster_id"])
        actual = float(m.get("points") or 0)
        optimal = svc._optimal_score(
            m.get("starters") or [], m.get("players") or [], m.get("players_points") or {}
        )
        gap = round(max(0.0, optimal - actual), 2)
        if worst_bench is None or gap > worst_bench["points"]:
            worst_bench = {"name": _name(rum, rid), "points": gap}

    awards: list[dict[str, Any]] = []
    if recap["high_score"]:
        awards.append(
            {
                "award": "Team of the Week",
                "emoji": "🏆",
                "team": recap["high_score"]["name"],
                "detail": f"League-high {recap['high_score']['points']} points",
            }
        )
    if recap["low_score"]:
        awards.append(
            {
                "award": "Cupcake of the Week",
                "emoji": "🧁",
                "team": recap["low_score"]["name"],
                "detail": f"League-low {recap['low_score']['points']} points",
            }
        )
    if recap["biggest_blowout"]:
        b = recap["biggest_blowout"]
        awards.append(
            {
                "award": "Beatdown of the Week",
                "emoji": "💥",
                "team": b["winner"],
                "detail": f"Won by {b['margin']} over {b['loser']}",
            }
        )
    if recap["closest_game"]:
        c = recap["closest_game"]
        awards.append(
            {
                "award": "Heart Attack of the Week",
                "emoji": "😰",
                "team": c["winner"],
                "detail": f"Survived {c['loser']} by just {c['margin']}",
            }
        )
    if worst_bench and worst_bench["points"] > 0:
        awards.append(
            {
                "award": "Bench Blunder of the Week",
                "emoji": "🪑",
                "team": worst_bench["name"],
                "detail": f"Left {worst_bench['points']} points on the bench",
            }
        )
    return awards


def season_yearbook_facts(league_id: str, through_week: int) -> dict[str, Any]:
    """#89 facts: season-long records and milestones."""
    standings = _standings(league_id, through_week)
    results, rum = _team_results(league_id, through_week)

    table = sorted(
        standings.values(), key=lambda x: (x["wins"], x["points_for"]), reverse=True
    )

    # Best / worst single-game scores across the season.
    best_game: dict[str, Any] | None = None
    worst_game: dict[str, Any] | None = None
    longest_streak: dict[str, Any] | None = None
    for rid, history in results.items():
        for h in history:
            if best_game is None or h["points"] > best_game["points"]:
                best_game = {"name": _name(rum, rid), "week": h["week"], "points": h["points"]}
            if h["points"] > 0 and (worst_game is None or h["points"] < worst_game["points"]):
                worst_game = {"name": _name(rum, rid), "week": h["week"], "points": h["points"]}
        # longest win streak
        streak = best = 0
        for h in history:
            streak = streak + 1 if h["result"] == "W" else 0
            best = max(best, streak)
        if best and (longest_streak is None or best > longest_streak["streak"]):
            longest_streak = {"name": _name(rum, rid), "streak": best}

    points_leader = max(table, key=lambda x: x["points_for"], default=None) if table else None

    return {
        "through_week": through_week,
        "standings": table,
        "leader": table[0] if table else None,
        "points_leader": points_leader,
        "best_game": best_game,
        "worst_game": worst_game,
        "longest_win_streak": longest_streak,
    }


def storylines_facts(league_id: str, through_week: int) -> list[dict[str, Any]]:
    """#91 facts: auto-detected streaks, surges, collapses, and rivalries."""
    results, rum = _team_results(league_id, through_week)
    stories: list[dict[str, Any]] = []

    for rid, history in results.items():
        played = [h for h in history if h["result"] in ("W", "L", "T")]
        if not played:
            continue
        name = _name(rum, rid)

        # Current streak.
        last = played[-1]["result"]
        streak = 0
        for h in reversed(played):
            if h["result"] == last:
                streak += 1
            else:
                break
        if last == "W" and streak >= 3:
            stories.append(
                {
                    "type": "hot_streak",
                    "emoji": "🔥",
                    "title": f"{name} is rolling",
                    "detail": f"Winners of {streak} straight and surging up the standings.",
                    "teams": [name],
                }
            )
        elif last == "L" and streak >= 3:
            stories.append(
                {
                    "type": "cold_streak",
                    "emoji": "🥶",
                    "title": f"{name} is in free fall",
                    "detail": f"Losers of {streak} in a row and looking for answers.",
                    "teams": [name],
                }
            )

        # Surge / collapse: recent form vs season average.
        if len(played) >= 5:
            season_avg = sum(h["points"] for h in played) / len(played)
            recent_avg = sum(h["points"] for h in played[-3:]) / 3
            delta = recent_avg - season_avg
            if delta >= 15:
                stories.append(
                    {
                        "type": "surging",
                        "emoji": "📈",
                        "title": f"{name} is heating up",
                        "detail": (
                            f"Averaging {round(recent_avg, 1)} over the last 3 weeks, "
                            f"{round(delta, 1)} above their season pace."
                        ),
                        "teams": [name],
                    }
                )
            elif delta <= -15:
                stories.append(
                    {
                        "type": "fading",
                        "emoji": "📉",
                        "title": f"{name} is cooling off",
                        "detail": (
                            f"Down to {round(recent_avg, 1)} per week lately, "
                            f"{round(abs(delta), 1)} below their season pace."
                        ),
                        "teams": [name],
                    }
                )

    # Rivalry: closest single game of the season.
    closest = None
    for rid, history in results.items():
        for h in history:
            if h["opponent"] is None or h["result"] != "W":
                continue
            margin = round(h["points"] - (h["opponent_points"] or 0), 2)
            if closest is None or margin < closest["margin"]:
                closest = {
                    "margin": margin,
                    "week": h["week"],
                    "winner": _name(rum, rid),
                    "loser": h["opponent"],
                }
    if closest:
        stories.append(
            {
                "type": "rivalry",
                "emoji": "⚔️",
                "title": f"Instant classic: {closest['winner']} vs {closest['loser']}",
                "detail": (
                    f"Week {closest['week']} came down to {closest['margin']} points — "
                    "the tightest finish of the season so far."
                ),
                "teams": [closest["winner"], closest["loser"]],
            }
        )

    return stories


# ---------------------------------------------------------------------------
# Narrative renderers (Claude with template fallback)
# ---------------------------------------------------------------------------

def weekly_recap_narrative(facts: dict[str, Any]) -> str:
    prompt = (
        f"Write a Week {facts['week']} fantasy football recap for the league. "
        "Open with the headline result, cover the standout performances, and "
        "close with a line of trash talk. Here are the facts as JSON:\n\n"
        f"{json.dumps(facts, indent=2)}"
    )
    text = _generate_text(_RECAP_SYSTEM, prompt)
    if text:
        return text

    lines = [f"Week {facts['week']} is in the books. Here's how it shook out."]
    for m in facts["matchups"]:
        if m["tie"]:
            lines.append(f"{m['winner']} and {m['loser']} fought to a {m['winner_points']} tie.")
        else:
            lines.append(
                f"{m['winner']} beat {m['loser']}, {m['winner_points']}–{m['loser_points']}."
            )
    if facts["high_score"]:
        lines.append(
            f"\n{facts['high_score']['name']} led the league with "
            f"{facts['high_score']['points']} points."
        )
    if facts["biggest_blowout"]:
        b = facts["biggest_blowout"]
        lines.append(
            f"The beatdown of the week: {b['winner']} hung {b['margin']} on {b['loser']}."
        )
    if facts["closest_game"]:
        c = facts["closest_game"]
        lines.append(
            f"The nail-biter: {c['winner']} edged {c['loser']} by just {c['margin']}."
        )
    return "\n".join(lines)


def matchup_preview_narrative(facts: dict[str, Any]) -> str:
    prompt = (
        f"Write punchy previews for the Week {facts['week']} matchups. One short "
        "paragraph per game, highlighting form and the key storyline. Facts as "
        f"JSON:\n\n{json.dumps(facts, indent=2)}"
    )
    text = _generate_text(_RECAP_SYSTEM, prompt)
    if text:
        return text

    lines = [f"Looking ahead to Week {facts['week']}:"]
    for m in facts["matchups"]:
        h, a = m["home"], m["away"]
        lines.append(
            f"\n{h['name']} ({h['record']}, {h['avg_points']} ppg, last 3: {h['last3']}) "
            f"vs {a['name']} ({a['record']}, {a['avg_points']} ppg, last 3: {a['last3']})."
        )
    return "\n".join(lines)


def weekly_awards_narrative(week: int, awards: list[dict[str, Any]]) -> str:
    if not awards:
        return f"No awards to hand out for Week {week} yet."
    prompt = (
        f"Write a short, funny Week {week} awards blurb (one sentence per award) "
        "based on these winners. Facts as JSON:\n\n"
        f"{json.dumps(awards, indent=2)}"
    )
    text = _generate_text(_RECAP_SYSTEM, prompt, max_tokens=800)
    if text:
        return text
    return "\n".join(
        f"{a['emoji']} {a['award']}: {a['team']} — {a['detail']}." for a in awards
    )


def season_yearbook_narrative(facts: dict[str, Any]) -> str:
    prompt = (
        "Write a season-in-review 'yearbook' summary for the league through "
        f"Week {facts['through_week']}: celebrate the leader, the records, and "
        "the milestones. Facts as JSON:\n\n"
        f"{json.dumps(facts, indent=2)}"
    )
    text = _generate_text(_RECAP_SYSTEM, prompt)
    if text:
        return text

    lines = [f"The league through Week {facts['through_week']}:"]
    if facts["leader"]:
        lines.append(
            f"{facts['leader']['name']} sits atop the standings at "
            f"{facts['leader']['wins']}-{facts['leader']['losses']}."
        )
    if facts["points_leader"]:
        lines.append(
            f"{facts['points_leader']['name']} has scored the most points "
            f"({facts['points_leader']['points_for']})."
        )
    if facts["best_game"]:
        g = facts["best_game"]
        lines.append(f"Best single game: {g['name']} dropped {g['points']} in Week {g['week']}.")
    if facts["longest_win_streak"]:
        s = facts["longest_win_streak"]
        lines.append(f"Longest win streak: {s['name']} at {s['streak']} games.")
    return "\n".join(lines)


def answer_question(league_id: str, through_week: int, question: str) -> dict[str, Any]:
    """#90 natural-language Q&A grounded in league data."""
    context = {
        "through_week": through_week,
        "standings": season_yearbook_facts(league_id, through_week)["standings"],
        "latest_week": weekly_recap_facts(league_id, through_week),
        "storylines": storylines_facts(league_id, through_week),
    }
    if not ai_enabled():
        return {
            "question": question,
            "answer": (
                "Ask-the-League chat needs an Anthropic API key configured on the "
                "server (ANTHROPIC_API_KEY). Until then, browse the standings, "
                "recaps, and storylines tabs for the data."
            ),
            "ai_enabled": False,
        }
    prompt = (
        f"League data (JSON):\n{json.dumps(context, indent=2)}\n\n"
        f"Question: {question}"
    )
    text = _generate_text(_QA_SYSTEM, prompt, max_tokens=_ANSWER_MAX_TOKENS)
    return {
        "question": question,
        "answer": text or "I couldn't generate an answer right now. Try again shortly.",
        "ai_enabled": True,
    }
