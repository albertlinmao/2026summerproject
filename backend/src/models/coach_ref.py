from pydantic import BaseModel, Field


class CoachReference(BaseModel):
    """Reference to a Coach managed by the Multi-Tenant User Service (Principle 16)."""

    id: str = Field(..., description="External coach UUID")
    club_id: str = Field(..., description="Owning club UUID (tenant scope)")
    name: str = Field(..., description="Coach display name")
