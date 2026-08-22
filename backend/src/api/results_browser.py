from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from typing import Optional, List
from pathlib import Path
import os

from src.api.schemas import ListResponse, SingleResponse, PaginatedResponse
from src.core.auth import get_current_user, get_club_id
from src.core.database import get_supabase

router = APIRouter(prefix="/results", tags=["results-browser"])


@router.get("/tree", response_model=SingleResponse[dict])
async def get_results_tree(
    user: dict = Depends(get_current_user),
    club_id: Optional[str] = Depends(get_club_id)
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
    user: dict = Depends(get_current_user),
    club_id: Optional[str] = Depends(get_club_id)
):
    """Get paginated figure results for a specific meet."""
    supabase = get_supabase()
    
    query = supabase.table("as_meet_figure_result").select("*", count="exact").eq("meet_id", meet_id)
    
    # Apply club filter if user has club_id
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
    user: dict = Depends(get_current_user),
    club_id: Optional[str] = Depends(get_club_id)
):
    """Get paginated routine results for a specific meet."""
    supabase = get_supabase()
    
    query = supabase.table("as_meet_routine_result").select("*", count="exact").eq("meet_id", meet_id)
    
    # Apply club filter if user has club_id
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
