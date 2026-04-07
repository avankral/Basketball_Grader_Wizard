"""Pytest fixtures and configuration for Basketball Grader Wizard tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data.

    Yields:
        Path to the temporary directory.
    """
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_games_df() -> pd.DataFrame:
    """Create a sample games DataFrame for testing.

    Returns:
        DataFrame with sample game data.
    """
    return pd.DataFrame(
        [
            {
                "team_name": "Jets U16 Boys 1",
                "club_name": "Jets",
                "gender": "Boys",
                "age_group": 16,
                "division": 1,
                "assigned_grade": "B1",
                "sheet_name": "B161",
                "round_num": 1,
                "opponent_name": "Apollo U16 Boys 1",
                "opponent_grade": "A",
                "score_for": 45,
                "score_against": 52,
                "margin": -7,
                "result": "Lost",
                "variance_class": "competitive",
                "opponent_sheet": "B161",
                "is_blowout": False,
                "is_close_game": False,
            },
            {
                "team_name": "Jets U16 Boys 1",
                "club_name": "Jets",
                "gender": "Boys",
                "age_group": 16,
                "division": 1,
                "assigned_grade": "B1",
                "sheet_name": "B161",
                "round_num": 2,
                "opponent_name": "Diamond Creek U16 Boys 1",
                "opponent_grade": "B1",
                "score_for": 68,
                "score_against": 42,
                "margin": 26,
                "result": "Won",
                "variance_class": "dominant_win",
                "opponent_sheet": "B161",
                "is_blowout": True,
                "is_close_game": False,
            },
            {
                "team_name": "Jets U16 Boys 1",
                "club_name": "Jets",
                "gender": "Boys",
                "age_group": 16,
                "division": 1,
                "assigned_grade": "B1",
                "sheet_name": "B161",
                "round_num": 3,
                "opponent_name": "Greenhills U16 Boys 1",
                "opponent_grade": "B2",
                "score_for": 55,
                "score_against": 51,
                "margin": 4,
                "result": "Won",
                "variance_class": "competitive",
                "opponent_sheet": "B161",
                "is_blowout": False,
                "is_close_game": True,
            },
            {
                "team_name": "Apollo U16 Boys 1",
                "club_name": "Apollo",
                "gender": "Boys",
                "age_group": 16,
                "division": 1,
                "assigned_grade": "A",
                "sheet_name": "B161",
                "round_num": 1,
                "opponent_name": "Jets U16 Boys 1",
                "opponent_grade": "B1",
                "score_for": 52,
                "score_against": 45,
                "margin": 7,
                "result": "Won",
                "variance_class": "competitive",
                "opponent_sheet": "B161",
                "is_blowout": False,
                "is_close_game": False,
            },
        ]
    )


@pytest.fixture
def real_excel_path() -> Path | None:
    """Get path to real Excel file if available.

    Returns:
        Path to the real Excel file, or None if not found.
    """
    data_dir = Path("data")
    for xlsx in data_dir.glob("*.xlsx"):
        if not xlsx.name.startswith("~$"):  # Skip temp files
            return xlsx
    return None
