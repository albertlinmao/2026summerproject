from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.dashboard import router as dashboard_router
from src.api.sst import router as sst_router
from src.api.insights import router as insights_router
from src.api.uploads import router as uploads_router
from src.api.markers import router as markers_router
from src.api.timers import router as timers_router

app = FastAPI(title="Artistic Swimming Analytics API")

# Configure CORS for the Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router, prefix="/api")
app.include_router(sst_router, prefix="/api")
app.include_router(insights_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(markers_router, prefix="/api")
app.include_router(timers_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Artistic Swimming Analytics API is running"}
