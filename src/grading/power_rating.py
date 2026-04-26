"""ELO-based Power Rating System for basketball teams.

Implements a modified ELO rating algorithm that:
- Updates ratings after each game based on expected vs actual outcome
- Accounts for margin of victory with diminishing returns for blowouts
- Tracks rating trajectory over the season
- Compares ratings vs assigned grades to identify mismatches

The system uses a base rating of 1500 for all teams and adjusts based on:
- Game outcomes (win/loss)
- Margin of victory (capped to prevent blowout inflation)
- Opponent strength (current ELO rating)
- Grade-level expectations
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.grading.grades import GRADE_ORDER
from src.models.game_result import Grade, ResultType

if TYPE_CHECKING:
    from src.models.game_result import GameResult, TeamSeason


# ELO Configuration
BASE_RATING = 1500  # Starting rating for all teams
K_FACTOR = 32  # Base K-factor (sensitivity to individual games)
MARGIN_MULTIPLIER = 0.5  # Weight for margin of victory adjustment
MAX_MARGIN_EFFECT = 30  # Cap margin effect to prevent blowout inflation
HOME_ADVANTAGE = 0  # No home advantage for neutral site games

# Grade-based expected rating ranges
GRADE_BASE_RATINGS: dict[Grade, int] = {
    Grade.A: 1800,
    Grade.AR: 1750,
    Grade.B1: 1650,
    Grade.B2: 1600,
    Grade.B3: 1550,
    Grade.B4: 1500,
    Grade.C1: 1450,
    Grade.C2: 1400,
    Grade.C3: 1350,
    Grade.D: 1300,
    Grade.D1: 1250,
    Grade.D2: 1200,
    Grade.D3: 1150,
}


@dataclass
class RatingSnapshot:
    """A point-in-time snapshot of a team's rating."""

    rating: float
    round_num: int
    timestamp: datetime = field(default_factory=datetime.now)
    game_opponent: str | None = None
    game_result: str | None = None
    rating_change: float = 0.0


@dataclass
class TeamPowerRating:
    """Power rating data for a single team.

    Tracks current rating, history, and grade comparison metrics.
    """

    team_name: str
    assigned_grade: Grade | None
    cohort_grades: set[Grade] = field(default_factory=set)
    current_rating: float = BASE_RATING
    peak_rating: float = BASE_RATING
    lowest_rating: float = BASE_RATING
    rating_history: list[RatingSnapshot] = field(default_factory=list)
    games_rated: int = 0

    @property
    def expected_rating(self) -> float:
        """Expected rating based on assigned grade."""
        if self.assigned_grade is None:
            return BASE_RATING
        return GRADE_BASE_RATINGS.get(self.assigned_grade, BASE_RATING)

    @property
    def rating_vs_expected(self) -> float:
        """Difference between actual and expected rating.

        Positive = performing above grade level.
        Negative = performing below grade level.
        """
        return self.current_rating - self.expected_rating

    @property
    def suggested_grade(self) -> Grade | None:
        """Suggest a grade based on current rating.

        Returns:
            Grade that best matches current rating, or None if ungraded.
        """
        if self.games_rated < 3:
            return self.assigned_grade  # Not enough data

        # Find closest grade by rating
        best_grade = None
        min_diff = float("inf")
        candidate_grades = self.cohort_grades or set(GRADE_BASE_RATINGS)

        for grade in GRADE_ORDER:
            if grade not in candidate_grades:
                continue
            expected = GRADE_BASE_RATINGS[grade]
            diff = abs(self.current_rating - expected)
            if diff < min_diff:
                min_diff = diff
                best_grade = grade

        return best_grade

    @property
    def grade_mismatch_severity(self) -> str:
        """Classify severity of grade mismatch.

        Returns:
            'NONE', 'MINOR', 'MODERATE', or 'SEVERE'
        """
        diff = abs(self.rating_vs_expected)
        if diff < 50:
            return "NONE"
        if diff < 100:
            return "MINOR"
        if diff < 150:
            return "MODERATE"
        return "SEVERE"

    @property
    def rating_trend(self) -> str:
        """Calculate recent rating trend.

        Returns:
            'RISING', 'FALLING', or 'STABLE'
        """
        if len(self.rating_history) < 3:
            return "STABLE"

        recent = self.rating_history[-3:]
        changes = [snap.rating_change for snap in recent]
        avg_change = sum(changes) / len(changes)

        if avg_change > 5:
            return "RISING"
        if avg_change < -5:
            return "FALLING"
        return "STABLE"

    def add_snapshot(
        self,
        rating: float,
        round_num: int,
        opponent: str | None = None,
        result: str | None = None,
        change: float = 0.0,
    ) -> None:
        """Record a rating snapshot."""
        self.rating_history.append(
            RatingSnapshot(
                rating=rating,
                round_num=round_num,
                game_opponent=opponent,
                game_result=result,
                rating_change=change,
            )
        )
        self.current_rating = rating
        self.peak_rating = max(self.peak_rating, rating)
        self.lowest_rating = min(self.lowest_rating, rating)
        self.games_rated += 1


def expected_score(rating_a: float, rating_b: float) -> float:
    """Calculate expected score for team A against team B.

    Uses the standard ELO expected score formula:
    E_A = 1 / (1 + 10^((R_B - R_A) / 400))

    Args:
        rating_a: Team A's current rating.
        rating_b: Team B's current rating.

    Returns:
        Expected score (0-1) for team A.
    """
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400))


def margin_multiplier(margin: int, winner_rating: float, loser_rating: float) -> float:
    """Calculate margin of victory multiplier.

    Uses diminishing returns formula to prevent blowout inflation:
    - Small margins have near-linear effect
    - Large margins have logarithmic effect
    - Upset victories (lower-rated team wins) get bonus

    Args:
        margin: Point differential (positive for winner).
        winner_rating: Winner's rating before game.
        loser_rating: Loser's rating before game.

    Returns:
        Multiplier for K-factor (typically 1.0 to 2.0).
    """
    # Cap the margin effect
    capped_margin = min(abs(margin), MAX_MARGIN_EFFECT)

    # Logarithmic diminishing returns
    margin_factor = math.log(capped_margin + 1) / math.log(MAX_MARGIN_EFFECT + 1)

    # Upset bonus: if lower-rated team wins, increase effect
    rating_diff = winner_rating - loser_rating
    upset_bonus = 1.0
    if rating_diff < -100:
        upset_bonus = 1.2  # 20% bonus for upset

    return 1.0 + (MARGIN_MULTIPLIER * margin_factor * upset_bonus)


def calculate_rating_change(
    team_rating: float,
    opponent_rating: float,
    won: bool,
    margin: int,
    k_factor: float = K_FACTOR,
) -> float:
    """Calculate rating change after a game.

    Args:
        team_rating: Team's rating before game.
        opponent_rating: Opponent's rating before game.
        won: Whether the team won.
        margin: Point differential (always positive).
        k_factor: K-factor for sensitivity.

    Returns:
        Rating change (positive or negative).
    """
    expected = expected_score(team_rating, opponent_rating)
    actual = 1.0 if won else 0.0

    # Base change
    base_change = k_factor * (actual - expected)

    # Apply margin multiplier
    if won:
        mult = margin_multiplier(margin, team_rating, opponent_rating)
    else:
        mult = margin_multiplier(margin, opponent_rating, team_rating)

    return base_change * mult


def calculate_power_ratings(teams: list[TeamSeason]) -> dict[str, TeamPowerRating]:
    """Calculate power ratings for all teams based on game history.

    Processes games chronologically by round to simulate season progression.

    Args:
        teams: List of TeamSeason objects with game history.

    Returns:
        Dictionary mapping team name to TeamPowerRating.
    """
    # Initialize ratings
    cohort_grades: dict[tuple[object, int], set[Grade]] = {}
    for team in teams:
        if team.assigned_grade is None:
            continue
        cohort_key = (team.gender, team.age_group)
        cohort_grades.setdefault(cohort_key, set()).add(team.assigned_grade)

    ratings: dict[str, TeamPowerRating] = {}
    for team in teams:
        ratings[team.team_name] = TeamPowerRating(
            team_name=team.team_name,
            assigned_grade=team.assigned_grade,
            cohort_grades=cohort_grades.get((team.gender, team.age_group), set()).copy(),
            current_rating=GRADE_BASE_RATINGS.get(team.assigned_grade, BASE_RATING)
            if team.assigned_grade
            else BASE_RATING,
        )
        # Record initial rating
        ratings[team.team_name].add_snapshot(
            rating=ratings[team.team_name].current_rating,
            round_num=0,
            opponent=None,
            result="Initial",
            change=0.0,
        )

    # Collect all games with round numbers
    all_games: list[tuple[int, TeamSeason, GameResult]] = []
    for team in teams:
        for game in team.games:
            if game.result != ResultType.DNP:
                all_games.append((game.round_num, team, game))

    # Sort by round number
    all_games.sort(key=lambda x: x[0])

    # Process games - track which games we've processed to avoid double-counting
    processed_matchups: set[tuple[int, str, str]] = set()

    for round_num, team, game in all_games:
        # Create unique key for this matchup (sorted team names)
        matchup_key = (
            round_num,
            min(team.team_name, game.opponent_name),
            max(team.team_name, game.opponent_name),
        )

        if matchup_key in processed_matchups:
            continue
        processed_matchups.add(matchup_key)

        team_rating = ratings[team.team_name]

        # Find opponent rating (may not exist if opponent not in our dataset)
        if game.opponent_name in ratings:
            opp_rating = ratings[game.opponent_name]
        else:
            # Estimate opponent rating from their grade
            opp_expected = GRADE_BASE_RATINGS.get(game.opponent_grade, BASE_RATING)
            opp_rating = TeamPowerRating(
                team_name=game.opponent_name,
                assigned_grade=game.opponent_grade,
                current_rating=opp_expected,
            )
            ratings[game.opponent_name] = opp_rating

        won = game.result == ResultType.WON
        margin = abs(game.margin)

        # Calculate rating changes
        team_change = calculate_rating_change(
            team_rating.current_rating,
            opp_rating.current_rating,
            won,
            margin,
        )

        # Update team rating
        new_team_rating = team_rating.current_rating + team_change
        result_str = f"{'W' if won else 'L'} {game.score_for}-{game.score_against}"
        team_rating.add_snapshot(
            rating=new_team_rating,
            round_num=round_num,
            opponent=game.opponent_name,
            result=result_str,
            change=team_change,
        )

        # Update opponent rating (inverse change)
        if game.opponent_name in ratings:
            opp_change = -team_change  # Zero-sum system
            new_opp_rating = opp_rating.current_rating + opp_change
            opp_result = f"{'L' if won else 'W'} {game.score_against}-{game.score_for}"
            opp_rating.add_snapshot(
                rating=new_opp_rating,
                round_num=round_num,
                opponent=team.team_name,
                result=opp_result,
                change=opp_change,
            )

    return ratings


def get_rating_comparison(ratings: dict[str, TeamPowerRating]) -> list[dict]:
    """Generate rating vs grade comparison report.

    Args:
        ratings: Dictionary of team power ratings.

    Returns:
        List of comparison dictionaries sorted by mismatch severity.
    """
    comparisons = []

    for team_name, rating in ratings.items():
        if rating.games_rated < 3:
            continue

        comparisons.append(
            {
                "team_name": team_name,
                "assigned_grade": rating.assigned_grade.value
                if hasattr(rating.assigned_grade, "value")
                else str(rating.assigned_grade)
                if rating.assigned_grade
                else "None",
                "current_rating": round(rating.current_rating, 1),
                "expected_rating": round(rating.expected_rating, 1),
                "rating_diff": round(rating.rating_vs_expected, 1),
                "suggested_grade": rating.suggested_grade.value
                if hasattr(rating.suggested_grade, "value")
                else str(rating.suggested_grade)
                if rating.suggested_grade
                else "None",
                "mismatch_severity": rating.grade_mismatch_severity,
                "trend": rating.rating_trend,
                "peak_rating": round(rating.peak_rating, 1),
                "lowest_rating": round(rating.lowest_rating, 1),
                "games_rated": rating.games_rated,
            }
        )

    # Sort by absolute rating difference (worst mismatches first)
    comparisons.sort(key=lambda x: abs(x["rating_diff"]), reverse=True)

    return comparisons


def get_grade_rating_distribution(ratings: dict[str, TeamPowerRating]) -> dict[str, list[float]]:
    """Get rating distribution per grade for visualization.

    Args:
        ratings: Dictionary of team power ratings.

    Returns:
        Dictionary mapping grade to list of team ratings.
    """
    distribution: dict[str, list[float]] = {}

    for grade in GRADE_ORDER:
        distribution[grade.value] = []

    for rating in ratings.values():
        if rating.assigned_grade and rating.games_rated >= 2:
            grade_key = (
                rating.assigned_grade.value
                if hasattr(rating.assigned_grade, "value")
                else str(rating.assigned_grade)
            )
            if grade_key in distribution:
                distribution[grade_key].append(rating.current_rating)

    return distribution
