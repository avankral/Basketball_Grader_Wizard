"""Pydantic models for recommendations and overrides.

This module defines data structures for grade movement recommendations
and admin override tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RecommendationType(str, Enum):
    """Type of grade movement recommendation."""

    PROMOTE = "promote"  # Move up a grade
    DEMOTE = "demote"  # Move down a grade
    MONITOR = "monitor"  # Watch closely, approaching threshold
    NO_CHANGE = "no_change"  # Stay in current grade
    REVIEW_NEEDED = "review_needed"  # Requires human judgment


class Confidence(str, Enum):
    """Confidence level in the recommendation."""

    HIGH = "high"  # Strong evidence, clear decision
    MEDIUM = "medium"  # Moderate evidence, likely correct
    LOW = "low"  # Weak evidence, uncertain


class Recommendation(BaseModel):
    """A grade movement recommendation for a team.

    Contains the recommendation type, supporting evidence,
    and human-readable explanation suitable for DVBA communication.
    """

    team_name: str = Field(..., description="Full team name")
    sheet_name: str = Field(..., description="Source sheet name")
    current_grade: str | None = Field(None, description="Currently assigned grade")
    recommended_grade: str | None = Field(None, description="Suggested new grade")
    recommendation_type: RecommendationType = Field(..., description="Type of recommendation")
    confidence: Confidence = Field(..., description="Confidence level")
    explanation: str = Field(
        ...,
        min_length=1,
        description="Human-readable explanation for parents/admin",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="List of supporting game results or facts",
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="List of ambiguous factors or caveats",
    )
    strength_of_schedule_note: str | None = Field(None, description="SoS analysis summary")
    transitive_variance_note: str | None = Field(
        None, description="Transitive variance chain if detected"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="When recommendation was generated"
    )

    @property
    def requires_action(self) -> bool:
        """Check if recommendation requires admin action."""
        return self.recommendation_type in (
            RecommendationType.PROMOTE,
            RecommendationType.DEMOTE,
            RecommendationType.REVIEW_NEEDED,
        )

    @property
    def is_grade_change(self) -> bool:
        """Check if recommendation suggests a grade change."""
        return self.recommendation_type in (
            RecommendationType.PROMOTE,
            RecommendationType.DEMOTE,
        )

    model_config = ConfigDict(use_enum_values=True)


class Override(BaseModel):
    """An admin override of a recommendation.

    Tracks when and why an admin chose to accept, reject, or modify
    a system recommendation. Used for audit trail and accountability.
    """

    team_name: str = Field(..., description="Full team name")
    sheet_name: str = Field(..., description="Source sheet name")
    original_recommendation: RecommendationType = Field(
        ..., description="Original system recommendation"
    )
    original_grade: str | None = Field(None, description="Grade before override")
    admin_decision: str = Field(
        ...,
        description="Admin's decision (accept, reject, modify to X)",
    )
    final_grade: str | None = Field(None, description="Final grade after override")
    reason: str = Field(..., min_length=1, description="Admin's justification for override")
    admin_id: str | None = Field(None, description="Admin identifier (if tracked)")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When override was applied"
    )
    season: str | None = Field(None, description="Season identifier (e.g., 'Autumn 2026')")
    round_num: int | None = Field(None, ge=1, description="Round number when override applied")

    model_config = ConfigDict(use_enum_values=True)
