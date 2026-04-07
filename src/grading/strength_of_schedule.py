"""Strength of Schedule (SoS) calculation engine.

Analyzes the quality of opponents a team has faced to provide
context for their results. Key insight: a competitive loss to an
A-grade team is more valuable than a blowout win against D-grade.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from src.grading.grades import GRADE_ORDER, GRADE_RANK
from src.models.game_result import Grade, ResultType, TeamSeason


@dataclass
class StrengthOfSchedule:
    """Strength of Schedule analysis for a team.

    Attributes:
        team_name: Team being analyzed.
        assigned_grade: Team's DVBA-assigned grade.
        opponent_grades_faced: Count of games per opponent grade.
        avg_opponent_rank: Average numeric rank of opponents (lower = harder schedule).
        grade_coverage: Whether team played any games at their assigned grade.
        played_above_count: Games against higher-graded opponents.
        played_at_grade_count: Games against same-grade opponents.
        played_below_count: Games against lower-graded opponents.
        never_played_at_grade: Flag for teams who never faced their assigned grade.
        grade_distribution: Percentage breakdown of opponent grades.
    """

    team_name: str
    assigned_grade: Grade | None
    opponent_grades_faced: Counter = field(default_factory=Counter)
    avg_opponent_rank: float = 0.0
    grade_coverage: bool = False
    played_above_count: int = 0
    played_at_grade_count: int = 0
    played_below_count: int = 0
    never_played_at_grade: bool = False
    grade_distribution: dict[str, float] = field(default_factory=dict)
    total_games: int = 0

    @property
    def schedule_difficulty(self) -> str:
        """Classify schedule difficulty based on opponent ranks."""
        if self.total_games == 0:
            return "No games"

        if self.avg_opponent_rank <= 2.0:
            return "Very Hard"
        elif self.avg_opponent_rank <= 3.5:
            return "Hard"
        elif self.avg_opponent_rank <= 5.0:
            return "Moderate"
        else:
            return "Easy"

    @property
    def sos_score(self) -> float:
        """Numeric SoS score (higher = harder schedule).

        Scale: 0-100 where 100 = all A-grade opponents.
        """
        if self.total_games == 0:
            return 0.0

        # Convert avg rank to 0-100 scale (A=100, D=0)
        max_rank = len(GRADE_ORDER)
        normalized = (max_rank - self.avg_opponent_rank + 1) / max_rank
        return round(normalized * 100, 1)

    def get_summary(self) -> str:
        """Generate human-readable summary for UI/reports."""
        if self.total_games == 0:
            return "No games played yet."

        parts = [f"SoS Score: {self.sos_score}/100 ({self.schedule_difficulty})"]

        if self.never_played_at_grade and self.assigned_grade:
            grade_str = (
                self.assigned_grade.value
                if hasattr(self.assigned_grade, "value")
                else str(self.assigned_grade)
            )
            parts.append(f"⚠️ Never played at assigned grade ({grade_str})")

        if self.played_above_count > 0:
            parts.append(f"Played UP: {self.played_above_count} games")
        if self.played_below_count > 0:
            parts.append(f"Played DOWN: {self.played_below_count} games")

        return " | ".join(parts)


def calculate_sos(team: TeamSeason) -> StrengthOfSchedule:
    """Calculate Strength of Schedule for a team.

    Args:
        team: TeamSeason with game history.

    Returns:
        StrengthOfSchedule analysis object.
    """
    sos = StrengthOfSchedule(
        team_name=team.team_name,
        assigned_grade=team.assigned_grade,
    )

    # Filter to played games with known opponent grades
    played_games = [
        g for g in team.games if g.result != ResultType.DNP and g.opponent_grade is not None
    ]

    if not played_games:
        return sos

    sos.total_games = len(played_games)

    # Count opponent grades
    for game in played_games:
        if game.opponent_grade:
            sos.opponent_grades_faced[game.opponent_grade] += 1

    # Calculate average opponent rank
    total_rank = sum(
        GRADE_RANK[game.opponent_grade] for game in played_games if game.opponent_grade
    )
    sos.avg_opponent_rank = total_rank / len(played_games)

    # Analyze grade coverage relative to assigned grade
    if team.assigned_grade:
        team_rank = GRADE_RANK[team.assigned_grade]

        for game in played_games:
            if game.opponent_grade:
                opp_rank = GRADE_RANK[game.opponent_grade]
                if opp_rank < team_rank:
                    sos.played_above_count += 1
                elif opp_rank > team_rank:
                    sos.played_below_count += 1
                else:
                    sos.played_at_grade_count += 1

        sos.grade_coverage = sos.played_at_grade_count > 0
        sos.never_played_at_grade = sos.played_at_grade_count == 0

    # Calculate grade distribution percentages
    for grade in GRADE_ORDER:
        count = sos.opponent_grades_faced.get(grade, 0)
        grade_key = grade.value if hasattr(grade, "value") else str(grade)
        sos.grade_distribution[grade_key] = round(count / len(played_games) * 100, 1)

    return sos


def compare_sos(sos1: StrengthOfSchedule, sos2: StrengthOfSchedule) -> int:
    """Compare two teams' strength of schedule.

    Args:
        sos1: First team's SoS.
        sos2: Second team's SoS.

    Returns:
        Negative if sos1 harder, positive if sos2 harder, 0 if equal.
    """
    return int((sos1.avg_opponent_rank - sos2.avg_opponent_rank) * 100)
