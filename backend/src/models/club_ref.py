from pydantic import BaseModel, Field


class ClubReference(BaseModel):
    """Reference to a Club (tenant) managed by the Multi-Tenant User Service."""

    id: str = Field(..., description="Club UUID (tenant identifier)")
    name: str = Field(..., description="Club display name")
