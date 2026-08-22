from pydantic import BaseModel, Field


class AthleteReference(BaseModel):
    """Reference to an Athlete managed by the Multi-Tenant User Service (Principle 16).

    Only UUID references and display data are stored locally; profile/auth
    data lives in the external user service.
    """

    id: str = Field(..., description="External athlete UUID")
    club_id: str = Field(..., description="Owning club UUID (tenant scope)")
    name: str = Field(..., description="Athlete display name")
