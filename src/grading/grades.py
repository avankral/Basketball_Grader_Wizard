"""Grade hierarchy and comparison utilities.

Defines the ordered grade structure and provides functions for
comparing grades and calculating distances between them.
"""

from __future__ import annotations

from src.models.game_result import Grade

# Ordered list of grades from highest (A) to lowest (D3)
GRADE_ORDER: list[Grade] = [
    Grade.A,
    Grade.AR,
    Grade.B1,
    Grade.B2,
    Grade.B3,
    Grade.B4,
    Grade.C1,
    Grade.C2,
    Grade.C3,
    Grade.D,
    Grade.D1,
    Grade.D2,
    Grade.D3,
]

# Numeric rank mapping (lower = better)
GRADE_RANK: dict[Grade, int] = {grade: idx + 1 for idx, grade in enumerate(GRADE_ORDER)}


def grade_distance(grade1: Grade, grade2: Grade) -> int:
    """Calculate the distance between two grades.

    Args:
        grade1: First grade.
        grade2: Second grade.

    Returns:
        Absolute difference in rank (0 = same grade).

    Example:
        >>> grade_distance(Grade.A, Grade.C1)
        4
    """
    return abs(GRADE_RANK[grade1] - GRADE_RANK[grade2])


def grade_above(grade: Grade) -> Grade | None:
    """Get the grade one level above the given grade.

    Args:
        grade: Current grade.

    Returns:
        Grade one level higher, or None if already at top (A).

    Example:
        >>> grade_above(Grade.B1)
        Grade.A
    """
    idx = GRADE_ORDER.index(grade)
    if idx == 0:
        return None
    return GRADE_ORDER[idx - 1]


def grade_below(grade: Grade) -> Grade | None:
    """Get the grade one level below the given grade.

    Args:
        grade: Current grade.

    Returns:
        Grade one level lower, or None if already at bottom (D).

    Example:
        >>> grade_below(Grade.B1)
        Grade.B2
    """
    idx = GRADE_ORDER.index(grade)
    if idx == len(GRADE_ORDER) - 1:
        return None
    return GRADE_ORDER[idx + 1]


def grades_between(grade1: Grade, grade2: Grade) -> list[Grade]:
    """Get all grades between two grades (exclusive).

    Args:
        grade1: First grade.
        grade2: Second grade.

    Returns:
        List of grades between (not including endpoints).

    Example:
        >>> grades_between(Grade.A, Grade.C1)
        [Grade.B1, Grade.B2, Grade.B3]
    """
    idx1 = GRADE_ORDER.index(grade1)
    idx2 = GRADE_ORDER.index(grade2)

    if idx1 > idx2:
        idx1, idx2 = idx2, idx1

    return GRADE_ORDER[idx1 + 1 : idx2]


def can_promote(grade: Grade) -> bool:
    """Check if a team can be promoted from this grade.

    Args:
        grade: Current grade.

    Returns:
        True if grade is not already at top (A).
    """
    return grade != Grade.A


def can_demote(grade: Grade) -> bool:
    """Check if a team can be demoted from this grade.

    Args:
        grade: Current grade.

    Returns:
        True if grade is not already at bottom (D3).
    """
    return grade != GRADE_ORDER[-1]  # Not at the lowest grade


def is_playing_up(team_grade: Grade, opponent_grade: Grade) -> bool:
    """Check if team is playing against a higher-graded opponent.

    Args:
        team_grade: Team's assigned grade.
        opponent_grade: Opponent's assigned grade.

    Returns:
        True if opponent is higher graded.
    """
    return GRADE_RANK[opponent_grade] < GRADE_RANK[team_grade]


def is_playing_down(team_grade: Grade, opponent_grade: Grade) -> bool:
    """Check if team is playing against a lower-graded opponent.

    Args:
        team_grade: Team's assigned grade.
        opponent_grade: Opponent's assigned grade.

    Returns:
        True if opponent is lower graded.
    """
    return GRADE_RANK[opponent_grade] > GRADE_RANK[team_grade]


def get_grade_weight(team_grade: Grade, opponent_grade: Grade) -> float:
    """Calculate weight multiplier based on opponent grade relative to team.

    Playing up (against better teams) is weighted higher.
    Playing down (against weaker teams) is weighted lower.

    Args:
        team_grade: Team's assigned grade.
        opponent_grade: Opponent's assigned grade.

    Returns:
        Weight multiplier (1.5 for playing up, 1.0 for same, 0.7 for down).
    """
    distance = GRADE_RANK[team_grade] - GRADE_RANK[opponent_grade]

    if distance > 0:
        # Playing up - more valuable
        return 1.0 + (0.15 * min(distance, 3))  # Cap at 1.45 for 3+ grades up
    elif distance < 0:
        # Playing down - less valuable
        return 1.0 - (0.1 * min(abs(distance), 3))  # Floor at 0.7 for 3+ grades down
    else:
        # Same grade
        return 1.0
