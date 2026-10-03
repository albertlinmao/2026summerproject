from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from typing import List
from pathlib import Path
import os

from src.api.schemas import ListResponse, SingleResponse, PaginatedResponse
from src.core.auth import get_current_user, get_default_club_id
from src.core.database import get_supabase
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service

router = APIRouter(prefix="/results", tags=["results-browser"])


@router.get("/tree", response_model=SingleResponse[dict])
async def get_results_tree(
    user: dict = Depends(get_current_user)
):
    """
    Get competition results browser tree structure mirroring swim-meets folder hierarchy.
    """
    supabase = get_supabase()
    
    # Get swim-meets folder path from environment
    from src.core.config import get_settings
    settings = get_settings()
    swim_meets_path = Path(settings.SWIM_MEETS_PATH)
    
    if not swim_meets_path.exists():
        raise HTTPException(status_code=404, detail="swim-meets folder not found")
    
    tree = {"year": "", "meets": []}
    
    try:
        for year_dir in sorted(swim_meets_path.iterdir()):
            if not year_dir.is_dir():
                continue
            
            year_node = {"name": year_dir.name, "meets": []}
            
            for meet_dir in sorted(year_dir.iterdir()):
                if not meet_dir.is_dir():
                    continue
                
                meet_node = {
                    "id": meet_dir.name,
                    "name": meet_dir.name,
                    "path": str(meet_dir.relative_to(swim_meets_path)),
                    "figure_events": [],
                    "routine_events": [],
                    "has_figure_results": False,
                    "has_routine_results": False,
                    "pdf_summary_path": None,
                    "pdf_detailed_path": None,
                }
                
                # Check for figure subdirectory
                figure_dir = meet_dir / "figure"
                if figure_dir.exists() and figure_dir.is_dir():
                    # Look for PDF files
                    for pdf_file in figure_dir.glob("*.pdf"):
                        if "Summary" in pdf_file.name:
                            meet_node["pdf_summary_path"] = str(pdf_file.relative_to(swim_meets_path))
                        elif "Detailed" in pdf_file.name:
                            meet_node["pdf_detailed_path"] = str(pdf_file.relative_to(swim_meets_path))
                    
                    meet_node["figure_events"] = [
                        {"name": "Summary", "filename": "Summary.pdf", "path": meet_node["pdf_summary_path"]},
                        {"name": "Detailed", "filename": "Detailed.pdf", "path": meet_node["pdf_detailed_path"]},
                    ]
                    meet_node["has_figure_results"] = True
                
                # Check for routine subdirectory
                routine_dir = meet_dir / "routine"
                if routine_dir.exists() and routine_dir.is_dir():
                    for pdf_file in routine_dir.glob("*.pdf"):
                        if "Summary" in pdf_file.name:
                            meet_node["pdf_summary_path"] = str(pdf_file.relative_to(swim_meets_path))
                        elif "Detailed" in pdf_file.name:
                            meet_node["pdf_detailed_path"] = str(pdf_file.relative_to(swim_meets_path))
                    
                    meet_node["routine_events"] = [
                        {"name": "Summary", "filename": "Summary.pdf", "path": meet_node["pdf_summary_path"]},
                        {"name": "Detailed", "filename": "Detailed.pdf", "path": meet_node["pdf_detailed_path"]},
                    ]
                    meet_node["has_routine_results"] = True
                
                year_node["meets"].append(meet_node)
            
            tree["year"] = year_dir.name
            tree["meets"].extend(year_node["meets"])
        
        return SingleResponse(data=tree)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build tree: {str(e)}")


@router.get("/figure/{meet_id}", response_model=PaginatedResponse[dict])
async def get_figure_results(
    meet_id: str = PathParam(..., description="Meet UUID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Get paginated figure results for a specific meet."""
    supabase = get_supabase()
    club_id = get_default_club_id(user)
    
    query = supabase.table("as_meet_figure_result").select("*", count="exact").eq("meet_id", meet_id)
    
    # Apply club filter if the caller has a club
    if club_id:
        query = query.eq("team_code", club_id)
    
    query = query.range(offset, offset + limit - 1).order("rank")
    
    result = query.execute()
    
    return PaginatedResponse(
        data=result.data or [],
        total=result.count or 0,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < (result.count or 0)
    )


@router.get("/routine/{meet_id}", response_model=PaginatedResponse[dict])
async def get_routine_results(
    meet_id: str = PathParam(..., description="Meet UUID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Get paginated routine results for a specific meet."""
    supabase = get_supabase()
    club_id = get_default_club_id(user)
    
    query = supabase.table("as_meet_routine_result").select("*", count="exact").eq("meet_id", meet_id)
    
    # Apply club filter if the caller has a club
    if club_id:
        query = query.eq("team_code", club_id)
    
    query = query.range(offset, offset + limit - 1).order("rank")
    
    result = query.execute()
    
    return PaginatedResponse(
        data=result.data or [],
        total=result.count or 0,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < (result.count or 0)
    )


@router.get("/pdf/{year}/{meet}/{type}/{filename}")
async def get_pdf_file(
    year: str = PathParam(...),
    meet: str = PathParam(...),
    type: str = PathParam(..., pattern="^(figure|routine)$"),
    filename: str = PathParam(...),
    user: dict = Depends(get_current_user)
):
    """Serve source PDF file for a meet/event."""
    from src.core.config import get_settings
    settings = get_settings()
    swim_meets_path = Path(settings.SWIM_MEETS_PATH)
    
    # Build the file path
    file_path = swim_meets_path / year / meet / type / filename
    
    # Security: Resolve path and ensure it's within swim-meets directory
    try:
        file_path = file_path.resolve()
        swim_meets_path = swim_meets_path.resolve()
        
        if not str(file_path).startswith(str(swim_meets_path)):
            raise HTTPException(status_code=403, detail="Path traversal attempt blocked")
    except Exception:
        raise HTTPException(status_code=403, detail="Path traversal attempt blocked")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Verify it's a PDF
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename
    )

@router.get("/events", response_model=SingleResponse[List[dict]])
async def get_events(user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    result = supabase.table("as_event").select("id, event_name").execute()
    data = [{"id": r["id"], "name": r["event_name"]} for r in (result.data or [])]
    return SingleResponse(data=data)

@router.get("/events/{event_id}/meets", response_model=SingleResponse[List[dict]])
async def get_meets_for_event(event_id: str, user: dict = Depends(get_current_user)):
    import uuid
    try:
        uuid.UUID(str(event_id))
    except ValueError:
        return SingleResponse(data=[])
        
    supabase = get_supabase()
    result = supabase.table("as_meet").select("id, name").eq("event_id", event_id).execute()
    return SingleResponse(data=result.data or [])

@router.get("/meets/{meet_id}/teams", response_model=SingleResponse[List[dict]])
async def get_teams_for_meet(meet_id: str, user: dict = Depends(get_current_user)):
    import uuid
    try:
        uuid.UUID(str(meet_id))
    except ValueError:
        return SingleResponse(data=[])

    supabase = get_supabase()
    fig_res = supabase.table("as_meet_figure_result").select("team_code, team_name").eq("meet_id", meet_id).execute()
    rout_res = supabase.table("as_meet_routine_result").select("team_code, team_name").eq("meet_id", meet_id).execute()
    
    teams = {}
    for r in (fig_res.data or []):
        if r.get("team_code"):
            teams[r["team_code"]] = r.get("team_name") or r["team_code"]
    for r in (rout_res.data or []):
        if r.get("team_code"):
            teams[r["team_code"]] = r.get("team_name") or r["team_code"]
            
    data = [{"id": k, "name": v} for k, v in teams.items()]
    data.sort(key=lambda x: x["name"])
    return SingleResponse(data=data)

@router.get("/meets/{meet_id}/teams/{team_code}/athletes", response_model=SingleResponse[List[dict]])
async def get_athletes_for_team(meet_id: str, team_code: str, user: dict = Depends(get_current_user)):
    import uuid
    try:
        uuid.UUID(str(meet_id))
    except ValueError:
        return SingleResponse(data=[])

    supabase = get_supabase()
    result = supabase.table("as_meet_figure_result").select("athlete_name").eq("meet_id", meet_id).eq("team_code", team_code).execute()
    
    athletes = set()
    for r in (result.data or []):
        if r.get("athlete_name"):
            athletes.add(r["athlete_name"])
            
    data = [{"id": a, "name": a} for a in sorted(athletes)]
    return SingleResponse(data=data)

@router.get("/meets/{meet_id}/teams/{team_code}/routines", response_model=SingleResponse[List[dict]])
async def get_routines_for_team(meet_id: str, team_code: str, user: dict = Depends(get_current_user)):
    import uuid
    try:
        uuid.UUID(str(meet_id))
    except ValueError:
        return SingleResponse(data=[])

    supabase = get_supabase()
    result = supabase.table("as_meet_routine_result").select("*").eq("meet_id", meet_id).eq("team_code", team_code).execute()
    
    data = []
    for r in (result.data or []):
        name = "Routine"
        if r.get("source_file"):
            name = Path(r["source_file"]).stem.replace("Detailed_-_", "").replace("_", " ")
        
        athletes = []
        if r.get("team_athletes"):
            import json
            try:
                # Could be a string or a parsed list depending on postgrest
                athletes_data = r["team_athletes"]
                if isinstance(athletes_data, str):
                    athletes_data = json.loads(athletes_data)
                if isinstance(athletes_data, list):
                    athletes = [a.get("name") for a in athletes_data if isinstance(a, dict) and a.get("name")]
            except Exception:
                pass

        data.append({
            "routineName": name,
            "type": "Team",
            "score": r.get("routine_score", 0),
            "athletes": athletes
        })
    return SingleResponse(data=data)

@router.get("/meets/{meet_id}/athletes/{athlete_name}/figures", response_model=SingleResponse[List[dict]])
async def get_figures_for_athlete(meet_id: str, athlete_name: str, user: dict = Depends(get_current_user)):
    """Figure scores for one athlete at one meet.

    ``athlete_name`` is a printed name from the source PDF, so it is ambiguous
    between two swimmers of the same name. Kept for compatibility and superseded
    by ``as_result_person_link``: new work should key on ``person_id``. See
    identity-contract.md §7.
    """
    import uuid
    try:
        uuid.UUID(str(meet_id))
    except ValueError:
        return SingleResponse(data=[])

    supabase = get_supabase()
    result = supabase.table("as_meet_figure_result").select("*").eq("meet_id", meet_id).eq("athlete_name", athlete_name).execute()
    
    data = []
    for r in (result.data or []):
        figure_scores = r.get("figure_scores", {})
        if isinstance(figure_scores, str):
            import json
            try:
                figure_scores = json.loads(figure_scores)
            except Exception:
                figure_scores = {}
        if isinstance(figure_scores, dict):
            for figure_name, score in figure_scores.items():
                data.append({
                    "figureName": figure_name,
                    "dd": "",
                    "score": score
                })
    return SingleResponse(data=data)


@router.get("/clubs", response_model=SingleResponse[List[dict]])
async def get_clubs(user: dict = Depends(get_current_user)):
    """List all clubs from the as_club table."""
    supabase = get_supabase()
    result = supabase.table("as_club").select("id, name, code").order("name").execute()
    data = [
        {"id": r["id"], "name": r["name"], "code": r.get("code", "")}
        for r in (result.data or [])
    ]
    return SingleResponse(data=data)


@router.get("/clubs/{club_id}/athletes", response_model=SingleResponse[List[dict]])
async def get_club_athletes(
    club_id: str,
    user: dict = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics_service)
):
    """List the people holding an active swimmer membership in a club.

    Club scope is resolved through ``as_club_membership`` rather than by
    filtering the ``as_athlete`` view, which spans clubs and has no club_id.
    """
    import uuid
    try:
        uuid.UUID(str(club_id))
    except ValueError:
        return SingleResponse(data=[])

    data = [
        {"id": s.person_id, "name": s.name}
        for s in sorted(analytics.get_club_swimmers(club_id), key=lambda s: s.name)
    ]
    return SingleResponse(data=data)


@router.get("/athletes/{athlete_name}/figure-history", response_model=SingleResponse[List[dict]])
async def get_athlete_figure_history(athlete_name: str, user: dict = Depends(get_current_user)):
    """Get figure scores for an athlete across all competitions (meets).

    ``athlete_name`` is a printed name from the source PDF, so it is ambiguous
    between two swimmers of the same name. Kept for compatibility and superseded
    by ``as_result_person_link``: new work should key on ``person_id``. See
    identity-contract.md §7.
    """
    import json

    supabase = get_supabase()

    # Fetch all figure result rows for the athlete
    result = supabase.table("as_meet_figure_result") \
        .select("*") \
        .eq("athlete_name", athlete_name) \
        .execute()

    # Pre-fetch all relevant meets to avoid N+1 queries
    meet_ids = list({r.get("meet_id") for r in (result.data or []) if r.get("meet_id")})
    meet_map = {}
    event_map = {}
    if meet_ids:
        meets_res = supabase.table("as_meet").select("id, name, meet_date, event_id").in_("id", meet_ids).execute()
        for m in (meets_res.data or []):
            meet_map[m["id"]] = m
        event_ids = list({m.get("event_id") for m in meet_map.values() if m.get("event_id")})
        if event_ids:
            events_res = supabase.table("as_event").select("id, event_name").in_("id", event_ids).execute()
            for e in (events_res.data or []):
                event_map[e["id"]] = e

    data = []
    for r in (result.data or []):
        meet_id = r.get("meet_id")
        team_code = r.get("team_code")
        team_name = r.get("team_name", "")
        total_score = r.get("total_score")
        figure_score = r.get("figure_score")

        # Look up meet info
        meet_info = meet_map.get(meet_id, {}) if meet_id else {}
        meet_name = meet_info.get("name", "")
        meet_date = meet_info.get("meet_date")

        # Look up event name
        event_info = event_map.get(meet_info.get("event_id"), {}) if meet_info else {}
        event_name = event_info.get("event_name", "")

        # Parse figure_scores (dict of figure_name -> score)
        figure_scores = r.get("figure_scores", {})
        if isinstance(figure_scores, str):
            try:
                figure_scores = json.loads(figure_scores)
            except (json.JSONDecodeError, TypeError):
                figure_scores = {}

        data.append({
            "meetId": meet_id,
            "meetName": meet_name,
            "meetDate": str(meet_date) if meet_date else None,
            "eventName": event_name,
            "teamCode": team_code,
            "teamName": team_name,
            "totalScore": total_score,
            "figureScore": figure_score,
            "figureScores": figure_scores
        })

    # Sort by meet date (chronological)
    data.sort(key=lambda x: x.get("meetDate") or "", reverse=False)

    return SingleResponse(data=data)

