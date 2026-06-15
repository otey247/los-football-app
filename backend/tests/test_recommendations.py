"""Unit tests for the recommendation engine (TODO items 92-100).

These exercise the pure analytics in ``app.services.recommendations`` against a
small in-memory league by monkeypatching the Sleeper service getters, so they
need no network access.
"""

from typing import Any

import pytest

from app.services import recommendations as rec
from app.services import sleeper as svc

_LEAGUE: dict[str, Any] = {
    "settings": {"playoff_week_start": 15, "playoff_teams": 2},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN"],
}
_USERS = [
    {"user_id": "u1", "display_name": "Alpha", "avatar": None},
    {"user_id": "u2", "display_name": "Bravo", "avatar": None},
]
_ROSTERS = [
    {
        "roster_id": 1,
        "owner_id": "u1",
        "players": ["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "rb3", "wr3"],
    },
    {
        "roster_id": 2,
        "owner_id": "u2",
        "players": ["qb2", "rb4", "wr4", "wr5", "te2", "k2"],
    },
]
_PLAYERS: dict[str, Any] = {
    "qb1": {"full_name": "QB One", "fantasy_positions": ["QB"], "team": "AAA"},
    "rb1": {"full_name": "RB One", "fantasy_positions": ["RB"], "team": "AAA"},
    "rb2": {"full_name": "RB Two", "fantasy_positions": ["RB"], "team": "AAA"},
    "rb3": {"full_name": "RB Three", "fantasy_positions": ["RB"], "team": "AAA"},
    "wr1": {"full_name": "WR One", "fantasy_positions": ["WR"], "team": "AAA"},
    "wr2": {"full_name": "WR Two", "fantasy_positions": ["WR"], "team": "AAA"},
    "wr3": {
        "full_name": "WR Three",
        "fantasy_positions": ["WR"],
        "team": "AAA",
        "injury_status": "Out",
    },
    "te1": {"full_name": "TE One", "fantasy_positions": ["TE"], "team": "AAA"},
    "qb2": {"full_name": "QB Two", "fantasy_positions": ["QB"], "team": "BBB"},
    "rb4": {"full_name": "RB Four", "fantasy_positions": ["RB"], "team": "BBB"},
    "wr4": {"full_name": "WR Four", "fantasy_positions": ["WR"], "team": "BBB"},
    "wr5": {"full_name": "WR Five", "fantasy_positions": ["WR"], "team": "BBB"},
    "te2": {"full_name": "TE Two", "fantasy_positions": ["TE"], "team": "BBB"},
    "k2": {"full_name": "K Two", "fantasy_positions": ["K"], "team": "BBB"},
    "freeRB": {"full_name": "Free Back", "fantasy_positions": ["RB"], "team": "CCC"},
}
_PP = {
    "qb1": 25, "rb1": 20, "rb2": 15, "rb3": 18, "wr1": 14, "wr2": 10,
    "wr3": 30, "te1": 8, "qb2": 12, "rb4": 9, "wr4": 7, "wr5": 5,
    "te2": 4, "k2": 6,
}


def _matchups(_league_id: str, week: int) -> list[dict[str, Any]]:
    if week > 3:  # future weeks: pairing rows only
        return [
            {"roster_id": 1, "matchup_id": 1, "points": 0, "starters": [],
             "players": [], "players_points": {}},
            {"roster_id": 2, "matchup_id": 1, "points": 0, "starters": [],
             "players": [], "players_points": {}},
        ]
    rows = []
    for r in _ROSTERS:
        pts = sum(_PP.get(p, 0) for p in r["players"][:6]) + week
        rows.append(
            {
                "roster_id": r["roster_id"],
                "matchup_id": 1,
                "points": float(pts),
                "starters": r["players"][:6],
                "players": r["players"],
                "players_points": {p: float(_PP.get(p, 0)) for p in r["players"]},
            }
        )
    return rows


@pytest.fixture(autouse=True)
def _patch_sleeper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "get_league", lambda lid: _LEAGUE)
    monkeypatch.setattr(svc, "get_users", lambda lid: _USERS)
    monkeypatch.setattr(svc, "get_rosters", lambda lid: _ROSTERS)
    monkeypatch.setattr(svc, "get_nfl_players", lambda: _PLAYERS)
    monkeypatch.setattr(svc, "get_matchups", _matchups)
    monkeypatch.setattr(
        svc,
        "get_trending_players",
        lambda *a, **k: [{"player_id": "freeRB", "count": 500},
                         {"player_id": "wr4", "count": 300}],
    )


def test_start_sit_benches_injured_and_fills_flex() -> None:
    res = rec.start_sit_recommendations("L", 1, 3)
    names = {s["name"] for s in res["starters"]}
    # 7 starting slots: QB, RB, RB, WR, WR, TE, FLEX
    assert len(res["starters"]) == 7
    # The highest-raw player is Out and must not start.
    assert "WR Three" not in names
    # The FLEX should take the best remaining RB/WR/TE (RB Two at 15).
    flex = next(s for s in res["starters"] if s["slot"] == "FLEX")
    assert flex["name"] == "RB Two"


def test_waiver_suggestions_respect_availability_and_need() -> None:
    res = rec.waiver_suggestions("L", 2, 3)
    sugg_names = {s["name"] for s in res["suggestions"]}
    # An available free agent is suggested; a rostered trending player is not.
    assert "Free Back" in sugg_names
    assert "WR Four" not in sugg_names
    assert {n["position"] for n in res["needs"]}  # weaker team has needs


def test_power_ranking_model_orders_stronger_team_first() -> None:
    model = rec.power_ranking_model("L", 3)
    assert model[0]["team"] == "Alpha"
    assert model[0]["model_rank"] == 1
    assert model[1]["model_rank"] == 2


def test_lineup_nudges_flag_empty_slots() -> None:
    res = rec.lineup_nudges("L", 3)
    flagged = {n["team"] for n in res["nudges"]}
    # Bravo only has 6 players for 7 starting slots.
    assert "Bravo" in flagged


def test_rivalry_index_detects_repeat_matchup() -> None:
    res = rec.rivalry_index("L", 3)
    assert res["rivalries"]
    top = res["rivalries"][0]
    assert top["meetings"] == 3
    assert set(top["teams"]) == {"Alpha", "Bravo"}


def test_rest_of_season_includes_all_teams() -> None:
    res = rec.rest_of_season_outlook("L", 3)
    assert {t["team"] for t in res["teams"]} == {"Alpha", "Bravo"}
    for t in res["teams"]:
        assert t["remaining_games"] > 0
