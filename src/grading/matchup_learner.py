"""Historical learning for matchup prediction improvement.

Tracks prediction outcomes and adjusts confidence levels based on
historical accuracy. Implements exponential decay for older data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import get_settings
from src.data.matchup_storage import MatchupStorage
from src.models.game_result import GameResult
from src.models.matchup import (
    MatchupConfidence,
    MatchupOutcome,
    MatchupRecommendation,
)


@dataclass
class LearningStats:
    """Statistics for learning performance."""

    total_predictions: int = 0
    accurate_predictions: int = 0
    variance_reduced_count: int = 0
    total_weighted: float = 0.0
    accurate_weighted: float = 0.0

    @property
    def accuracy_rate(self) -> float:
        """Unweighted accuracy rate (0-100)."""
        if self.total_predictions == 0:
            return 0.0
        return self.accurate_predictions / self.total_predictions * 100

    @property
    def weighted_accuracy_rate(self) -> float:
        """Weighted accuracy rate with recency bias (0-100)."""
        if self.total_weighted == 0:
            return 0.0
        return self.accurate_weighted / self.total_weighted * 100

    @property
    def variance_reduction_rate(self) -> float:
        """Rate of predictions that reduced variance (0-100)."""
        if self.total_predictions == 0:
            return 0.0
        return self.variance_reduced_count / self.total_predictions * 100


@dataclass
class TeamPairHistory:
    """Historical performance for a specific team pairing."""

    team_a: str
    team_b: str
    outcomes: list[MatchupOutcome] = field(default_factory=list)

    @property
    def games_played(self) -> int:
        """Number of games between these teams."""
        return len(self.outcomes)

    @property
    def avg_margin(self) -> float:
        """Average margin in games between these teams."""
        if not self.outcomes:
            return 0.0
        return sum(o.actual_margin for o in self.outcomes) / len(self.outcomes)


class MatchupLearner:
    """Learns from matchup outcomes to improve future predictions.

    Tracks which predictions were accurate and adjusts confidence
    levels based on historical performance.
    """

    def __init__(
        self,
        storage: MatchupStorage | None = None,
        decay_factor: float | None = None,
    ) -> None:
        """Initialize the matchup learner.

        Args:
            storage: Storage backend for persistence.
            decay_factor: Exponential decay factor for older predictions.
                         Higher = more weight on recent data.
        """
        settings = get_settings()
        self.storage = storage or MatchupStorage()
        self.decay_factor = (
            decay_factor if decay_factor is not None else settings.confidence_decay_factor
        )

        # Cache for team pair histories
        self._pair_cache: dict[str, TeamPairHistory] = {}

    def record_outcome(
        self,
        matchup: MatchupRecommendation,
        actual_game: GameResult,
        season: str,
    ) -> MatchupOutcome:
        """Record the outcome of a matchup for learning.

        Args:
            matchup: The original matchup recommendation.
            actual_game: The actual game result.
            season: Season identifier.

        Returns:
            The created MatchupOutcome.
        """
        # Calculate predicted margin range based on team averages
        margin_a = matchup.team_a_recent_margin or 0.0
        margin_b = matchup.team_b_recent_margin or 0.0

        # Predicted range: midpoint +/- spread based on confidence
        midpoint = (margin_a - margin_b) / 2
        spread = self._get_spread_for_confidence(matchup.confidence)
        predicted_range = (int(midpoint - spread), int(midpoint + spread))

        # Determine if prediction was accurate
        actual_margin = actual_game.margin
        prediction_accurate = predicted_range[0] <= actual_margin <= predicted_range[1]

        # Determine if variance was reduced
        # (actual margin is closer to 0 than predicted margins)
        variance_reduced = abs(actual_margin) < abs(midpoint)

        outcome = MatchupOutcome(
            matchup_id=matchup.id,
            round_num=matchup.round_num,
            team_a_name=matchup.team_a_name,
            team_b_name=matchup.team_b_name,
            predicted_margin_range=predicted_range,
            actual_margin=actual_margin,
            variance_reduced=variance_reduced,
            prediction_accurate=prediction_accurate,
        )

        # Save to storage
        self.storage.save_outcome(outcome, season)

        # Update cache
        self._update_pair_cache(outcome)

        return outcome

    def _get_spread_for_confidence(self, confidence: MatchupConfidence) -> float:
        """Get margin spread based on confidence level.

        Args:
            confidence: Confidence level.

        Returns:
            Spread value in points.
        """
        spreads = {
            MatchupConfidence.HIGH: 10,
            MatchupConfidence.MEDIUM: 15,
            MatchupConfidence.LOW: 25,
        }
        conf_value = confidence.value if isinstance(confidence, MatchupConfidence) else confidence
        return spreads.get(MatchupConfidence(conf_value), 20)

    def _update_pair_cache(self, outcome: MatchupOutcome) -> None:
        """Update the team pair cache with new outcome.

        Args:
            outcome: The new outcome to add.
        """
        # Create canonical key (alphabetically sorted)
        teams = sorted([outcome.team_a_name, outcome.team_b_name])
        key = f"{teams[0]}|{teams[1]}"

        if key not in self._pair_cache:
            self._pair_cache[key] = TeamPairHistory(
                team_a=teams[0],
                team_b=teams[1],
            )

        self._pair_cache[key].outcomes.append(outcome)

    def get_accuracy_stats(self, season: str) -> LearningStats:
        """Get accuracy statistics for a season.

        Args:
            season: Season identifier.

        Returns:
            LearningStats with accuracy metrics.
        """
        outcomes = self.storage.load_outcomes(season)

        if not outcomes:
            return LearningStats()

        # Sort by round number for decay calculation
        outcomes.sort(key=lambda o: o.round_num)
        max_round = max(o.round_num for o in outcomes)

        stats = LearningStats()

        for outcome in outcomes:
            # Calculate weight with exponential decay
            rounds_ago = max_round - outcome.round_num
            weight = self.decay_factor**rounds_ago

            stats.total_predictions += 1
            stats.total_weighted += weight

            if outcome.prediction_accurate:
                stats.accurate_predictions += 1
                stats.accurate_weighted += weight

            if outcome.variance_reduced:
                stats.variance_reduced_count += 1

        return stats

    def adjust_confidence(
        self,
        team_a: str,
        team_b: str,
        base_confidence: MatchupConfidence,
        season: str,
    ) -> MatchupConfidence:
        """Adjust confidence based on historical accuracy for team pair.

        Args:
            team_a: First team name.
            team_b: Second team name.
            base_confidence: Initial confidence level.
            season: Season identifier.

        Returns:
            Adjusted confidence level.
        """
        # Get historical outcomes for this pair
        teams = sorted([team_a, team_b])
        key = f"{teams[0]}|{teams[1]}"

        # Load from cache or storage
        if key not in self._pair_cache:
            all_outcomes = self.storage.load_outcomes(season)
            for outcome in all_outcomes:
                self._update_pair_cache(outcome)

        pair_history = self._pair_cache.get(key)

        if not pair_history or pair_history.games_played < 2:
            return base_confidence  # Not enough data

        # Calculate accuracy for this pair
        accurate = sum(1 for o in pair_history.outcomes if o.prediction_accurate)
        accuracy_rate = accurate / pair_history.games_played

        # Adjust confidence based on historical accuracy
        confidence_map = [
            MatchupConfidence.LOW,
            MatchupConfidence.MEDIUM,
            MatchupConfidence.HIGH,
        ]
        base_index = confidence_map.index(base_confidence)

        if accuracy_rate >= 0.8:
            # High accuracy -> boost confidence
            new_index = min(base_index + 1, 2)
        elif accuracy_rate <= 0.3:
            # Low accuracy -> reduce confidence
            new_index = max(base_index - 1, 0)
        else:
            new_index = base_index

        return confidence_map[new_index]

    def get_team_pair_history(
        self,
        team_a: str,
        team_b: str,
        season: str,
    ) -> TeamPairHistory | None:
        """Get historical matchup data for a team pair.

        Args:
            team_a: First team name.
            team_b: Second team name.
            season: Season identifier.

        Returns:
            TeamPairHistory or None if no history.
        """
        teams = sorted([team_a, team_b])
        key = f"{teams[0]}|{teams[1]}"

        # Ensure cache is loaded
        if key not in self._pair_cache:
            all_outcomes = self.storage.load_outcomes(season)
            for outcome in all_outcomes:
                self._update_pair_cache(outcome)

        return self._pair_cache.get(key)

    def get_improvement_suggestions(
        self,
        season: str,
    ) -> list[str]:
        """Get suggestions for improving matchup predictions.

        Args:
            season: Season identifier.

        Returns:
            List of improvement suggestions.
        """
        stats = self.get_accuracy_stats(season)
        suggestions: list[str] = []

        if stats.total_predictions < 10:
            suggestions.append(
                "More data needed: Record at least 10 matchup outcomes "
                "for meaningful learning insights."
            )
            return suggestions

        if stats.accuracy_rate < 50:
            suggestions.append(
                f"Low prediction accuracy ({stats.accuracy_rate:.1f}%). "
                "Consider adjusting variance thresholds or cross-grade triggers."
            )

        if stats.variance_reduction_rate < 40:
            suggestions.append(
                f"Low variance reduction rate ({stats.variance_reduction_rate:.1f}%). "
                "Cross-grade matchups may not be effectively balancing grades."
            )

        if stats.weighted_accuracy_rate > stats.accuracy_rate + 10:
            suggestions.append(
                "Recent predictions are more accurate than historical average. "
                "The algorithm is improving over time."
            )
        elif stats.weighted_accuracy_rate < stats.accuracy_rate - 10:
            suggestions.append(
                "Recent predictions are less accurate than historical average. "
                "Consider reviewing recent team performance changes."
            )

        if not suggestions:
            suggestions.append(
                f"Predictions are performing well: {stats.accuracy_rate:.1f}% accuracy, "
                f"{stats.variance_reduction_rate:.1f}% variance reduction."
            )

        return suggestions

    def clear_cache(self) -> None:
        """Clear the team pair cache."""
        self._pair_cache.clear()
