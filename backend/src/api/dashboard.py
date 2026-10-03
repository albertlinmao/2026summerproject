"""US1 endpoint: GET /analytics/dashboard — role-based widget data aggregation.

Identity follows ``specs/001-analytics-dashboard/identity-contract.md``. Two things
this endpoint must not repeat from the old model:

* It must not read a scalar ``club_id`` claim. A person can belong to several
  clubs, so the club is either passed explicitly or resolved from active
  membership, and an unauthorized club is rejected rather than silently swapped.
* It must not treat a swimmer's own id as ``athlete_ids[0] or user_id``. The
  caller's own analytics are keyed on ``person_id``, which exists whether or not
  they have an account.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.auth import STAFF_ROLES, get_current_user
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_club(user: Dict[str, Any], requested: Optional[str]) -> Optional[str]:
    """Pick the club to render, and reject one the caller does not hold.

    Returning 403 on an unknown club matters: silently falling back to the
    caller's first club would show a coach of club A the dashboard for club B.
    """
    memberships = user.get("memberships") or []
    if not memberships:
        return None

    if requested:
        if any(m.get("club_id") == requested for m in memberships):
            return requested
        raise HTTPException(status_code=403, detail="No membership in the requested club")

    return memberships[0]["club_id"]


def _roles_across(user: Dict[str, Any], club_id: Optional[str]) -> set:
    if not club_id:
        return set()
    return {
        m["role"]
        for m in (user.get("memberships") or [])
        if m.get("club_id") == club_id
    }


def _child_person_ids(user: Dict[str, Any], club_id: str) -> List[str]:
    """People the caller is a guardian of, from as_person_link.

    Guardianship is a database relationship, not a token claim, so a parent with
    two children on different teams is one row pair each rather than a growing
    ``athlete_ids`` array.
    """
    from src.core.database import get_supabase

    res = (
        get_supabase()
        .table("as_person_link")
        .select("child_person_id")
        .eq("parent_person_id", user.get("person_id"))
        .eq("club_id", club_id)
        .in_("kind", ["parent", "guardian"])
        .execute()
    )
    return [r["child_person_id"] for r in (res.data or []) if r.get("child_person_id")]


@router.get("/analytics/dashboard")
def get_dashboard(
    club_id: Optional[str] = Query(
        None,
        description="Club to render. Defaults to the caller's first active membership.",
    ),
    user: Dict[str, Any] = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Aggregate widget data based on the caller's roles in the selected club."""
    try:
        selected = _resolve_club(user, club_id)
        if not selected:
            raise HTTPException(
                status_code=403,
                detail="No active club membership is associated with this account",
            )

        roles = _roles_across(user, selected)
        if not roles:
            raise HTTPException(status_code=403, detail="No active role in this club")

        if roles & STAFF_ROLES:
            return {
                "role": "admin" if "admin" in roles else "coach",
                "person_id": user.get("person_id"),
                "club_id": selected,
                "widgets": {
                    "team_overview": analytics.get_team_overview(selected),
                },
            }

        person_id = user.get("person_id")

        if "parent" in roles:
            # A parent may hold no swimmer membership at all, so their own trends
            # are empty by design rather than an error.
            children = _child_person_ids(user, selected)
            return {
                "role": "parent",
                "person_id": person_id,
                "club_id": selected,
                "widgets": {
                    "children_progress": {
                        "children": [
                            analytics.get_person_trends(child, club_id=selected)
                            for child in children
                        ]
                    },
                },
            }

        if "swimmer" in roles and person_id:
            return {
                "role": "swimmer",
                "person_id": person_id,
                "club_id": selected,
                "widgets": {
                    "personal_summary": analytics.get_person_trends(person_id, club_id=selected),
                },
            }

        if "official" in roles:
            return {
                "role": "official",
                "person_id": person_id,
                "club_id": selected,
                "widgets": {},
            }

        raise HTTPException(status_code=403, detail="No dashboard view for this role")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Dashboard aggregation failed for club %s", club_id)
        raise HTTPException(status_code=503, detail="Analytics data unavailable") from exc
