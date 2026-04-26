"""Grading engine module.

Contains logic for:
- Grade hierarchy and comparisons
- Strength of Schedule (SoS) calculations
- Team performance metrics
- Transitive variance detection
- Recommendation generation
- Admin override tracking
- Round analysis and matchup optimization
- Bye rotation management
- Historical learning for matchup predictions
"""

from src.grading.bye_manager import ByeRotationManager
from src.grading.grades import (
    GRADE_ORDER,
    can_demote,
    can_promote,
    grade_above,
    grade_below,
    grade_distance,
    grades_between,
)
from src.grading.matchup_learner import LearningStats, MatchupLearner, TeamPairHistory
from src.grading.matchup_optimizer import MatchupOptimizer, generate_matchups
from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.grading.overrides import OverrideManager
from src.grading.power_rating import (
    TeamPowerRating,
    calculate_power_ratings,
    get_grade_rating_distribution,
    get_rating_comparison,
)
from src.grading.recommender import RecommendationEngine
from src.grading.round_analyzer import RoundAnalyzer, analyze_round
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
    "RoundAnalyzer",
    "analyze_round",
    "MatchupOptimizer",
    "generate_matchups",
    "ByeRotationManager",
    "MatchupLearner",
    "LearningStats",
    "TeamPairHistory",
    "TeamPowerRating",
    "calculate_power_ratings",
    "get_grade_rating_distribution",
    "get_rating_comparison",
]
