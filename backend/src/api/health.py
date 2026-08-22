from fastapi import APIRouter
from src.core.cache import get_redis_client
from src.core.database import get_supabase

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    checks = {}
    
    # Check Redis
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    # Check Supabase
    try:
        supabase = get_supabase()
        # Simple query to verify connection
        result = supabase.table("as_club").select("id").limit(1).execute()
        checks["supabase"] = "healthy"
    except Exception as e:
        checks["supabase"] = f"unhealthy: {str(e)}"
    
    all_healthy = all(v == "healthy" for v in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks
    }


@router.get("/health/ready")
async def readiness_check():
    return await health_check()


@router.get("/health/live")
async def liveness_check():
    return {"status": "alive"}