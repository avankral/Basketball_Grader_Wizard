"""Parquet storage layer for matchup data persistence.

This module handles saving and loading matchup recommendations and
outcomes to/from Parquet files for historical learning.

Storage structure:
    data/
    └── {season}/
        ├── matchups.parquet         # Recommended matchups
        ├── matchup_outcomes.parquet # Actual outcomes for learning
        └── bye_assignments.parquet  # Bye rotation history
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models.matchup import (
    ByeAssignment,
    MatchupConfidence,
    MatchupOutcome,
    MatchupRecommendation,
    MatchupStatus,
    MatchupType,
)


class MatchupStorage:
    """Parquet-based storage for matchup data.

    Provides methods to save, load, and query matchup recommendations
    and outcomes stored in Parquet format.
    """

    def __init__(self, data_dir: Path | str = "data"):
        """Initialize storage with base data directory.

        Args:
            data_dir: Base directory for data storage.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_season_dir(self, season: str) -> Path:
        """Get or create directory for a season.

        Args:
            season: Season identifier (e.g., "Autumn_2026").

        Returns:
            Path to the season directory.
        """
        season_dir = self.data_dir / season.replace(" ", "_")
        season_dir.mkdir(parents=True, exist_ok=True)
        return season_dir

    def _matchups_path(self, season: str) -> Path:
        """Get path to matchups parquet file."""
        return self._get_season_dir(season) / "matchups.parquet"

    def _outcomes_path(self, season: str) -> Path:
        """Get path to outcomes parquet file."""
        return self._get_season_dir(season) / "matchup_outcomes.parquet"

    def _byes_path(self, season: str) -> Path:
        """Get path to bye assignments parquet file."""
        return self._get_season_dir(season) / "bye_assignments.parquet"

    # --- Matchup Recommendations ---

    def save_matchups(
        self,
        matchups: list[MatchupRecommendation],
        season: str,
        append: bool = True,
    ) -> Path:
        """Save matchup recommendations to Parquet file.

        Args:
            matchups: List of matchup recommendations.
            season: Season identifier.
            append: If True, append to existing data.

        Returns:
            Path to the saved file.
        """
        file_path = self._matchups_path(season)

        # Convert to DataFrame
        records = []
        for m in matchups:
            records.append(
                {
                    "id": m.id,
                    "round_num": m.round_num,
                    "team_a_name": m.team_a_name,
                    "team_a_grade": m.team_a_grade.value
                    if hasattr(m.team_a_grade, "value")
                    else str(m.team_a_grade)
                    if m.team_a_grade
                    else None,
                    "team_b_name": m.team_b_name,
                    "team_b_grade": m.team_b_grade.value
                    if hasattr(m.team_b_grade, "value")
                    else str(m.team_b_grade)
                    if m.team_b_grade
                    else None,
                    "matchup_type": m.matchup_type.value
                    if isinstance(m.matchup_type, MatchupType)
                    else m.matchup_type,
                    "status": m.status.value if isinstance(m.status, MatchupStatus) else m.status,
                    "confidence": m.confidence.value
                    if isinstance(m.confidence, MatchupConfidence)
                    else m.confidence,
                    "justification": m.justification,
                    "variance_reduction_estimate": m.variance_reduction_estimate,
                    "team_a_recent_margin": m.team_a_recent_margin,
                    "team_b_recent_margin": m.team_b_recent_margin,
                    "created_at": m.created_at.isoformat(),
                }
            )

        df = pd.DataFrame(records)

        if append and file_path.exists():
            existing = pd.read_parquet(file_path, engine="pyarrow")
            # Update existing records by id
            existing_ids = set(existing["id"].tolist())
            new_records = df[~df["id"].isin(existing_ids)]
            updated_records = df[df["id"].isin(existing_ids)]

            # Remove old versions of updated records
            existing = existing[~existing["id"].isin(updated_records["id"])]
            df = pd.concat([existing, updated_records, new_records], ignore_index=True)

        df.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def load_matchups(
        self,
        season: str,
        round_num: int | None = None,
    ) -> list[MatchupRecommendation]:
        """Load matchup recommendations from Parquet file.

        Args:
            season: Season identifier.
            round_num: Optional round number to filter.

        Returns:
            List of matchup recommendations.
        """
        file_path = self._matchups_path(season)

        if not file_path.exists():
            return []

        df = pd.read_parquet(file_path, engine="pyarrow")

        if round_num is not None:
            df = df[df["round_num"] == round_num]

        matchups = []
        for _, row in df.iterrows():
            from src.models.game_result import Grade

            matchup = MatchupRecommendation(
                id=row["id"],
                round_num=row["round_num"],
                team_a_name=row["team_a_name"],
                team_a_grade=Grade.from_string(row["team_a_grade"])
                if row["team_a_grade"]
                else None,
                team_b_name=row["team_b_name"],
                team_b_grade=Grade.from_string(row["team_b_grade"])
                if row["team_b_grade"]
                else None,
                matchup_type=MatchupType(row["matchup_type"]),
                status=MatchupStatus(row["status"]),
                confidence=MatchupConfidence(row["confidence"]),
                justification=row["justification"],
                variance_reduction_estimate=row["variance_reduction_estimate"],
                team_a_recent_margin=row.get("team_a_recent_margin"),
                team_b_recent_margin=row.get("team_b_recent_margin"),
            )
            matchups.append(matchup)

        return matchups

    def update_matchup_status(
        self,
        matchup_id: str,
        new_status: MatchupStatus,
        season: str,
    ) -> bool:
        """Update the status of a matchup recommendation.

        Args:
            matchup_id: ID of the matchup to update.
            new_status: New status value.
            season: Season identifier.

        Returns:
            True if updated successfully, False if not found.
        """
        file_path = self._matchups_path(season)

        if not file_path.exists():
            return False

        df = pd.read_parquet(file_path, engine="pyarrow")
        mask = df["id"] == matchup_id

        if not mask.any():
            return False

        status_value = new_status.value if isinstance(new_status, MatchupStatus) else new_status
        df.loc[mask, "status"] = status_value
        df.to_parquet(file_path, engine="pyarrow", index=False)
        return True

    # --- Matchup Outcomes ---

    def save_outcome(self, outcome: MatchupOutcome, season: str) -> Path:
        """Save a matchup outcome for learning.

        Args:
            outcome: The matchup outcome.
            season: Season identifier.

        Returns:
            Path to the saved file.
        """
        file_path = self._outcomes_path(season)

        record = {
            "matchup_id": outcome.matchup_id,
            "round_num": outcome.round_num,
            "team_a_name": outcome.team_a_name,
            "team_b_name": outcome.team_b_name,
            "predicted_margin_low": outcome.predicted_margin_range[0],
            "predicted_margin_high": outcome.predicted_margin_range[1],
            "actual_margin": outcome.actual_margin,
            "variance_reduced": outcome.variance_reduced,
            "prediction_accurate": outcome.prediction_accurate,
            "recorded_at": outcome.recorded_at.isoformat(),
        }

        df = pd.DataFrame([record])

        if file_path.exists():
            existing = pd.read_parquet(file_path, engine="pyarrow")
            # Avoid duplicates by matchup_id
            existing = existing[existing["matchup_id"] != outcome.matchup_id]
            df = pd.concat([existing, df], ignore_index=True)

        df.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def load_outcomes(
        self,
        season: str,
        round_num: int | None = None,
    ) -> list[MatchupOutcome]:
        """Load matchup outcomes from Parquet file.

        Args:
            season: Season identifier.
            round_num: Optional round number to filter.

        Returns:
            List of matchup outcomes.
        """
        file_path = self._outcomes_path(season)

        if not file_path.exists():
            return []

        df = pd.read_parquet(file_path, engine="pyarrow")

        if round_num is not None:
            df = df[df["round_num"] == round_num]

        outcomes = []
        for _, row in df.iterrows():
            outcome = MatchupOutcome(
                matchup_id=row["matchup_id"],
                round_num=row["round_num"],
                team_a_name=row["team_a_name"],
                team_b_name=row["team_b_name"],
                predicted_margin_range=(
                    row["predicted_margin_low"],
                    row["predicted_margin_high"],
                ),
                actual_margin=row["actual_margin"],
                variance_reduced=row["variance_reduced"],
                prediction_accurate=row["prediction_accurate"],
            )
            outcomes.append(outcome)

        return outcomes

    # --- Bye Assignments ---

    def save_bye(self, assignment: ByeAssignment, season: str) -> Path:
        """Save a bye assignment.

        Args:
            assignment: The bye assignment.
            season: Season identifier.

        Returns:
            Path to the saved file.
        """
        file_path = self._byes_path(season)

        record = {
            "team_name": assignment.team_name,
            "round_num": assignment.round_num,
            "reason": assignment.reason,
            "assigned_at": assignment.assigned_at.isoformat(),
        }

        df = pd.DataFrame([record])

        if file_path.exists():
            existing = pd.read_parquet(file_path, engine="pyarrow")
            # Avoid duplicates by (team_name, round_num)
            mask = ~(
                (existing["team_name"] == assignment.team_name)
                & (existing["round_num"] == assignment.round_num)
            )
            existing = existing[mask]
            df = pd.concat([existing, df], ignore_index=True)

        df.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def load_byes(self, season: str) -> list[ByeAssignment]:
        """Load bye assignments from Parquet file.

        Args:
            season: Season identifier.

        Returns:
            List of bye assignments.
        """
        file_path = self._byes_path(season)

        if not file_path.exists():
            return []

        df = pd.read_parquet(file_path, engine="pyarrow")

        assignments = []
        for _, row in df.iterrows():
            assignment = ByeAssignment(
                team_name=row["team_name"],
                round_num=row["round_num"],
                reason=row["reason"],
            )
            assignments.append(assignment)

        return assignments

    def get_season_stats(self, season: str) -> dict:
        """Get statistics for a season's matchup data.

        Args:
            season: Season identifier.

        Returns:
            Dictionary with statistics.
        """
        matchups = self.load_matchups(season)
        outcomes = self.load_outcomes(season)
        byes = self.load_byes(season)

        approved = sum(1 for m in matchups if m.status == MatchupStatus.APPROVED)
        rejected = sum(1 for m in matchups if m.status == MatchupStatus.REJECTED)
        pending = sum(1 for m in matchups if m.status == MatchupStatus.PENDING)

        accurate = sum(1 for o in outcomes if o.prediction_accurate)
        reduced_variance = sum(1 for o in outcomes if o.variance_reduced)

        return {
            "total_matchups": len(matchups),
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "total_outcomes": len(outcomes),
            "accurate_predictions": accurate,
            "variance_reduced_count": reduced_variance,
            "accuracy_rate": (accurate / len(outcomes) * 100) if outcomes else 0.0,
            "variance_reduction_rate": (reduced_variance / len(outcomes) * 100)
            if outcomes
            else 0.0,
            "total_byes": len(byes),
        }
