"""Grading engine module.

Contains logic for:
- Grade hierarchy and comparisons
- Strength of Schedule (SoS) calculations
- Team performance metrics
- Transitive variance detection
- Recommendation generation
- Admin override tracking
"""

from src.grading.grades import (
    GRADE_ORDER,
    can_demote,
    can_promote,
    grade_above,
    grade_below,
    grade_distance,
    grades_between,
)
from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.grading.overrides import OverrideManager
from src.grading.recommender import RecommendationEngine
from src.grading.strength_of_schedule import StrengthOfSchedule, calculate_sos
from src.grading.transitive import TransitiveChain, find_transitive_chains

__all__ = [
    "GRADE_ORDER",
    "grade_distance",
    "grade_above",
    "grade_below",
    "grades_between",
    "can_promote",
    "can_demote",
    "StrengthOfSchedule",
    "calculate_sos",
    "TeamMetrics",
    "calculate_team_metrics",
    "TransitiveChain",
    "find_transitive_chains",
    "RecommendationEngine",
    "OverrideManager",
]
