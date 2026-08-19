from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import verify_jwt
from src.services.media.video_upload_service import get_signed_upload_url, finalize_upload

router = APIRouter()


class SignRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int


class FinalizeRequest(BaseModel):
    upload_id: str
    storage_path: str


@router.post("/uploads/sign")
def sign_upload(req: SignRequest, user_payload: dict = Depends(verify_jwt)):
    user_id = user_payload.get("uid")
    try:
        return get_signed_upload_url(user_id, req.filename, req.mime_type, req.size_bytes)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.post("/uploads/finalize")
def finalize(req: FinalizeRequest, user_payload: dict = Depends(verify_jwt)):
    user_id = user_payload.get("uid")
    try:
        return finalize_upload(req.upload_id, req.storage_path, user_id)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
