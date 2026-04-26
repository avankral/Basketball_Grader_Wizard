"""Round analysis for variance detection and matchup optimization.

Analyzes results from a single round to identify high-variance games
and calculate grade-level standard deviations. Used to inform
matchup recommendations for reducing transitive variance.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from config import get_settings
from src.models.game_result import GameResult, Grade, ResultType, TeamSeason
from src.models.matchup import HighVarianceGame, RoundAnalysis


class RoundAnalyzer:
    """Analyzes round results to identify variance issues.

    Calculates per-grade standard deviations and identifies games
    that exceed the variance threshold, flagging teams that may
    need cross-grade matchups.
    """

    def __init__(
        self,
        variance_threshold: float | None = None,
        cross_grade_trigger: float | None = None,
    ) -> None:
        """Initialize the round analyzer.

        Args:
            variance_threshold: Variance percentage threshold for high-variance
                classification. Defaults to settings value.
            cross_grade_trigger: Margin percentage that triggers cross-grade
                consideration. Defaults to settings value.
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

    def analyze_round(
        self,
        round_num: int,
        teams: list[TeamSeason],
    ) -> RoundAnalysis:
        """Analyze a single round's results.

        Args:
            round_num: Round number to analyze.
            teams: All teams with their game results.

        Returns:
            RoundAnalysis with variance metrics and flagged games.
        """
        # Collect all games from this round
        round_games: list[GameResult] = []
        for team in teams:
            for game in team.games:
                if game.round_num == round_num and game.result != ResultType.DNP:
                    round_games.append(game)

        # Deduplicate games (each game appears twice, once per team)
        seen_matchups: set[tuple[str, str, int]] = set()
        unique_games: list[GameResult] = []
        for game in round_games:
            # Create canonical key (alphabetically sorted teams)
            teams_key = tuple(sorted([game.team_name, game.opponent_name]))
            matchup_key = (*teams_key, round_num)
            if matchup_key not in seen_matchups:
                seen_matchups.add(matchup_key)
                unique_games.append(game)

        # Calculate variance metrics
        high_variance_games = self._identify_high_variance_games(unique_games, teams)
        grade_std_devs = self._calculate_grade_std_devs(unique_games, teams)
        avg_variance = self._calculate_avg_variance(unique_games)

        return RoundAnalysis(
            round_num=round_num,
            total_games=len(unique_games),
            high_variance_games=high_variance_games,
            grade_std_devs=grade_std_devs,
            avg_variance_percentage=avg_variance,
        )

    def _identify_high_variance_games(
        self,
        games: list[GameResult],
        teams: list[TeamSeason],
    ) -> list[HighVarianceGame]:
        """Identify games exceeding variance threshold.

        Args:
            games: Unique games from the round.
            teams: All teams for grade lookup.

        Returns:
            List of HighVarianceGame objects for flagged games.
        """
        # Build team lookup for grade info
        team_grades: dict[str, Grade | None] = {}
        for team in teams:
            team_grades[team.team_name] = team.assigned_grade

        high_variance: list[HighVarianceGame] = []

        for game in games:
            variance_pct = game.variance_percentage

            if variance_pct >= self.variance_threshold:
                # Determine recommendations for winner and loser
                winner_should, loser_should = self._determine_recommendations(game, team_grades)

                high_variance.append(
                    HighVarianceGame(
                        game=game.model_dump(),
                        variance_percentage=variance_pct,
                        winner_should=winner_should,
                        loser_should=loser_should,
                    )
                )

        # Sort by variance percentage descending
        high_variance.sort(key=lambda x: x.variance_percentage, reverse=True)
        return high_variance

    def _determine_recommendations(
        self,
        game: GameResult,
        team_grades: dict[str, Grade | None],
    ) -> tuple[str, str]:
        """Determine recommendations for winner and loser.

        Analyzes whether the winning team should play up, stay,
        or be monitored, and similarly for the losing team.

        Args:
            game: The game result.
            team_grades: Mapping of team names to grades.

        Returns:
            Tuple of (winner_should, loser_should) recommendation strings.
        """
        variance_pct = game.variance_percentage

        # Determine winner and loser
        if game.margin > 0:
            winner_name = game.team_name
            loser_name = game.opponent_name
        else:
            winner_name = game.opponent_name
            loser_name = game.team_name

        winner_grade = team_grades.get(winner_name)
        loser_grade = team_grades.get(loser_name)

        # Determine winner recommendation
        if variance_pct >= self.cross_grade_trigger:
            winner_should = "play_up"
        elif variance_pct >= self.variance_threshold:
            winner_should = "monitor"
        else:
            winner_should = "stay"

        # Determine loser recommendation
        if variance_pct >= self.cross_grade_trigger:
            loser_should = "play_down"
        elif variance_pct >= self.variance_threshold:
            loser_should = "monitor"
        else:
            loser_should = "stay"

        # Adjust if teams are already at extreme grades
        if winner_grade == Grade.A:
            winner_should = "stay"  # Can't play up from A
        if loser_grade == Grade.D:
            loser_should = "stay"  # Can't play down from D

        return winner_should, loser_should

    def _calculate_grade_std_devs(
        self,
        games: list[GameResult],
        teams: list[TeamSeason],
    ) -> dict[str, float]:
        """Calculate standard deviation of margins by grade.

        Args:
            games: Games from the round.
            teams: All teams for grade lookup.

        Returns:
            Dictionary mapping grade to standard deviation.
        """
        # Build team lookup
        team_grades: dict[str, Grade | None] = {}
        for team in teams:
            team_grades[team.team_name] = team.assigned_grade

        # Group margins by grade
        margins_by_grade: dict[str, list[int]] = defaultdict(list)

        for game in games:
            team_grade = team_grades.get(game.team_name)
            if team_grade:
                grade_key = team_grade.value if isinstance(team_grade, Grade) else str(team_grade)
                margins_by_grade[grade_key].append(abs(game.margin))

        # Calculate std dev for each grade
        std_devs: dict[str, float] = {}
        for grade, margins in margins_by_grade.items():
            if len(margins) >= 2:
                std_devs[grade] = round(statistics.stdev(margins), 2)
            elif len(margins) == 1:
                std_devs[grade] = 0.0  # Single game, no deviation

        return std_devs

    def _calculate_avg_variance(self, games: list[GameResult]) -> float:
        """Calculate average variance percentage across all games.

        Args:
            games: Games from the round.

        Returns:
            Average variance percentage.
        """
        if not games:
            return 0.0

        total_variance = sum(g.variance_percentage for g in games)
        return round(total_variance / len(games), 2)

    def get_teams_needing_adjustment(
        self,
        round_analysis: RoundAnalysis,
        teams: list[TeamSeason],
    ) -> dict[str, list[str]]:
        """Get teams that need grade adjustment based on round analysis.

        Args:
            round_analysis: Completed round analysis.
            teams: All teams.

        Returns:
            Dictionary with 'play_up', 'play_down', 'monitor' lists.
        """
        adjustments: dict[str, list[str]] = {
            "play_up": [],
            "play_down": [],
            "monitor": [],
        }

        seen_teams: set[str] = set()

        for hvg in round_analysis.high_variance_games:
            game = hvg.game

            # Determine winner and loser
            if game.margin > 0:
                winner_name = game.team_name
                loser_name = game.opponent_name
            else:
                winner_name = game.opponent_name
                loser_name = game.team_name

            # Add winner recommendation
            if winner_name not in seen_teams:
                if hvg.winner_should == "play_up":
                    adjustments["play_up"].append(winner_name)
                elif hvg.winner_should == "monitor":
                    adjustments["monitor"].append(winner_name)
                seen_teams.add(winner_name)

            # Add loser recommendation
            if loser_name not in seen_teams:
                if hvg.loser_should == "play_down":
                    adjustments["play_down"].append(loser_name)
                elif hvg.loser_should == "monitor":
                    adjustments["monitor"].append(loser_name)
                seen_teams.add(loser_name)

        return adjustments


def analyze_round(
    round_num: int,
    teams: list[TeamSeason],
    variance_threshold: float | None = None,
) -> RoundAnalysis:
    """Convenience function to analyze a single round.

    Args:
        round_num: Round number to analyze.
        teams: All teams with game results.
        variance_threshold: Optional custom threshold.

    Returns:
        RoundAnalysis with variance metrics.
    """
    analyzer = RoundAnalyzer(variance_threshold=variance_threshold)
    return analyzer.analyze_round(round_num, teams)
