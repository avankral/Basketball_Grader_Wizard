"""Matchup optimization for reducing transitive variance.

Generates recommended matchups based on round analysis, identifying
cross-grade pairings that can help balance grade-level competitiveness.
"""

from __future__ import annotations

from collections import defaultdict

from config import get_settings
from src.grading.grades import grade_above
from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.models.game_result import Grade, TeamSeason
from src.models.matchup import (
    MatchupConfidence,
    MatchupRecommendation,
    MatchupStatus,
    MatchupType,
    RoundAnalysis,
)


class MatchupOptimizer:
    """Generates optimized matchups to reduce variance.

    Analyzes team performance and round results to suggest matchups
    that will create more competitive games and reduce the spread
    within grades.
    """

    def __init__(
        self,
        variance_threshold: float | None = None,
        cross_grade_trigger: float | None = None,
        min_games_for_cross_grade: int | None = None,
    ) -> None:
        """Initialize the matchup optimizer.

        Args:
            variance_threshold: Variance threshold for high-variance detection.
            cross_grade_trigger: Margin that triggers cross-grade consideration.
            min_games_for_cross_grade: Minimum games before cross-grade eligible.
        """
        settings = get_settings()
        self.variance_threshold = (
            variance_threshold
            if variance_threshold is not None
            else settings.variance_threshold_percent
        )
        self.cross_grade_trigger = (
            cross_grade_trigger
            if cross_grade_trigger is not None
            else settings.cross_grade_margin_trigger
        )
        self.min_games_for_cross_grade = (
            min_games_for_cross_grade
            if min_games_for_cross_grade is not None
            else settings.min_games_for_cross_grade
        )

    def generate_matchups(
        self,
        next_round: int,
        teams: list[TeamSeason],
        round_analysis: RoundAnalysis | None = None,
    ) -> list[MatchupRecommendation]:
        """Generate recommended matchups for the next round.

        Args:
            next_round: Round number for the matchups.
            teams: All teams to schedule.
            round_analysis: Analysis of previous round (optional).

        Returns:
            List of matchup recommendations.
        """
        matchups: list[MatchupRecommendation] = []

        # Group teams by age group and gender for valid matchups
        team_groups = self._group_teams_by_category(teams)

        for _group_key, group_teams in team_groups.items():
            # Generate matchups within each age/gender group
            group_matchups = self._generate_group_matchups(next_round, group_teams, round_analysis)
            matchups.extend(group_matchups)

        # Sort by confidence and variance reduction estimate
        matchups.sort(
            key=lambda m: (
                m.confidence != MatchupConfidence.HIGH,
                -m.variance_reduction_estimate,
            )
        )

        return matchups

    def _group_teams_by_category(
        self,
        teams: list[TeamSeason],
    ) -> dict[str, list[TeamSeason]]:
        """Group teams by age group and gender.

        Cross-grade matchups only allowed within same age/gender.

        Args:
            teams: All teams.

        Returns:
            Dictionary mapping category key to teams.
        """
        groups: dict[str, list[TeamSeason]] = defaultdict(list)

        for team in teams:
            # Key: "U12_Boys" or "U16_Girls"
            key = f"U{team.age_group}_{team.gender.value if hasattr(team.gender, 'value') else team.gender}"
            groups[key].append(team)

        return dict(groups)

    def _generate_group_matchups(
        self,
        next_round: int,
        teams: list[TeamSeason],
        round_analysis: RoundAnalysis | None,
    ) -> list[MatchupRecommendation]:
        """Generate matchups within an age/gender group.

        Args:
            next_round: Round number.
            teams: Teams in this group.
            round_analysis: Previous round analysis.

        Returns:
            List of matchup recommendations for this group.
        """
        matchups: list[MatchupRecommendation] = []

        # Identify cross-grade candidates
        play_up_candidates = self._identify_play_up_candidates(teams, round_analysis)
        play_down_candidates = self._identify_play_down_candidates(teams, round_analysis)

        # Track which teams have been matched
        matched_teams: set[str] = set()

        # First, create cross-grade matchups
        cross_grade_matchups = self._create_cross_grade_matchups(
            next_round, play_up_candidates, play_down_candidates, matched_teams
        )
        matchups.extend(cross_grade_matchups)

        # Then, create same-grade matchups for remaining teams
        same_grade_matchups = self._create_same_grade_matchups(next_round, teams, matched_teams)
        matchups.extend(same_grade_matchups)

        return matchups

    def _identify_play_up_candidates(
        self,
        teams: list[TeamSeason],
        round_analysis: RoundAnalysis | None,
    ) -> list[tuple[TeamSeason, float]]:
        """Identify teams that should play up a grade.

        Args:
            teams: Teams in the group.
            round_analysis: Previous round analysis.

        Returns:
            List of (team, avg_margin) tuples, sorted by strength.
        """
        candidates: list[tuple[TeamSeason, float]] = []

        for team in teams:
            if team.games_played < self.min_games_for_cross_grade:
                continue

            # Can't play up from A grade
            if team.assigned_grade == Grade.A:
                continue

            metrics = calculate_team_metrics(team)

            # Check if team is dominating
            if self._should_play_up(metrics, team, round_analysis):
                candidates.append((team, metrics.avg_margin))

        # Sort by avg margin descending (strongest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def _identify_play_down_candidates(
        self,
        teams: list[TeamSeason],
        round_analysis: RoundAnalysis | None,
    ) -> list[tuple[TeamSeason, float]]:
        """Identify teams that should play down a grade.

        Args:
            teams: Teams in the group.
            round_analysis: Previous round analysis.

        Returns:
            List of (team, avg_margin) tuples, sorted by weakness.
        """
        candidates: list[tuple[TeamSeason, float]] = []

        for team in teams:
            if team.games_played < self.min_games_for_cross_grade:
                continue

            # Can't play down from D grade
            if team.assigned_grade == Grade.D:
                continue

            metrics = calculate_team_metrics(team)

            # Check if team is struggling
            if self._should_play_down(metrics, team, round_analysis):
                candidates.append((team, metrics.avg_margin))

        # Sort by avg margin ascending (weakest first)
        candidates.sort(key=lambda x: x[1])
        return candidates

    def _should_play_up(
        self,
        metrics: TeamMetrics,
        team: TeamSeason,
        round_analysis: RoundAnalysis | None,
    ) -> bool:
        """Determine if a team should play up based on metrics.

        Args:
            metrics: Team's performance metrics.
            team: The team.
            round_analysis: Previous round analysis.

        Returns:
            True if team should be considered for playing up.
        """
        # High win rate with dominant margins
        if metrics.win_rate >= 70 and metrics.avg_margin >= 15:
            return True

        # Multiple blowout wins, no blowout losses
        if metrics.blowout_wins >= 2 and metrics.blowout_losses == 0:
            return True

        # Check if in round analysis high variance games as winner
        if round_analysis:
            for hvg in round_analysis.high_variance_games:
                game = hvg.game
                winner = game.team_name if game.margin > 0 else game.opponent_name
                if winner == team.team_name and hvg.winner_should == "play_up":
                    return True

        return False

    def _should_play_down(
        self,
        metrics: TeamMetrics,
        team: TeamSeason,
        round_analysis: RoundAnalysis | None,
    ) -> bool:
        """Determine if a team should play down based on metrics.

        Args:
            metrics: Team's performance metrics.
            team: The team.
            round_analysis: Previous round analysis.

        Returns:
            True if team should be considered for playing down.
        """
        # Low win rate with poor margins
        if metrics.win_rate <= 30 and metrics.avg_margin <= -15:
            return True

        # Multiple blowout losses, no blowout wins
        if metrics.blowout_losses >= 2 and metrics.blowout_wins == 0:
            return True

        # Check if in round analysis high variance games as loser
        if round_analysis:
            for hvg in round_analysis.high_variance_games:
                game = hvg.game
                loser = game.opponent_name if game.margin > 0 else game.team_name
                if loser == team.team_name and hvg.loser_should == "play_down":
                    return True

        return False

    def _create_cross_grade_matchups(
        self,
        next_round: int,
        play_up: list[tuple[TeamSeason, float]],
        play_down: list[tuple[TeamSeason, float]],
        matched: set[str],
    ) -> list[MatchupRecommendation]:
        """Create cross-grade matchups between candidates.

        Pairs strong teams from lower grades with weak teams from
        higher grades to test their true levels.

        Args:
            next_round: Round number.
            play_up: Teams that should play up (strongest first).
            play_down: Teams that should play down (weakest first).
            matched: Set of already matched team names (modified in-place).

        Returns:
            List of cross-grade matchup recommendations.
        """
        matchups: list[MatchupRecommendation] = []

        for team_up, margin_up in play_up:
            if team_up.team_name in matched:
                continue

            # Find a play-down candidate from an adjacent higher grade
            target_grade = grade_above(team_up.assigned_grade)
            if target_grade is None:
                continue

            for team_down, margin_down in play_down:
                if team_down.team_name in matched:
                    continue

                # Check if team_down is in the target grade (or adjacent)
                down_grade = team_down.assigned_grade
                if down_grade and (
                    down_grade == target_grade or down_grade == grade_above(target_grade)
                ):
                    # Create the cross-grade matchup
                    matchup = self._create_matchup(
                        next_round=next_round,
                        team_a=team_up,
                        team_b=team_down,
                        matchup_type=MatchupType.CROSS_GRADE_UP,
                        margin_a=margin_up,
                        margin_b=margin_down,
                    )
                    matchups.append(matchup)
                    matched.add(team_up.team_name)
                    matched.add(team_down.team_name)
                    break

        return matchups

    def _create_same_grade_matchups(
        self,
        next_round: int,
        teams: list[TeamSeason],
        matched: set[str],
    ) -> list[MatchupRecommendation]:
        """Create same-grade matchups for remaining teams.

        Pairs teams within the same grade, trying to match teams
        with similar performance levels.

        Args:
            next_round: Round number.
            teams: All teams in the group.
            matched: Set of already matched team names.

        Returns:
            List of same-grade matchup recommendations.
        """
        matchups: list[MatchupRecommendation] = []

        # Group unmatched teams by grade
        by_grade: dict[str, list[TeamSeason]] = defaultdict(list)
        for team in teams:
            if team.team_name not in matched:
                if team.assigned_grade:
                    grade_key = (
                        team.assigned_grade.value
                        if hasattr(team.assigned_grade, "value")
                        else str(team.assigned_grade)
                    )
                else:
                    grade_key = "Unknown"
                by_grade[grade_key].append(team)

        # Create matchups within each grade
        for _grade, grade_teams in by_grade.items():
            # Sort by avg margin to pair similar teams
            grade_teams.sort(key=lambda t: t.avg_margin, reverse=True)

            # Pair adjacent teams (1st vs 2nd, 3rd vs 4th, etc.)
            for i in range(0, len(grade_teams) - 1, 2):
                team_a = grade_teams[i]
                team_b = grade_teams[i + 1]

                metrics_a = calculate_team_metrics(team_a)
                metrics_b = calculate_team_metrics(team_b)

                matchup = self._create_matchup(
                    next_round=next_round,
                    team_a=team_a,
                    team_b=team_b,
                    matchup_type=MatchupType.SAME_GRADE,
                    margin_a=metrics_a.avg_margin,
                    margin_b=metrics_b.avg_margin,
                )
                matchups.append(matchup)
                matched.add(team_a.team_name)
                matched.add(team_b.team_name)

        return matchups

    def _create_matchup(
        self,
        next_round: int,
        team_a: TeamSeason,
        team_b: TeamSeason,
        matchup_type: MatchupType,
        margin_a: float,
        margin_b: float,
    ) -> MatchupRecommendation:
        """Create a matchup recommendation.

        Args:
            next_round: Round number.
            team_a: First team.
            team_b: Second team.
            matchup_type: Type of matchup.
            margin_a: Team A's average margin.
            margin_b: Team B's average margin.

        Returns:
            MatchupRecommendation object.
        """
        # Determine confidence based on matchup type and data
        confidence = self._calculate_confidence(team_a, team_b, matchup_type)

        # Generate justification for cross-grade matchups
        justification = None
        if matchup_type != MatchupType.SAME_GRADE:
            justification = self._generate_justification(
                team_a, team_b, matchup_type, margin_a, margin_b
            )

        # Estimate variance reduction
        variance_reduction = self._estimate_variance_reduction(margin_a, margin_b, matchup_type)

        return MatchupRecommendation(
            round_num=next_round,
            team_a_name=team_a.team_name,
            team_a_grade=team_a.assigned_grade,
            team_b_name=team_b.team_name,
            team_b_grade=team_b.assigned_grade,
            matchup_type=matchup_type,
            status=MatchupStatus.PENDING,
            confidence=confidence,
            justification=justification,
            variance_reduction_estimate=variance_reduction,
            team_a_recent_margin=margin_a,
            team_b_recent_margin=margin_b,
        )

    def _calculate_confidence(
        self,
        team_a: TeamSeason,
        team_b: TeamSeason,
        matchup_type: MatchupType,
    ) -> MatchupConfidence:
        """Calculate confidence level for a matchup.

        Args:
            team_a: First team.
            team_b: Second team.
            matchup_type: Type of matchup.

        Returns:
            Confidence level.
        """
        # Same grade matchups are generally high confidence
        if matchup_type == MatchupType.SAME_GRADE:
            return MatchupConfidence.HIGH

        # Cross-grade depends on data quality
        games_a = team_a.games_played
        games_b = team_b.games_played

        if games_a >= 4 and games_b >= 4:
            return MatchupConfidence.HIGH
        elif games_a >= 2 and games_b >= 2:
            return MatchupConfidence.MEDIUM
        else:
            return MatchupConfidence.LOW

    def _generate_justification(
        self,
        team_a: TeamSeason,
        team_b: TeamSeason,
        matchup_type: MatchupType,
        margin_a: float,
        margin_b: float,
    ) -> str:
        """Generate human-readable justification for cross-grade matchup.

        Args:
            team_a: First team.
            team_b: Second team.
            matchup_type: Type of matchup.
            margin_a: Team A's average margin.
            margin_b: Team B's average margin.

        Returns:
            Justification string.
        """
        metrics_a = calculate_team_metrics(team_a)
        metrics_b = calculate_team_metrics(team_b)

        # Handle both Grade enum and string types for assigned_grade
        if team_a.assigned_grade:
            grade_a = (
                team_a.assigned_grade.value
                if hasattr(team_a.assigned_grade, "value")
                else str(team_a.assigned_grade)
            )
        else:
            grade_a = "Unknown"

        if team_b.assigned_grade:
            grade_b = (
                team_b.assigned_grade.value
                if hasattr(team_b.assigned_grade, "value")
                else str(team_b.assigned_grade)
            )
        else:
            grade_b = "Unknown"

        if matchup_type == MatchupType.CROSS_GRADE_UP:
            return (
                f"{team_a.team_name} ({grade_a}) is dominating at their current level "
                f"(avg margin: {margin_a:+.1f}, {metrics_a.blowout_wins} blowout wins). "
                f"Testing against {team_b.team_name} ({grade_b}) who is struggling "
                f"(avg margin: {margin_b:+.1f}, {metrics_b.blowout_losses} blowout losses) "
                f"to assess true skill levels."
            )
        elif matchup_type == MatchupType.CROSS_GRADE_DOWN:
            return (
                f"{team_b.team_name} ({grade_b}) may be overgraded based on results "
                f"(avg margin: {margin_b:+.1f}). "
                f"Testing against {team_a.team_name} ({grade_a}) who is performing well "
                f"(avg margin: {margin_a:+.1f}) to validate grade placements."
            )
        else:
            return ""

    def _estimate_variance_reduction(
        self,
        margin_a: float,
        margin_b: float,
        matchup_type: MatchupType,
    ) -> float:
        """Estimate potential variance reduction from this matchup.

        Args:
            margin_a: Team A's average margin.
            margin_b: Team B's average margin.
            matchup_type: Type of matchup.

        Returns:
            Estimated variance reduction (0-100%).
        """
        # Cross-grade matchups have higher potential for variance reduction
        if matchup_type == MatchupType.SAME_GRADE:
            # Similar margins = more competitive = lower variance
            margin_diff = abs(margin_a - margin_b)
            return max(0.0, min(50.0, 50.0 - margin_diff))
        else:
            # Cross-grade: larger margin differences suggest more correction needed
            margin_diff = abs(margin_a - margin_b)
            return min(80.0, margin_diff)


def generate_matchups(
    next_round: int,
    teams: list[TeamSeason],
    round_analysis: RoundAnalysis | None = None,
) -> list[MatchupRecommendation]:
    """Convenience function to generate matchups.

    Args:
        next_round: Round number for matchups.
        teams: All teams.
        round_analysis: Previous round analysis.

    Returns:
        List of matchup recommendations.
    """
    optimizer = MatchupOptimizer()
    return optimizer.generate_matchups(next_round, teams, round_analysis)
