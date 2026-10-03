from pydantic import BaseModel, Field
from typing import List, Optional


class PersonRef(BaseModel):
    """A person, as seen by the dashboard (Principle 16).

    A person is a human being and carries no club: belonging to a club is a row in
    ``as_club_membership``, which is why this model has no ``club_id``. Profile and
    auth data live in the external user service.
    """

    person_id: str = Field(..., description="Person UUID (as_person.id)")
    name: str = Field(..., description="Display name assembled from the name parts")
    given_name: Optional[str] = Field(None, description="Given name")
    family_name: Optional[str] = Field(None, description="Family name")
    birth_date: Optional[str] = Field(None, description="ISO date, when known")


class AthleteRef(PersonRef):
    """A person holding an active ``swimmer`` membership in at least one club.

    Projected from the ``as_athlete`` view, so it spans clubs and has no
    ``club_id``. The club a swimmer competes for is a separate question, answered
    by ``as_club_membership``.
    """


class CoachRef(PersonRef):
    """A person holding an active ``coach`` or ``admin`` membership.

    Projected from the ``as_coach`` view, so it spans clubs and has no ``club_id``.
    """


class ClubMembershipRef(BaseModel):
    """One person's standing in one club."""

    person_id: str
    club_id: str
    role: str = Field(..., description="admin | coach | swimmer | parent | official")
    title: Optional[str] = Field(
        None,
        description="Display-only title such as 'Lead Coach' or 'Team Captain'. "
                    "Never authorizes anything; `role` is what RLS matches on.",
    )
    status: str = Field(..., description="invited | active | dormant | left")
    joined_at: Optional[str] = None
    left_at: Optional[str] = None


class PersonLinkRef(BaseModel):
    """A directed guardian edge between two people, scoped to a club.

    This is what makes family-only video access expressible without requiring an
    account for every minor swimmer.
    """

    parent_person_id: str
    child_person_id: str
    club_id: str
    kind: str = Field(..., description="parent | guardian | emergency_contact")
