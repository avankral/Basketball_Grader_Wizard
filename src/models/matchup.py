"""Pydantic models for matchup recommendations and round analysis.

This module defines data structures for the round scheduling optimizer,
including matchup recommendations, round analysis, and outcome tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.models.game_result import GameResult, Grade


class MatchupType(str, Enum):
    """Type of matchup recommendation."""

    SAME_GRADE = "same_grade"  # Teams from the same grade
    CROSS_GRADE_UP = "cross_grade_up"  # Lower-grade team playing up
    CROSS_GRADE_DOWN = "cross_grade_down"  # Higher-grade team playing down


class MatchupStatus(str, Enum):
    """Status of a matchup recommendation."""

    PENDING = "pending"  # Awaiting admin approval
    APPROVED = "approved"  # Admin approved
    REJECTED = "rejected"  # Admin rejected


class MatchupConfidence(str, Enum):
    """Confidence level in the matchup recommendation."""

    HIGH = "high"  # Strong evidence, likely to reduce variance
    MEDIUM = "medium"  # Moderate evidence
    LOW = "low"  # Speculative, experimental


class MatchupRecommendation(BaseModel):
    """A recommended matchup between two teams.

    Contains the pairing, justification, and expected variance reduction.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique matchup ID")
    round_num: int = Field(..., ge=1, description="Round number for this matchup")
    team_a_name: str = Field(..., min_length=1, description="First team name")
    team_a_grade: Grade | None = Field(None, description="First team's current grade")
    team_b_name: str = Field(..., min_length=1, description="Second team name")
    team_b_grade: Grade | None = Field(None, description="Second team's current grade")
    matchup_type: MatchupType = Field(..., description="Type of matchup")
    status: MatchupStatus = Field(MatchupStatus.PENDING, description="Current approval status")
    confidence: MatchupConfidence = Field(..., description="Confidence level")
    justification: str | None = Field(
        None,
        description="Human-readable justification (required for cross-grade)",
    )
    variance_reduction_estimate: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Estimated variance reduction (0-100%)",
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="When recommendation was generated"
    )

    # Context about why this matchup was suggested
    team_a_recent_margin: float | None = Field(
        None, description="Team A's average margin in recent games"
    )
    team_b_recent_margin: float | None = Field(
        None, description="Team B's average margin in recent games"
    )

    @property
    def is_cross_grade(self) -> bool:
        """Check if this is a cross-grade matchup."""
        return self.matchup_type in (
            MatchupType.CROSS_GRADE_UP,
            MatchupType.CROSS_GRADE_DOWN,
        )

    @property
    def requires_justification(self) -> bool:
        """Check if this matchup requires a justification."""
        return self.is_cross_grade and not self.justification

    model_config = ConfigDict(use_enum_values=True)


class HighVarianceGame(BaseModel):
    """A game identified as having high variance.

    Used to flag games that contributed to grade imbalance.
    """

    game: GameResult = Field(..., description="The game result")
    variance_percentage: float = Field(
        ..., ge=0.0, description="Variance as percentage of total points"
    )
    winner_should: str = Field(
        ..., description="Recommendation for winner: 'play_up', 'stay', or 'monitor'"
    )
    loser_should: str = Field(
        ..., description="Recommendation for loser: 'play_down', 'stay', or 'monitor'"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)


class RoundAnalysis(BaseModel):
    """Analysis of a single round's results.

    Contains variance metrics and identified high-variance games.
    """

    round_num: int = Field(..., ge=1, description="Round number analyzed")
    total_games: int = Field(..., ge=0, description="Total games played in round")
    high_variance_games: list[HighVarianceGame] = Field(
        default_factory=list, description="Games exceeding variance threshold"
    )
    grade_std_devs: dict[str, float] = Field(
        default_factory=dict,
        description="Standard deviation of margins by grade (grade -> std dev)",
    )
    avg_variance_percentage: float = Field(
        0.0, ge=0.0, description="Average variance percentage across all games"
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="When analysis was performed"
    )

    @property
    def high_variance_count(self) -> int:
        """Count of high variance games."""
        return len(self.high_variance_games)

    @property
    def has_issues(self) -> bool:
        """Check if round has significant variance issues."""
        return self.high_variance_count > 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MatchupOutcome(BaseModel):
    """Recorded outcome of a matchup for historical learning.

    Tracks whether predictions were accurate to improve future recommendations.
    """

    matchup_id: str = Field(..., description="Reference to the MatchupRecommendation")
    round_num: int = Field(..., ge=1, description="Round when matchup occurred")
    team_a_name: str = Field(..., description="First team name")
    team_b_name: str = Field(..., description="Second team name")
    predicted_margin_range: tuple[int, int] = Field(
        ..., description="Expected margin range (low, high)"
    )
    actual_margin: int = Field(..., description="Actual point differential")
    variance_reduced: bool = Field(..., description="Whether the matchup reduced overall variance")
    prediction_accurate: bool = Field(
        ..., description="Whether actual margin fell within predicted range"
    )
    recorded_at: datetime = Field(
        default_factory=datetime.now, description="When outcome was recorded"
    )

    model_config = ConfigDict()


class ByeAssignment(BaseModel):
    """A bye assignment for a team in a round.

    Tracks bye rotations for fairness.
    """

    team_name: str = Field(..., description="Team receiving the bye")
    round_num: int = Field(..., ge=1, description="Round number")
    reason: str = Field("rotation", description="Reason for bye: 'rotation', 'odd_count', etc.")
    assigned_at: datetime = Field(default_factory=datetime.now, description="When bye was assigned")

    model_config = ConfigDict()
