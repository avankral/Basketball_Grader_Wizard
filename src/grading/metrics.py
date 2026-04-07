"""Team performance metrics with grade-weighted calculations.

Provides detailed performance analysis that accounts for the quality
of opposition faced. Key features:
- Weighted wins/losses based on opponent grade
- Blowout detection (20+ point margins)
- Close game analysis (5 or fewer points)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.grading.grades import GRADE_RANK, get_grade_weight
from src.models.game_result import GameResult, Grade, ResultType, TeamSeason

# Configurable thresholds
BLOWOUT_MARGIN = 20  # Points difference for blowout classification
CLOSE_GAME_MARGIN = 5  # Points difference for close game classification
MIN_GAMES_FOR_RECOMMENDATION = 3  # Minimum games before making recommendations


@dataclass
class TeamMetrics:
    """Comprehensive performance metrics for a team.

    Includes both raw statistics and grade-weighted metrics that
    account for opponent quality.
    """

    team_name: str
    assigned_grade: Grade | None

    # Raw stats
    wins: int = 0
    losses: int = 0
    dnp_count: int = 0
    total_margin: int = 0
    points_for: int = 0
    points_against: int = 0

    # Blowout analysis
    blowout_wins: int = 0
    blowout_losses: int = 0
    blowout_win_games: list[GameResult] = field(default_factory=list)
    blowout_loss_games: list[GameResult] = field(default_factory=list)

    # Close game analysis
    close_wins: int = 0
    close_losses: int = 0

    # Grade-weighted metrics
    weighted_wins: float = 0.0
    weighted_losses: float = 0.0
    weighted_margin: float = 0.0

    # Results by opponent grade
    results_vs_higher: dict = field(default_factory=lambda: {"W": 0, "L": 0})
    results_vs_same: dict = field(default_factory=lambda: {"W": 0, "L": 0})
    results_vs_lower: dict = field(default_factory=lambda: {"W": 0, "L": 0})

    @property
    def games_played(self) -> int:
        """Total games played (excluding DNP)."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        """Win percentage (0-100)."""
        if self.games_played == 0:
            return 0.0
        return round(self.wins / self.games_played * 100, 1)

    @property
    def avg_margin(self) -> float:
        """Average point differential per game."""
        if self.games_played == 0:
            return 0.0
        return round(self.total_margin / self.games_played, 1)

    @property
    def weighted_win_rate(self) -> float:
        """Weighted win percentage accounting for opponent quality."""
        total_weighted = self.weighted_wins + self.weighted_losses
        if total_weighted == 0:
            return 0.0
        return round(self.weighted_wins / total_weighted * 100, 1)

    @property
    def blowout_ratio(self) -> float:
        """Ratio of blowout wins to blowout losses.

        Returns:
            Positive = more blowout wins, negative = more blowout losses.
        """
        return self.blowout_wins - self.blowout_losses

    @property
    def is_dominant(self) -> bool:
        """Check if team is dominating their grade level."""
        return self.blowout_wins >= 3 and self.blowout_losses == 0 and self.win_rate >= 80

    @property
    def is_struggling(self) -> bool:
        """Check if team is struggling at their grade level."""
        return self.blowout_losses >= 3 and self.blowout_wins == 0 and self.win_rate <= 20

    @property
    def has_sufficient_data(self) -> bool:
        """Check if team has enough games for reliable analysis."""
        return self.games_played >= MIN_GAMES_FOR_RECOMMENDATION

    def get_summary(self) -> str:
        """Generate human-readable summary."""
        parts = [
            f"{self.wins}W-{self.losses}L",
            f"Avg Margin: {self.avg_margin:+.1f}",
        ]

        if self.blowout_wins > 0:
            parts.append(f"Blowout W: {self.blowout_wins}")
        if self.blowout_losses > 0:
            parts.append(f"Blowout L: {self.blowout_losses}")

        return " | ".join(parts)


def calculate_team_metrics(team: TeamSeason) -> TeamMetrics:
    """Calculate comprehensive metrics for a team.

    Args:
        team: TeamSeason with game history.

    Returns:
        TeamMetrics with raw and weighted statistics.
    """
    metrics = TeamMetrics(
        team_name=team.team_name,
        assigned_grade=team.assigned_grade,
    )

    for game in team.games:
        if game.result == ResultType.DNP:
            metrics.dnp_count += 1
            continue

        # Basic stats
        metrics.points_for += game.score_for
        metrics.points_against += game.score_against
        metrics.total_margin += game.margin

        is_win = game.result == ResultType.WON
        is_blowout = abs(game.margin) >= BLOWOUT_MARGIN
        is_close = abs(game.margin) <= CLOSE_GAME_MARGIN

        if is_win:
            metrics.wins += 1
            if is_blowout:
                metrics.blowout_wins += 1
                metrics.blowout_win_games.append(game)
            if is_close:
                metrics.close_wins += 1
        else:
            metrics.losses += 1
            if is_blowout:
                metrics.blowout_losses += 1
                metrics.blowout_loss_games.append(game)
            if is_close:
                metrics.close_losses += 1

        # Grade-weighted calculations
        if game.opponent_grade and team.assigned_grade:
            weight = get_grade_weight(team.assigned_grade, game.opponent_grade)
            team_rank = GRADE_RANK[team.assigned_grade]
            opp_rank = GRADE_RANK[game.opponent_grade]

            if is_win:
                metrics.weighted_wins += weight
            else:
                metrics.weighted_losses += weight

            metrics.weighted_margin += game.margin * weight

            # Track results by relative grade
            key = "W" if is_win else "L"
            if opp_rank < team_rank:
                metrics.results_vs_higher[key] += 1
            elif opp_rank > team_rank:
                metrics.results_vs_lower[key] += 1
            else:
                metrics.results_vs_same[key] += 1

    return metrics
