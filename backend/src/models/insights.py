"""Deprecated shim.

``PredictiveInsight`` and ``CoachingRecommendation`` were defined twice — here and
in the dedicated modules. The dedicated modules are canonical because they carry
the field documentation; this file re-exports them so existing imports keep working.

Import from :mod:`src.models.predictive_insight` and
:mod:`src.models.coaching_recommendation` instead.
"""

from src.models.coaching_recommendation import CoachingRecommendation  # noqa: F401
from src.models.predictive_insight import PredictiveInsight  # noqa: F401
