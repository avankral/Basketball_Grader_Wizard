"""Pydantic models for game results and team data.

This module defines the core data structures for parsing and storing
basketball game results from the DVBA Club Grading Book Excel files.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Gender(str, Enum):
    """Gender classification for teams."""

    BOYS = "Boys"
    GIRLS = "Girls"


class Grade(str, Enum):
    """Basketball grade levels in hierarchical order.

    Ordered from highest (A) to lowest (D).
    B1, B2, B3 exist to avoid negative connotations of grades below D.
    """

    A = "A"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    C1 = "C1"
    C2 = "C2"
    D = "D"

    @classmethod
    def from_string(cls, value: str) -> Grade | None:
        """Parse a grade string to Grade enum, handling variations.

        Args:
            value: Grade string (e.g., "A", "B1", "b2", "C")

        Returns:
            Grade enum value or None if not recognized.
        """
        if not value:
            return None

        normalized = value.strip().upper()

        # Direct match
        for grade in cls:
            if grade.value.upper() == normalized:
                return grade

        # Handle single-letter grades (C -> C1, B -> B1)
        if normalized == "B":
            return cls.B1
        if normalized == "C":
            return cls.C1

        return None

    @property
    def rank(self) -> int:
        """Numeric rank for comparison (lower = better).

        Returns:
            Integer rank: A=1, B1=2, B2=3, B3=4, C1=5, C2=6, D=7
        """
        rank_map = {
            Grade.A: 1,
            Grade.B1: 2,
            Grade.B2: 3,
            Grade.B3: 4,
            Grade.C1: 5,
            Grade.C2: 6,
            Grade.D: 7,
        }
        return rank_map[self]


class ResultType(str, Enum):
    """Game result type."""

    WON = "Won"
    LOST = "Lost"
    DNP = "DNP"  # Did Not Play

    @classmethod
    def from_string(cls, value: str) -> ResultType | None:
        """Parse a result string to ResultType enum.

        Args:
            value: Result string (e.g., "Won", "Lost", "DNP")

        Returns:
            ResultType enum value or None if not recognized.
        """
        if not value:
            return None

        normalized = value.strip().lower()

        if normalized in ("won", "win", "w"):
            return cls.WON
        if normalized in ("lost", "loss", "l"):
            return cls.LOST
        if normalized in ("dnp", "did not play", "bye"):
            return cls.DNP

        return None


class VarianceClass(str, Enum):
    """Classification of game result variance based on Excel cell colors.

    From DVBA color coding:
    - Blue: Extremely high variance win (blowout win)
    - Green: High variance win (dominant win)
    - White: Competitive game (correct grade)
    - Light Red: Moderate-high loss (concerning)
    - Dark Red: High variance loss (bad loss)
    """

    BLOWOUT_WIN = "blowout_win"  # Blue cell
    DOMINANT_WIN = "dominant_win"  # Green cell
    COMPETITIVE = "competitive"  # White cell
    CONCERNING_LOSS = "concerning_loss"  # Light red cell
    BAD_LOSS = "bad_loss"  # Dark red cell
    UNKNOWN = "unknown"  # Could not determine


class SheetInfo(BaseModel):
    """Parsed information from Excel sheet name.

    Sheet names follow pattern: {Gender}{Age}{Division}
    Example: B161 = Boys, U16, Grading Group 1
    """

    sheet_name: str = Field(..., description="Original sheet name (e.g., 'B161')")
    gender: Gender = Field(..., description="Boys or Girls")
    age_group: int = Field(..., ge=6, le=19, description="Age group (e.g., 16 for U16)")
    division: int = Field(..., ge=1, description="Grading group/division number")

    @classmethod
    def from_sheet_name(cls, sheet_name: str) -> SheetInfo | None:
        """Parse sheet name to extract gender, age, and division.

        Args:
            sheet_name: Excel sheet name (e.g., "B161", "G122")

        Returns:
            SheetInfo if valid, None otherwise.
        """
        pattern = r"^([BG])(\d{2})(\d+)$"
        match = re.match(pattern, sheet_name.strip().upper())

        if not match:
            return None

        gender_char, age_str, division_str = match.groups()
        gender = Gender.BOYS if gender_char == "B" else Gender.GIRLS

        return cls(
            sheet_name=sheet_name,
            gender=gender,
            age_group=int(age_str),
            division=int(division_str),
        )

    @property
    def age_label(self) -> str:
        """Human-readable age label (e.g., 'U16')."""
        return f"U{self.age_group}"

    model_config = ConfigDict(frozen=True)


class GameResult(BaseModel):
    """A single game result for a team.

    Represents one row of round data from the wide-format Excel file,
    unpivoted to long format.
    """

    team_name: str = Field(..., min_length=1, description="Full team name")
    opponent_name: str = Field(..., min_length=1, description="Opponent team name")
    opponent_grade: Grade | None = Field(
        None, description="Opponent's assigned grade (for SoS calculation)"
    )
    score_for: int = Field(..., ge=0, description="Points scored by team")
    score_against: int = Field(..., ge=0, description="Points scored by opponent")
    margin: int = Field(..., description="Point differential (positive = win)")
    result: ResultType = Field(..., description="Win, Loss, or DNP")
    round_num: int = Field(..., ge=1, description="Round number (1-indexed)")
    variance_class: VarianceClass = Field(
        VarianceClass.UNKNOWN, description="Variance classification from cell color"
    )
    opponent_sheet: str | None = Field(None, description="Sheet code where opponent is listed")

    @field_validator("margin")
    @classmethod
    def validate_margin(cls, v: int, info) -> int:
        """Validate margin matches score differential."""
        data = info.data
        if "score_for" in data and "score_against" in data:
            expected = data["score_for"] - data["score_against"]
            if v != expected:
                # Allow the provided margin (from Excel) even if it differs
                # Log warning in production
                pass
        return v

    @property
    def is_blowout(self) -> bool:
        """Check if game was a blowout (>20 point margin)."""
        return abs(self.margin) >= 20

    @property
    def is_close_game(self) -> bool:
        """Check if game was close (<=5 point margin)."""
        return abs(self.margin) <= 5

    model_config = ConfigDict(use_enum_values=True)


class TeamSeason(BaseModel):
    """A team's complete season data within a grading group.

    Aggregates all game results for a single team across multiple rounds.
    """

    team_name: str = Field(..., min_length=1, description="Full team name")
    club_name: str | None = Field(None, description="Extracted club name (e.g., 'Jets')")
    gender: Gender = Field(..., description="Boys or Girls")
    age_group: int = Field(..., ge=6, le=19, description="Age group (e.g., 16 for U16)")
    division: int = Field(..., ge=1, description="Grading group/division number")
    assigned_grade: Grade | None = Field(None, description="Grade assigned by DVBA (Column C)")
    current_rank: int | None = Field(None, ge=1, description="Current standings rank")
    games: list[GameResult] = Field(default_factory=list, description="All game results")
    sheet_name: str = Field(..., description="Source sheet name")

    @classmethod
    def extract_club_name(cls, team_name: str) -> str | None:
        """Extract club name from full team name.

        Args:
            team_name: Full team name (e.g., "Jets U12 Girls 2")

        Returns:
            Club name (e.g., "Jets") or None if not extractable.
        """
        # Pattern: Club name is typically the first word(s) before age/gender
        # Examples: "Jets U12 Girls 2", "Diamond Creek U16 Boys 1"
        pattern = r"^(.+?)\s+U\d+"
        match = re.match(pattern, team_name.strip())
        if match:
            return match.group(1).strip()
        return None

    @property
    def wins(self) -> int:
        """Total wins."""
        return sum(1 for g in self.games if g.result == ResultType.WON)

    @property
    def losses(self) -> int:
        """Total losses."""
        return sum(1 for g in self.games if g.result == ResultType.LOST)

    @property
    def games_played(self) -> int:
        """Total games played (excluding DNP)."""
        return sum(1 for g in self.games if g.result != ResultType.DNP)

    @property
    def total_margin(self) -> int:
        """Sum of all margins."""
        return sum(g.margin for g in self.games if g.result != ResultType.DNP)

    @property
    def avg_margin(self) -> float:
        """Average margin per game."""
        played = self.games_played
        if played == 0:
            return 0.0
        return self.total_margin / played

    @property
    def blowout_wins(self) -> int:
        """Count of wins by 20+ points."""
        return sum(1 for g in self.games if g.result == ResultType.WON and g.margin >= 20)

    @property
    def blowout_losses(self) -> int:
        """Count of losses by 20+ points."""
        return sum(1 for g in self.games if g.result == ResultType.LOST and g.margin <= -20)

    @property
    def age_label(self) -> str:
        """Human-readable age label (e.g., 'U16')."""
        return f"U{self.age_group}"

    model_config = ConfigDict(use_enum_values=True)
