"""Minimal, rate-aware, read-only client for the Sleeper Fantasy Football API.

Sleeper's public API requires no authentication and is read-only. The two main
concerns are (1) not hammering the rate limit (~1,000 calls/min) and (2) not
fetching the large ``players/nfl`` payload more than once per day. This client
handles client-side throttling and timeouts; pair it with a daily player cache
(see ``references/player-cache-strategy.md``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class SleeperConfig:
    base_url: str = "https://api.sleeper.app/v1"
    timeout_seconds: int = 20
    # Soft client-side throttle. ~20 req/s stays far under the 1,000/min guidance.
    min_request_interval_seconds: float = 0.05
    max_retries: int = 3


class SleeperClient:
    def __init__(self, config: SleeperConfig | None = None) -> None:
        self.config = config or SleeperConfig()
        self._session = requests.Session()
        self._last_request_at = 0.0

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        wait = self.config.min_request_interval_seconds - (
            time.time() - self._last_request_at
        )
        if wait > 0:
            time.sleep(wait)

        url = f"{self.config.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self._session.get(
                    url, params=params, timeout=self.config.timeout_seconds
                )
                self._last_request_at = time.time()
                if response.status_code == 429:
                    # Backoff and retry on rate limiting / block risk.
                    time.sleep(2**attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                time.sleep(2**attempt)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Sleeper request failed after retries: {url}")

    # --- Users & leagues -------------------------------------------------
    def get_user(self, username_or_user_id: str) -> dict[str, Any]:
        return self._get(f"/user/{username_or_user_id}")

    def get_user_leagues(
        self, user_id: str, season: str, sport: str = "nfl"
    ) -> list[dict[str, Any]]:
        return self._get(f"/user/{user_id}/leagues/{sport}/{season}")

    def get_league(self, league_id: str) -> dict[str, Any]:
        return self._get(f"/league/{league_id}")

    def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/rosters")

    def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/users")

    # --- Matchups, transactions, picks, brackets -------------------------
    def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/matchups/{week}")

    def get_transactions(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/transactions/{week}")

    def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/traded_picks")

    def get_winners_bracket(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/winners_bracket")

    def get_losers_bracket(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/losers_bracket")

    # --- State & drafts --------------------------------------------------
    def get_nfl_state(self) -> dict[str, Any]:
        return self._get("/state/nfl")

    def get_league_drafts(self, league_id: str) -> list[dict[str, Any]]:
        return self._get(f"/league/{league_id}/drafts")

    def get_user_drafts(
        self, user_id: str, season: str, sport: str = "nfl"
    ) -> list[dict[str, Any]]:
        return self._get(f"/user/{user_id}/drafts/{sport}/{season}")

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return self._get(f"/draft/{draft_id}")

    def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return self._get(f"/draft/{draft_id}/picks")

    def get_draft_traded_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return self._get(f"/draft/{draft_id}/traded_picks")

    # --- Players ---------------------------------------------------------
    def get_players(self, sport: str = "nfl") -> dict[str, Any]:
        """Large payload. Call at most once per day and cache the result."""
        return self._get(f"/players/{sport}")

    def get_trending_players(
        self,
        trend_type: str,
        sport: str = "nfl",
        lookback_hours: int = 24,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if trend_type not in {"add", "drop"}:
            raise ValueError("trend_type must be 'add' or 'drop'")
        return self._get(
            f"/players/{sport}/trending/{trend_type}",
            params={"lookback_hours": lookback_hours, "limit": limit},
        )


if __name__ == "__main__":
    client = SleeperClient()
    state = client.get_nfl_state()
    print(f"Season {state['season']} ({state['season_type']}), week {state['week']}")
