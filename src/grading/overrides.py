"""Admin override management and audit trail.

Tracks when administrators accept, reject, or modify system
recommendations. Provides an audit log for accountability
and transparency.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.models.recommendation import Override, RecommendationType


class OverrideManager:
    """Manages admin overrides with Parquet persistence.

    Provides methods to record, query, and audit admin decisions
    on grade recommendations.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize the override manager.

        Args:
            data_dir: Directory for storing override data.
        """
        self.data_dir = data_dir
        self.overrides_file = data_dir / "overrides.parquet"
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def record_override(self, override: Override) -> None:
        """Record an admin override decision.

        Args:
            override: Override object with decision details.
        """
        # Convert to dict for DataFrame
        record = {
            "team_name": override.team_name,
            "sheet_name": override.sheet_name,
            "original_recommendation": override.original_recommendation,
            "original_grade": override.original_grade,
            "admin_decision": override.admin_decision,
            "final_grade": override.final_grade,
            "reason": override.reason,
            "admin_id": override.admin_id,
            "timestamp": override.timestamp,
            "season": override.season,
            "round_num": override.round_num,
        }

        new_df = pd.DataFrame([record])

        if self.overrides_file.exists():
            existing_df = pd.read_parquet(self.overrides_file)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        combined_df.to_parquet(self.overrides_file, index=False)

    def get_team_overrides(self, team_name: str) -> list[Override]:
        """Get all overrides for a specific team.

        Args:
            team_name: Team name to query.

        Returns:
            List of Override objects for this team.
        """
        if not self.overrides_file.exists():
            return []

        df = pd.read_parquet(self.overrides_file)
        team_df = df[df["team_name"] == team_name]

        return [self._row_to_override(row) for _, row in team_df.iterrows()]

    def get_overrides_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Override]:
        """Get overrides within a date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            List of Override objects in date range.
        """
        if not self.overrides_file.exists():
            return []

        df = pd.read_parquet(self.overrides_file)
        mask = (df["timestamp"] >= start_date) & (df["timestamp"] <= end_date)
        filtered_df = df[mask]

        return [self._row_to_override(row) for _, row in filtered_df.iterrows()]

    def get_overrides_by_season(self, season: str) -> list[Override]:
        """Get all overrides for a specific season.

        Args:
            season: Season identifier (e.g., "Autumn 2026").

        Returns:
            List of Override objects for this season.
        """
        if not self.overrides_file.exists():
            return []

        df = pd.read_parquet(self.overrides_file)
        season_df = df[df["season"] == season]

        return [self._row_to_override(row) for _, row in season_df.iterrows()]

    def get_all_overrides(self) -> list[Override]:
        """Get all recorded overrides.

        Returns:
            Complete list of Override objects.
        """
        if not self.overrides_file.exists():
            return []

        df = pd.read_parquet(self.overrides_file)
        return [self._row_to_override(row) for _, row in df.iterrows()]

    def get_audit_summary(self, season: str | None = None) -> dict:
        """Generate audit summary statistics.

        Args:
            season: Optional season filter.

        Returns:
            Dictionary with audit statistics.
        """
        if not self.overrides_file.exists():
            return {
                "total_overrides": 0,
                "accepted": 0,
                "rejected": 0,
                "modified": 0,
                "by_admin": {},
            }

        df = pd.read_parquet(self.overrides_file)

        if season:
            df = df[df["season"] == season]

        # Count decisions
        decision_counts = df["admin_decision"].value_counts().to_dict()

        # Count by admin
        admin_counts = df["admin_id"].value_counts().to_dict() if "admin_id" in df else {}

        return {
            "total_overrides": len(df),
            "accepted": decision_counts.get("accept", 0),
            "rejected": decision_counts.get("reject", 0),
            "modified": sum(v for k, v in decision_counts.items() if k not in ("accept", "reject")),
            "by_admin": admin_counts,
        }

    def export_to_dataframe(self, season: str | None = None) -> pd.DataFrame:
        """Export overrides to DataFrame for reporting.

        Args:
            season: Optional season filter.

        Returns:
            DataFrame with override records.
        """
        if not self.overrides_file.exists():
            return pd.DataFrame()

        df = pd.read_parquet(self.overrides_file)

        if season:
            df = df[df["season"] == season]

        return df

    def _row_to_override(self, row: pd.Series) -> Override:
        """Convert DataFrame row to Override object.

        Args:
            row: Pandas Series with override data.

        Returns:
            Override object.
        """
        return Override(
            team_name=row["team_name"],
            sheet_name=row["sheet_name"],
            original_recommendation=RecommendationType(row["original_recommendation"]),
            original_grade=row.get("original_grade"),
            admin_decision=row["admin_decision"],
            final_grade=row.get("final_grade"),
            reason=row["reason"],
            admin_id=row.get("admin_id"),
            timestamp=row["timestamp"],
            season=row.get("season"),
            round_num=row.get("round_num"),
        )
