import os
import uuid
import httpx

from src.core.database import supabase

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
STORAGE_BUCKET = "videos"


def get_signed_upload_url(user_id: str, filename: str, mime_type: str, size_bytes: int) -> dict:
    if size_bytes > MAX_FILE_SIZE:
        raise ValueError("File too large. Maximum size is 2GB.")

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp4"
    storage_path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    res = supabase.storage.from_(STORAGE_BUCKET).create_signed_upload_url(storage_path)

    upload_id = uuid.uuid4().hex
    supabase.table("as_video_uploads").insert({
        "id": upload_id,
        "club_id": None,
        "uploaded_by": user_id,
        "storage_path": storage_path,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "status": "uploading",
    }).execute()

    return {
        "upload_url": res.get("signedUrl"),
        "storage_path": storage_path,
        "upload_id": upload_id,
    }


def finalize_upload(upload_id: str, storage_path: str, user_id: str) -> dict:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    file_url = f"{supabase_url}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"

    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

    with httpx.Client() as client:
        head_resp = client.head(file_url, headers=headers, follow_redirects=True)

        if head_resp.status_code == 403:
            raise PermissionError("Unauthorized: cannot access storage object.")
        if head_resp.status_code == 404:
            raise FileNotFoundError("Uploaded file not found in storage.")

        content_length = int(head_resp.headers.get("content-length", 0))
        if content_length > MAX_FILE_SIZE:
            supabase.table("as_video_uploads").update({"status": "uploading"}).eq("id", upload_id).execute()
            raise ValueError("File too large. Maximum size is 2GB.")

    supabase.table("as_video_uploads").update({"status": "ready"}).eq("id", upload_id).execute()

    resp = supabase.table("as_video_uploads").select("*").eq("id", upload_id).single().execute()
    return resp.data
