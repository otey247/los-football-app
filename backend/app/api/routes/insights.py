"""API routes for AI-generated narrative insights & storytelling.

Covers the league's storytelling surface: weekly recaps (optionally auto-drafted
into the commissioner blog), upcoming-week matchup previews, weekly awards,
the season yearbook, auto-detected storylines, and natural-language Q&A.
"""

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.sleeper import _handle_sleeper_error, _requested_week
from app.core.config import settings
from app.models import BlogPost
from app.services import narrative as nar

router = APIRouter(prefix="/insights", tags=["insights"])


def _resolve_league(league_id: str) -> str:
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(
            status_code=400,
            detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured",
        )
    return lid


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "post"


@router.get("/meta")
def get_insights_meta() -> dict[str, Any]:
    """Describe the available insight features and whether AI is enabled."""
    return {
        "ai_enabled": nar.ai_enabled(),
        "features": [
            {
                "key": "weekly-recap",
                "title": "Weekly Recap",
                "description": "AI-written recap of the week's results, publishable to the blog.",
            },
            {
                "key": "matchup-previews",
                "title": "Matchup Previews",
                "description": "Storyline-driven previews of the upcoming week's matchups.",
            },
            {
                "key": "weekly-awards",
                "title": "Weekly Awards",
                "description": "Manager of the Week and other weekly superlatives with blurbs.",
            },
            {
                "key": "season-yearbook",
                "title": "Season Yearbook",
                "description": "Season-in-review with records and milestones.",
            },
            {
                "key": "storylines",
                "title": "Storylines",
                "description": "Auto-detected streaks, surges, collapses, and rivalries.",
            },
            {
                "key": "ask",
                "title": "Ask the League",
                "description": "Natural-language Q&A grounded in your league data.",
            },
        ],
    }


@router.get("/weekly-recap")
def get_weekly_recap(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#86 Weekly recap — facts + AI-written narrative."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        facts = nar.weekly_recap_facts(lid, wk)
        narrative, generated = nar.weekly_recap_narrative(facts)
        return {
            "week": wk,
            "ai_enabled": nar.ai_enabled(),
            "ai_generated": generated,
            "narrative": narrative,
            "facts": facts,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


class PublishRecapRequest(BaseModel):
    league_id: str = ""
    week: int | None = None
    publish: bool = False


@router.post("/weekly-recap/publish")
def publish_weekly_recap(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: PublishRecapRequest,
) -> Any:
    """#86 Auto-draft the weekly recap into the commissioner blog (super admin)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    lid = _resolve_league(body.league_id)
    wk = _requested_week(lid, body.week)
    try:
        facts = nar.weekly_recap_facts(lid, wk)
        narrative_text, _ = nar.weekly_recap_narrative(facts)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)
        return  # unreachable; _handle_sleeper_error always raises

    title = f"Week {wk} Recap"
    high = facts.get("high_score")
    excerpt = (
        f"{high['name']} led the way with {high['points']} points."
        if high
        else f"The Week {wk} results are in."
    )

    # Ensure a unique slug (one recap per week, but allow re-publishing).
    base_slug = _slugify(title)
    slug = base_slug
    n = 2
    while session.exec(select(BlogPost).where(BlogPost.slug == slug)).first():
        slug = f"{base_slug}-{n}"
        n += 1

    post = BlogPost(
        title=title,
        slug=slug,
        content=narrative_text,
        excerpt=excerpt[:500],
        published=body.publish,
        author_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return {
        "id": str(post.id),
        "slug": post.slug,
        "title": post.title,
        "published": post.published,
    }


@router.get("/matchup-previews")
def get_matchup_previews(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#87 Matchup previews for the upcoming week."""
    lid = _resolve_league(league_id)
    # Default to the week *after* the latest completed week.
    current = _requested_week(lid, None)
    wk = week if week is not None else min(current + 1, 18)
    try:
        facts = nar.matchup_preview_facts(lid, wk)
        narrative, generated = nar.matchup_preview_narrative(facts)
        return {
            "week": wk,
            "ai_enabled": nar.ai_enabled(),
            "ai_generated": generated,
            "narrative": narrative,
            "facts": facts,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/weekly-awards")
def get_weekly_awards(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#88 Manager of the Week & weekly superlatives."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        awards = nar.weekly_awards_facts(lid, wk)
        narrative, generated = nar.weekly_awards_narrative(wk, awards)
        return {
            "week": wk,
            "ai_enabled": nar.ai_enabled(),
            "ai_generated": generated,
            "narrative": narrative,
            "awards": awards,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/season-yearbook")
def get_season_yearbook(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#89 Season-in-review yearbook with milestones."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        facts = nar.season_yearbook_facts(lid, wk)
        narrative, generated = nar.season_yearbook_narrative(facts)
        return {
            "through_week": wk,
            "ai_enabled": nar.ai_enabled(),
            "ai_generated": generated,
            "narrative": narrative,
            "facts": facts,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/storylines")
def get_storylines(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#91 Auto-detected storylines (streaks, surges, collapses, rivalries)."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return {"week": wk, "storylines": nar.storylines_facts(lid, wk)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


class AskRequest(BaseModel):
    question: str
    league_id: str = ""
    week: int | None = None


@router.post("/ask")
def ask_the_league(body: AskRequest) -> Any:
    """#90 Natural-language Q&A grounded in league data."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="A question is required")
    lid = _resolve_league(body.league_id)
    wk = _requested_week(lid, body.week)
    try:
        return nar.answer_question(lid, wk, question)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)
