"""Tests for data pipeline: parser and storage modules."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.parser import GradingBookParser, parse_score_string
from src.data.storage import GameStorage
from src.models.game_result import (
    Gender,
    Grade,
    ResultType,
    SheetInfo,
    TeamSeason,
)


class TestSheetInfo:
    """Tests for SheetInfo parsing."""

    def test_parse_boys_sheet(self) -> None:
        """Test parsing Boys sheet name."""
        info = SheetInfo.from_sheet_name("B161")
        assert info is not None
        assert info.gender == Gender.BOYS
        assert info.age_group == 16
        assert info.division == 1
        assert info.age_label == "U16"

    def test_parse_girls_sheet(self) -> None:
        """Test parsing Girls sheet name."""
        info = SheetInfo.from_sheet_name("G122")
        assert info is not None
        assert info.gender == Gender.GIRLS
        assert info.age_group == 12
        assert info.division == 2

    def test_invalid_sheet_name_returns_none(self) -> None:
        """Test that invalid sheet names return None."""
        assert SheetInfo.from_sheet_name("Summary") is None
        assert SheetInfo.from_sheet_name("Sheet1") is None
        assert SheetInfo.from_sheet_name("") is None
        assert SheetInfo.from_sheet_name("X123") is None

    def test_case_insensitive(self) -> None:
        """Test that sheet parsing is case insensitive."""
        info_upper = SheetInfo.from_sheet_name("B161")
        info_lower = SheetInfo.from_sheet_name("b161")
        assert info_upper is not None
        assert info_lower is not None
        assert info_upper.gender == info_lower.gender


class TestGrade:
    """Tests for Grade enum."""

    def test_from_string_exact_match(self) -> None:
        """Test parsing exact grade strings."""
        assert Grade.from_string("A") == Grade.A
        assert Grade.from_string("B1") == Grade.B1
        assert Grade.from_string("C2") == Grade.C2
        assert Grade.from_string("D") == Grade.D

    def test_from_string_case_insensitive(self) -> None:
        """Test that grade parsing is case insensitive."""
        assert Grade.from_string("a") == Grade.A
        assert Grade.from_string("b1") == Grade.B1
        assert Grade.from_string("B1") == Grade.B1

    def test_from_string_single_letter(self) -> None:
        """Test that single letters map to primary grades."""
        assert Grade.from_string("B") == Grade.B1
        assert Grade.from_string("C") == Grade.C1

    def test_from_string_invalid(self) -> None:
        """Test that invalid grades return None."""
        assert Grade.from_string("X") is None
        assert Grade.from_string("") is None
        assert Grade.from_string("E1") is None

    def test_grade_ranks_ordered(self) -> None:
        """Test that grade ranks are properly ordered."""
        assert Grade.A.rank < Grade.B1.rank
        assert Grade.B1.rank < Grade.B2.rank
        assert Grade.B2.rank < Grade.B3.rank
        assert Grade.B3.rank < Grade.C1.rank
        assert Grade.C1.rank < Grade.C2.rank
        assert Grade.C2.rank < Grade.D.rank


class TestResultType:
    """Tests for ResultType enum."""

    def test_from_string_won(self) -> None:
        """Test parsing winning results."""
        assert ResultType.from_string("Won") == ResultType.WON
        assert ResultType.from_string("win") == ResultType.WON
        assert ResultType.from_string("W") == ResultType.WON

    def test_from_string_lost(self) -> None:
        """Test parsing losing results."""
        assert ResultType.from_string("Lost") == ResultType.LOST
        assert ResultType.from_string("loss") == ResultType.LOST
        assert ResultType.from_string("L") == ResultType.LOST

    def test_from_string_dnp(self) -> None:
        """Test parsing DNP results."""
        assert ResultType.from_string("DNP") == ResultType.DNP
        assert ResultType.from_string("dnp") == ResultType.DNP

    def test_from_string_invalid(self) -> None:
        """Test that invalid results return None."""
        assert ResultType.from_string("") is None
        assert ResultType.from_string("Draw") is None


class TestScoreParsing:
    """Tests for score string parsing."""

    def test_standard_format(self) -> None:
        """Test parsing standard score format."""
        score_for, score_against = parse_score_string("31 - 56")
        assert score_for == 31
        assert score_against == 56

    def test_no_spaces(self) -> None:
        """Test parsing without spaces."""
        score_for, score_against = parse_score_string("45-32")
        assert score_for == 45
        assert score_against == 32

    def test_extra_spaces(self) -> None:
        """Test parsing with extra spaces."""
        score_for, score_against = parse_score_string("  78  -  42  ")
        assert score_for == 78
        assert score_against == 42

    def test_invalid_format_raises(self) -> None:
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError):
            parse_score_string("invalid")
        with pytest.raises(ValueError):
            parse_score_string("")
        with pytest.raises(ValueError):
            parse_score_string("abc - def")


class TestTeamSeason:
    """Tests for TeamSeason model."""

    def test_extract_club_name_single_word(self) -> None:
        """Test extracting single-word club names."""
        assert TeamSeason.extract_club_name("Jets U12 Girls 2") == "Jets"
        assert TeamSeason.extract_club_name("Apollo U16 Boys 1") == "Apollo"

    def test_extract_club_name_multi_word(self) -> None:
        """Test extracting multi-word club names."""
        assert TeamSeason.extract_club_name("Diamond Creek U16 Boys 1") == "Diamond Creek"
        assert TeamSeason.extract_club_name("St Thomas U14 Girls 1") == "St Thomas"

    def test_extract_club_name_invalid(self) -> None:
        """Test that invalid team names return None."""
        assert TeamSeason.extract_club_name("") is None
        assert TeamSeason.extract_club_name("InvalidName") is None


class TestGameStorage:
    """Tests for Parquet storage layer."""

    def test_save_and_load_games(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test saving and loading game data."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"

        # Save
        path = storage.save_games(sample_games_df, season)
        assert path.exists()

        # Load
        loaded = storage.load_games(season)
        assert loaded is not None
        assert len(loaded) == len(sample_games_df)
        assert "team_name" in loaded.columns

    def test_append_deduplicates(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test that appending deduplicates by key columns."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"

        # Save initial data
        storage.save_games(sample_games_df, season)

        # Append same data
        storage.save_games(sample_games_df, season, append=True)

        # Should still have same number of rows
        loaded = storage.load_games(season)
        assert loaded is not None
        assert len(loaded) == len(sample_games_df)

    def test_get_team_history(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test getting team-specific history."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"
        storage.save_games(sample_games_df, season)

        history = storage.get_team_history(season, "Jets U16 Boys 1")
        assert history is not None
        assert len(history) == 3  # Jets has 3 games in sample data
        assert all(history["team_name"] == "Jets U16 Boys 1")

    def test_get_round_results(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test getting round-specific results."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"
        storage.save_games(sample_games_df, season)

        round_1 = storage.get_round_results(season, round_num=1)
        assert round_1 is not None
        assert all(round_1["round_num"] == 1)

    def test_get_rolling_window(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test getting rolling window of data."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"
        storage.save_games(sample_games_df, season)

        window = storage.get_rolling_window(
            season,
            "Jets U16 Boys 1",
            window_size=2,
            current_round=3,
        )
        assert window is not None
        assert all(window["round_num"].isin([2, 3]))

    def test_get_clubs(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test getting list of clubs."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"
        storage.save_games(sample_games_df, season)

        clubs = storage.get_clubs(season)
        assert "Jets" in clubs
        assert "Apollo" in clubs

    def test_get_available_seasons(
        self,
        temp_dir: Path,
        sample_games_df: pd.DataFrame,
    ) -> None:
        """Test getting list of available seasons."""
        storage = GameStorage(temp_dir)
        storage.save_games(sample_games_df, "Autumn 2026")
        storage.save_games(sample_games_df, "Summer 2026")

        seasons = storage.get_available_seasons()
        assert "Autumn 2026" in seasons
        assert "Summer 2026" in seasons

    def test_save_and_load_override(
        self,
        temp_dir: Path,
    ) -> None:
        """Test saving and loading admin overrides."""
        storage = GameStorage(temp_dir)
        season = "Autumn 2026"

        override = {
            "team_name": "Jets U16 Boys 1",
            "sheet_name": "B161",
            "original_recommendation": "promote",
            "admin_decision": "reject",
            "reason": "Injury to key player",
        }

        storage.save_override(season, override)

        overrides = storage.load_overrides(season)
        assert overrides is not None
        assert len(overrides) == 1
        assert overrides.iloc[0]["team_name"] == "Jets U16 Boys 1"

    def test_nonexistent_season_returns_none(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that loading nonexistent season returns None."""
        storage = GameStorage(temp_dir)
        assert storage.load_games("Nonexistent") is None


class TestGradingBookParser:
    """Tests for Excel parser (requires real file)."""

    def test_parse_real_file(self, real_excel_path: Path | None) -> None:
        """Test parsing real Excel file if available."""
        if real_excel_path is None:
            pytest.skip("No real Excel file available")

        parser = GradingBookParser(real_excel_path)

        # Should have some valid sheets
        sheets = parser.get_valid_sheets()
        assert len(sheets) > 0, "Expected at least one valid sheet"

        # First sheet should have gender/age/division info
        first_sheet = sheets[0]
        assert first_sheet.gender in (Gender.BOYS, Gender.GIRLS)
        assert 6 <= first_sheet.age_group <= 19

    def test_parse_sheet_returns_teams(self, real_excel_path: Path | None) -> None:
        """Test that parsing a sheet returns TeamSeason objects."""
        if real_excel_path is None:
            pytest.skip("No real Excel file available")

        parser = GradingBookParser(real_excel_path)
        sheets = parser.get_valid_sheets()

        if sheets:
            teams = parser.parse_sheet(sheets[0].sheet_name)
            assert isinstance(teams, list)
            if teams:
                assert isinstance(teams[0], TeamSeason)

    def test_to_dataframe(self, real_excel_path: Path | None) -> None:
        """Test converting parsed data to DataFrame."""
        if real_excel_path is None:
            pytest.skip("No real Excel file available")

        parser = GradingBookParser(real_excel_path)
        df = parser.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            expected_cols = [
                "team_name",
                "opponent_name",
                "score_for",
                "score_against",
                "margin",
                "result",
                "round_num",
            ]
            for col in expected_cols:
                assert col in df.columns, f"Missing column: {col}"

    def test_file_not_found_raises(self, temp_dir: Path) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            GradingBookParser(temp_dir / "nonexistent.xlsx")
