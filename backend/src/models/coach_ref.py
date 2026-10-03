"""Deprecated shim.

The identity model has no separate Coach record: a coach is a person holding an
active ``coach`` or ``admin`` membership, projected through the ``as_coach`` view.

Import from :mod:`src.models.athlete_ref` instead — ``CoachRef`` and ``PersonRef``
live there alongside the rest of the person/membership models.
"""

from src.models.athlete_ref import CoachRef, PersonLinkRef, PersonRef  # noqa: F401
