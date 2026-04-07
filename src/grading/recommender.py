"""Recommendation engine for grade movement decisions.

Generates transparent, defensible recommendations based on:
- Team performance metrics
- Strength of Schedule analysis
- Transitive variance detection
- Configurable thresholds

Recommendations include human-readable explanations suitable
for parent communication and DVBA appeals.
"""

from __future__ import annotations

from src.grading.grades import can_demote, can_promote, grade_above, grade_below
from src.grading.metrics import (
    BLOWOUT_MARGIN,
    MIN_GAMES_FOR_RECOMMENDATION,
    TeamMetrics,
    calculate_team_metrics,
)
from src.grading.strength_of_schedule import StrengthOfSchedule, calculate_sos
from src.grading.transitive import TransitiveChain, find_transitive_chains
from src.models.game_result import Grade, TeamSeason
from src.models.recommendation import Confidence, Recommendation, RecommendationType


def _get_grade_value(grade: Grade | str | None) -> str | None:
    """Get string value from Grade enum or string.

    Args:
        grade: Grade enum, string, or None.

    Returns:
        Grade value as string, or None.
    """
    if grade is None:
        return None
    if isinstance(grade, Grade):
        return grade.value
    return str(grade)


def _ensure_grade_enum(grade: Grade | str | None) -> Grade | None:
    """Ensure we have a Grade enum (convert from string if needed).

    Args:
        grade: Grade enum, string, or None.

    Returns:
        Grade enum or None.
    """
    if grade is None:
        return None
    if isinstance(grade, Grade):
        return grade
    return Grade.from_string(str(grade))


class RecommendationEngine:
    """Engine for generating grade movement recommendations.

    Analyzes team performance and generates recommendations with
    supporting evidence and confidence levels.
    """

    def __init__(
        self,
        blowout_threshold: int = BLOWOUT_MARGIN,
        min_games: int = MIN_GAMES_FOR_RECOMMENDATION,
        blowout_win_threshold: int = 3,
        blowout_loss_threshold: int = 3,
    ) -> None:
        """Initialize the recommendation engine.

        Args:
            blowout_threshold: Point margin for blowout classification.
            min_games: Minimum games before making recommendations.
            blowout_win_threshold: Blowout wins needed for promotion.
            blowout_loss_threshold: Blowout losses needed for demotion.
        """
        self.blowout_threshold = blowout_threshold
        self.min_games = min_games
        self.blowout_win_threshold = blowout_win_threshold
        self.blowout_loss_threshold = blowout_loss_threshold

    def generate_recommendation(
        self,
        team: TeamSeason,
        all_teams: list[TeamSeason] | None = None,
    ) -> Recommendation:
        """Generate a grade recommendation for a team.

        Args:
            team: Team to analyze.
            all_teams: All teams for transitive analysis (optional).

        Returns:
            Recommendation with type, confidence, and explanation.
        """
        metrics = calculate_team_metrics(team)
        sos = calculate_sos(team)

        # Find transitive chains if all teams provided
        transitive_chains: list[TransitiveChain] = []
        if all_teams:
            transitive_chains = find_transitive_chains(team.team_name, all_teams)

        # Build evidence and concerns lists
        evidence: list[str] = []
        concerns: list[str] = []

        # Add basic stats to evidence
        evidence.append(
            f"Record: {metrics.wins}W-{metrics.losses}L (Win rate: {metrics.win_rate}%)"
        )
        evidence.append(f"Average margin: {metrics.avg_margin:+.1f} points")

        if metrics.blowout_wins > 0:
            evidence.append(f"Blowout wins (20+ pts): {metrics.blowout_wins}")
        if metrics.blowout_losses > 0:
            evidence.append(f"Blowout losses (20+ pts): {metrics.blowout_losses}")

        # Add SoS context
        if sos.total_games > 0:
            evidence.append(f"SoS Score: {sos.sos_score}/100 ({sos.schedule_difficulty})")
            if sos.played_above_count > 0:
                evidence.append(f"Games vs higher grades: {sos.played_above_count}")
            if sos.played_below_count > 0:
                evidence.append(f"Games vs lower grades: {sos.played_below_count}")

        # Check for insufficient data
        if not metrics.has_sufficient_data:
            concerns.append(
                f"Only {metrics.games_played} games played "
                f"(minimum {self.min_games} required for recommendation)"
            )
            return self._create_recommendation(
                team=team,
                rec_type=RecommendationType.MONITOR,
                confidence=Confidence.LOW,
                explanation=(
                    f"Insufficient data: {team.team_name} has only played "
                    f"{metrics.games_played} games. Need {self.min_games}+ "
                    "games for reliable grade assessment."
                ),
                evidence=evidence,
                concerns=concerns,
                sos=sos,
                transitive_chains=transitive_chains,
            )

        # Check for grade coverage issues (never played at assigned grade)
        if sos.never_played_at_grade and team.assigned_grade:
            grade_str = _get_grade_value(team.assigned_grade)
            concerns.append(
                f"Team has not played any {grade_str}-grade opponents during grading rounds"
            )

            # This requires review - we can't predict performance at assigned grade
            return self._create_recommendation(
                team=team,
                rec_type=RecommendationType.REVIEW_NEEDED,
                confidence=Confidence.MEDIUM,
                explanation=(
                    f"Grade coverage issue: {team.team_name} (assigned {grade_str}) "
                    f"has played 0 games against {grade_str}-grade opponents. "
                    f"Played {sos.played_above_count} games UP, {sos.played_below_count} games DOWN. "
                    "Cannot reliably predict performance at assigned grade."
                ),
                evidence=evidence,
                concerns=concerns,
                sos=sos,
                transitive_chains=transitive_chains,
            )

        # Check for transitive variance concerns
        if transitive_chains:
            significant_chains = [c for c in transitive_chains if c.implied_variance >= 50]
            if significant_chains:
                for chain in significant_chains[:3]:  # Limit to top 3
                    concerns.append(f"Transitive variance: {chain}")

        # Determine recommendation based on metrics
        rec_type, confidence, explanation = self._evaluate_metrics(
            team, metrics, sos, transitive_chains
        )

        return self._create_recommendation(
            team=team,
            rec_type=rec_type,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence,
            concerns=concerns,
            sos=sos,
            transitive_chains=transitive_chains,
        )

    def _evaluate_metrics(
        self,
        team: TeamSeason,
        metrics: TeamMetrics,
        sos: StrengthOfSchedule,
        transitive_chains: list[TransitiveChain],
    ) -> tuple[RecommendationType, Confidence, str]:
        """Evaluate metrics and determine recommendation type.

        Args:
            team: Team being analyzed.
            metrics: Calculated team metrics.
            sos: Strength of schedule analysis.
            transitive_chains: Detected transitive variance chains.

        Returns:
            Tuple of (recommendation_type, confidence, explanation).
        """
        grade = _ensure_grade_enum(team.assigned_grade)
        grade_str = _get_grade_value(team.assigned_grade)

        # PROMOTE: Dominating current grade
        if metrics.is_dominant and grade and can_promote(grade):
            new_grade = grade_above(grade)
            new_grade_str = _get_grade_value(new_grade)
            confidence = Confidence.HIGH if metrics.blowout_wins >= 4 else Confidence.MEDIUM

            return (
                RecommendationType.PROMOTE,
                confidence,
                f"{team.team_name} is dominating at {grade_str} grade. "
                f"Won {metrics.blowout_wins} games by 20+ points with no blowout losses. "
                f"Recommend promotion to {new_grade_str or 'higher grade'}.",
            )

        # DEMOTE: Struggling at current grade
        if metrics.is_struggling and grade and can_demote(grade):
            new_grade = grade_below(grade)
            new_grade_str = _get_grade_value(new_grade)
            confidence = Confidence.HIGH if metrics.blowout_losses >= 4 else Confidence.MEDIUM

            return (
                RecommendationType.DEMOTE,
                confidence,
                f"{team.team_name} is struggling at {grade_str} grade. "
                f"Lost {metrics.blowout_losses} games by 20+ points with no blowout wins. "
                f"Recommend demotion to {new_grade_str or 'lower grade'}.",
            )

        # MONITOR: Approaching thresholds
        if metrics.blowout_wins >= 2 or metrics.blowout_losses >= 2:
            trend = "improvement" if metrics.blowout_wins > metrics.blowout_losses else "decline"
            return (
                RecommendationType.MONITOR,
                Confidence.MEDIUM,
                f"{team.team_name} showing signs of {trend} at {grade_str or 'current'} grade. "
                f"Blowout W: {metrics.blowout_wins}, Blowout L: {metrics.blowout_losses}. "
                "Monitor closely over next 1-2 rounds.",
            )

        # REVIEW_NEEDED: Significant transitive concerns
        if transitive_chains and any(c.implied_variance >= 50 for c in transitive_chains):
            return (
                RecommendationType.REVIEW_NEEDED,
                Confidence.MEDIUM,
                f"Transitive variance detected for {team.team_name}. "
                "Analysis suggests potential grade mismatch through indirect comparison. "
                "Manual review recommended.",
            )

        # NO_CHANGE: Playing at appropriate level
        return (
            RecommendationType.NO_CHANGE,
            Confidence.HIGH,
            f"{team.team_name} is appropriately placed at {grade_str or 'current'} grade. "
            f"Competitive results (Avg margin: {metrics.avg_margin:+.1f}, "
            f"Win rate: {metrics.win_rate}%). No grade change recommended.",
        )

    def _create_recommendation(
        self,
        team: TeamSeason,
        rec_type: RecommendationType,
        confidence: Confidence,
        explanation: str,
        evidence: list[str],
        concerns: list[str],
        sos: StrengthOfSchedule,
        transitive_chains: list[TransitiveChain],
    ) -> Recommendation:
        """Create a Recommendation object with all details.

        Args:
            team: Team being recommended.
            rec_type: Type of recommendation.
            confidence: Confidence level.
            explanation: Human-readable explanation.
            evidence: List of supporting facts.
            concerns: List of caveats or issues.
            sos: SoS analysis.
            transitive_chains: Detected chains.

        Returns:
            Complete Recommendation object.
        """
        current_grade = _get_grade_value(team.assigned_grade)
        recommended_grade: str | None = None

        grade_enum = _ensure_grade_enum(team.assigned_grade)
        if rec_type == RecommendationType.PROMOTE and grade_enum:
            new_grade = grade_above(grade_enum)
            recommended_grade = _get_grade_value(new_grade)
        elif rec_type == RecommendationType.DEMOTE and grade_enum:
            new_grade = grade_below(grade_enum)
            recommended_grade = _get_grade_value(new_grade)

        # Build SoS note
        sos_note = sos.get_summary() if sos.total_games > 0 else None

        # Build transitive note
        transitive_note: str | None = None
        if transitive_chains:
            chain_strs = [str(c) for c in transitive_chains[:3]]
            transitive_note = "\n".join(chain_strs)

        return Recommendation(
            team_name=team.team_name,
            sheet_name=team.sheet_name,
            current_grade=current_grade,
            recommended_grade=recommended_grade,
            recommendation_type=rec_type,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence,
            concerns=concerns,
            strength_of_schedule_note=sos_note,
            transitive_variance_note=transitive_note,
        )

    def generate_all_recommendations(
        self,
        teams: list[TeamSeason],
    ) -> list[Recommendation]:
        """Generate recommendations for all teams.

        Args:
            teams: List of all teams to analyze.

        Returns:
            List of recommendations, one per team.
        """
        return [self.generate_recommendation(team, teams) for team in teams]
