"""Video upload: presigned-URL issuance and finalization.

Identity follows ``specs/001-analytics-dashboard/identity-contract.md``:

* The club is the caller's **active membership**, not a claim.
* The video is keyed on ``person_id``, the athlete who appears in it, which is
  the family-access key; ``uploaded_by`` is the caller and may be a different
  person — a parent uploading their child's footage.

The two are now separate, so the upload needs its own authorization check. This
endpoint re-implements the RLS insert policy
(``app_is_club_staff(club_id) or app_is_guardian_of(...)``) at the API layer
because this service holds a key that bypasses RLS.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.core.auth import (
    ACTIVE_MEMBERSHIP_STATUSES,
    get_current_person_id,
    get_current_user,
    is_club_staff,
    require_club_membership,
)
from src.core.database import supabase
from src.services.media.video_upload_service import get_signed_upload_url, finalize_upload

router = APIRouter()


class SignRequest(BaseModel):
    # The athlete who appears in the video. Required rather than inferred from
    # the caller, because a parent or coach uploads on someone else's behalf.
    person_id: str
    filename: str
    mime_type: str
    size_bytes: int


class FinalizeRequest(BaseModel):
    upload_id: str
    storage_path: str


def _is_guardian_of(parent_person_id: str, child_person_id: str, club_id: str) -> bool:
    """Mirrors ``app_is_guardian_of``: a club-scoped ``as_person_link`` row.

    The link is scoped to one club on purpose — guardianship in a different club
    does not grant access to a swimmer who happens to be the same person.
    """
    res = (
        supabase.table("as_person_link")
        .select("id")
        .eq("parent_person_id", parent_person_id)
        .eq("child_person_id", child_person_id)
        .eq("club_id", club_id)
        .in_("kind", ["parent", "guardian"])
        .limit(1)
        .execute()
    )
    return bool(res.data)


def _is_active_club_member(person_id: str, club_id: str) -> bool:
    res = (
        supabase.table("as_club_membership")
        .select("id")
        .eq("person_id", person_id)
        .eq("club_id", club_id)
        .in_("status", list(ACTIVE_MEMBERSHIP_STATUSES))
        .limit(1)
        .execute()
    )
    return bool(res.data)


def _require_upload_access(
    user: Dict[str, Any], club_id: str, uploaded_by: str, person_id: str
) -> None:
    """Staff may upload for anyone in their club; a parent only for their child."""
    if is_club_staff(user, club_id):
        if not _is_active_club_member(person_id, club_id):
            raise HTTPException(
                status_code=403,
                detail="Person is not an active member of this club",
            )
        return

    if not _is_guardian_of(uploaded_by, person_id, club_id):
        raise HTTPException(status_code=403, detail="Not permitted to upload for this athlete")


@router.post("/uploads/sign")
def sign_upload(
    req: SignRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    uploaded_by: str = Depends(get_current_person_id),
    club_id: str = Depends(require_club_membership),
):
    _require_upload_access(user, club_id, uploaded_by, req.person_id)
    try:
        return get_signed_upload_url(
            club_id,
            req.person_id,
            uploaded_by,
            req.filename,
            req.mime_type,
            req.size_bytes,
        )
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.post("/uploads/finalize")
def finalize(req: FinalizeRequest, user: dict = Depends(get_current_user)):
    try:
        return finalize_upload(req.upload_id, req.storage_path)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
