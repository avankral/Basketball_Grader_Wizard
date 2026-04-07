"""Parquet storage layer for game data persistence.

This module handles saving and loading game data to/from Parquet files,
providing efficient storage and fast queries for historical analysis.

Storage structure:
    data/
    └── {season}/
        ├── games.parquet      # All game results
        └── overrides.parquet  # Admin overrides audit log
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


class GameStorage:
    """Parquet-based storage for basketball game data.

    Provides methods to save, load, append, and query game results
    stored in Parquet format for efficient persistence.
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

    def _games_path(self, season: str) -> Path:
        """Get path to games parquet file.

        Args:
            season: Season identifier.

        Returns:
            Path to games.parquet file.
        """
        return self._get_season_dir(season) / "games.parquet"

    def _overrides_path(self, season: str) -> Path:
        """Get path to overrides parquet file.

        Args:
            season: Season identifier.

        Returns:
            Path to overrides.parquet file.
        """
        return self._get_season_dir(season) / "overrides.parquet"

    def save_games(
        self,
        df: pd.DataFrame,
        season: str,
        append: bool = False,
    ) -> Path:
        """Save game results to Parquet file.

        Args:
            df: DataFrame with game results (long format).
            season: Season identifier.
            append: If True, append to existing data; otherwise overwrite.

        Returns:
            Path to the saved file.
        """
        file_path = self._games_path(season)

        if append and file_path.exists():
            existing = pd.read_parquet(file_path, engine="pyarrow")

            # Combine and deduplicate
            combined = pd.concat([existing, df], ignore_index=True)

            # Dedupe by (team_name, opponent_name, round_num, sheet_name)
            dedup_cols = ["team_name", "opponent_name", "round_num", "sheet_name"]
            available_cols = [c for c in dedup_cols if c in combined.columns]

            if available_cols:
                combined = combined.drop_duplicates(subset=available_cols, keep="last")

            df = combined

        # Add metadata columns
        if "imported_at" not in df.columns:
            df = df.copy()
            df["imported_at"] = datetime.now().isoformat()

        df.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def load_games(self, season: str) -> pd.DataFrame | None:
        """Load game results from Parquet file.

        Args:
            season: Season identifier.

        Returns:
            DataFrame with game results, or None if file doesn't exist.
        """
        file_path = self._games_path(season)
        if not file_path.exists():
            return None
        return pd.read_parquet(file_path, engine="pyarrow")

    def get_team_history(
        self,
        season: str,
        team_name: str,
        rounds: list[int] | None = None,
    ) -> pd.DataFrame | None:
        """Get game history for a specific team.

        Args:
            season: Season identifier.
            team_name: Full team name to filter.
            rounds: Optional list of round numbers to include.

        Returns:
            DataFrame filtered to the team's games, or None if no data.
        """
        df = self.load_games(season)
        if df is None:
            return None

        mask = df["team_name"] == team_name
        if rounds:
            mask &= df["round_num"].isin(rounds)

        return df[mask].copy()

    def get_round_results(
        self,
        season: str,
        round_num: int,
        sheet_name: str | None = None,
    ) -> pd.DataFrame | None:
        """Get all results for a specific round.

        Args:
            season: Season identifier.
            round_num: Round number to retrieve.
            sheet_name: Optional sheet name to filter.

        Returns:
            DataFrame with round results, or None if no data.
        """
        df = self.load_games(season)
        if df is None:
            return None

        mask = df["round_num"] == round_num
        if sheet_name:
            mask &= df["sheet_name"] == sheet_name

        return df[mask].copy()

    def get_rolling_window(
        self,
        season: str,
        team_name: str,
        window_size: int = 5,
        current_round: int | None = None,
    ) -> pd.DataFrame | None:
        """Get last N rounds of data for a team.

        Args:
            season: Season identifier.
            team_name: Full team name.
            window_size: Number of rounds to include.
            current_round: Current round (defaults to max round in data).

        Returns:
            DataFrame with rolling window data, or None if no data.
        """
        df = self.load_games(season)
        if df is None:
            return None

        team_df = df[df["team_name"] == team_name].copy()
        if team_df.empty:
            return None

        if current_round is None:
            current_round = team_df["round_num"].max()

        min_round = max(1, current_round - window_size + 1)
        mask = (team_df["round_num"] >= min_round) & (team_df["round_num"] <= current_round)

        return team_df[mask].copy()

    def get_clubs(self, season: str) -> list[str]:
        """Get list of unique club names in the data.

        Args:
            season: Season identifier.

        Returns:
            List of unique club names.
        """
        df = self.load_games(season)
        if df is None or "club_name" not in df.columns:
            return []

        clubs = df["club_name"].dropna().unique().tolist()
        return sorted(clubs)

    def get_club_teams(self, season: str, club_name: str) -> list[str]:
        """Get all team names for a specific club.

        Args:
            season: Season identifier.
            club_name: Club name to filter.

        Returns:
            List of team names belonging to the club.
        """
        df = self.load_games(season)
        if df is None or "club_name" not in df.columns:
            return []

        teams = df[df["club_name"] == club_name]["team_name"].unique().tolist()
        return sorted(teams)

    def get_available_seasons(self) -> list[str]:
        """Get list of seasons with stored data.

        Returns:
            List of season identifiers.
        """
        seasons = []
        for path in self.data_dir.iterdir():
            if path.is_dir() and (path / "games.parquet").exists():
                seasons.append(path.name.replace("_", " "))
        return sorted(seasons)

    def get_max_round(self, season: str) -> int:
        """Get the maximum round number in the data.

        Args:
            season: Season identifier.

        Returns:
            Maximum round number, or 0 if no data.
        """
        df = self.load_games(season)
        if df is None or "round_num" not in df.columns:
            return 0
        return int(df["round_num"].max())

    def get_sheets(self, season: str) -> list[str]:
        """Get list of unique sheet names in the data.

        Args:
            season: Season identifier.

        Returns:
            List of sheet names.
        """
        df = self.load_games(season)
        if df is None or "sheet_name" not in df.columns:
            return []

        return sorted(df["sheet_name"].unique().tolist())

    # Override management

    def save_override(
        self,
        season: str,
        override_data: dict,
    ) -> Path:
        """Save an admin override to the audit log.

        Args:
            season: Season identifier.
            override_data: Dictionary with override information.

        Returns:
            Path to the overrides file.
        """
        file_path = self._overrides_path(season)

        # Add timestamp if not present
        if "timestamp" not in override_data:
            override_data["timestamp"] = datetime.now().isoformat()

        new_row = pd.DataFrame([override_data])

        if file_path.exists():
            existing = pd.read_parquet(file_path, engine="pyarrow")
            combined = pd.concat([existing, new_row], ignore_index=True)
        else:
            combined = new_row

        combined.to_parquet(file_path, engine="pyarrow", index=False)
        return file_path

    def load_overrides(self, season: str) -> pd.DataFrame | None:
        """Load all overrides for a season.

        Args:
            season: Season identifier.

        Returns:
            DataFrame with overrides, or None if no overrides exist.
        """
        file_path = self._overrides_path(season)
        if not file_path.exists():
            return None
        return pd.read_parquet(file_path, engine="pyarrow")

    def get_team_overrides(self, season: str, team_name: str) -> pd.DataFrame | None:
        """Get overrides for a specific team.

        Args:
            season: Season identifier.
            team_name: Full team name.

        Returns:
            DataFrame filtered to team's overrides, or None if no data.
        """
        df = self.load_overrides(season)
        if df is None:
            return None

        return df[df["team_name"] == team_name].copy()

    def delete_season(self, season: str) -> bool:
        """Delete all data for a season.

        Args:
            season: Season identifier.

        Returns:
            True if deletion was successful, False otherwise.
        """
        season_dir = self._get_season_dir(season)
        if not season_dir.exists():
            return False

        import shutil

        shutil.rmtree(season_dir)
        return True
