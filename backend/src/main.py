from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from src.core.config import get_settings
from src.core.logging_config import setup_logging
from src.core.exceptions import register_exception_handlers
from src.core.cache import get_redis_client, close_redis_client

# Import API routers
from src.api.dashboard import router as dashboard_router
from src.api.insights import router as insights_router
from src.api.predictions import router as predictions_router
from src.api.recommendations import router as recommendations_router
from src.api.team import router as team_router
from src.api.uploads import router as uploads_router
from src.api.markers import router as markers_router
from src.api.timers import router as timers_router
from src.api.results_browser import router as results_browser_router
from src.api.auth import router as auth_router
from src.api.health import router as health_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging(settings.LOG_LEVEL, json_format=settings.APP_ENV == "production")
    logger = __import__("logging").getLogger(__name__)
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    
    # Initialize Redis connection
    try:
        await get_redis_client()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    await close_redis_client()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Artistic Swimming Analytics Dashboard API",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include API routers
app.include_router(health_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(insights_router, prefix="/api")
app.include_router(predictions_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(team_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(markers_router, prefix="/api")
app.include_router(timers_router, prefix="/api")
app.include_router(results_browser_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "Artistic Swimming Analytics API is running",
        "version": "1.0.0",
        "docs": "/docs" if settings.APP_ENV != "production" else "disabled"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}