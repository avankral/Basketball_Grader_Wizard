"""Historical season comparison and analytics.

Provides cross-season analysis for:
- Team performance trends over multiple seasons
- Grade progression history (promotion/demotion tracking)
- Club-level aggregate performance
- Pattern identification for grading accuracy
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.models.game_result import Grade

if TYPE_CHECKING:
    from src.models.game_result import TeamSeason


def _enum_value(value: object | None) -> str | None:
    """Return enum `.value` when present, otherwise string form."""
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _club_name(value: str | None) -> str:
    """Normalize club names for storage keys."""
    return value or "Unknown Club"


def _row_value(row: pd.Series, key: str) -> object | None:
    """Safely extract a scalar value from a pandas row."""
    value = row.get(key)
    if pd.isna(value):
        return None
    return value


@dataclass
class SeasonSnapshot:
    """Performance snapshot for a single season."""

    season: str
    team_name: str
    club_name: str
    grade: Grade | None
    wins: int
    losses: int
    win_rate: float
    avg_margin: float
    blowout_wins: int
    blowout_losses: int
    games_played: int
    final_recommendation: str | None = None  # PROMOTE, DEMOTE, NO_CHANGE
    actual_grade_change: str | None = None  # What actually happened


@dataclass
class TeamHistory:
    """Historical performance data for a team across seasons."""

    team_name: str
    club_name: str
    seasons: list[SeasonSnapshot] = field(default_factory=list)

    @property
    def grade_progression(self) -> list[tuple[str, str]]:
        """Get list of (season, grade) tuples showing progression."""
        return [
            (
                s.season,
                _enum_value(s.grade) or "None",
            )
            for s in sorted(self.seasons, key=lambda x: x.season)
        ]

    @property
    def total_promotions(self) -> int:
        """Count times team was promoted."""
        return sum(1 for s in self.seasons if s.actual_grade_change == "PROMOTED")

    @property
    def total_demotions(self) -> int:
        """Count times team was demoted."""
        return sum(1 for s in self.seasons if s.actual_grade_change == "DEMOTED")

    @property
    def avg_win_rate(self) -> float:
        """Average win rate across all seasons."""
        if not self.seasons:
            return 0.0
        return sum(s.win_rate for s in self.seasons) / len(self.seasons)

    @property
    def trend(self) -> str:
        """Calculate overall trend: IMPROVING, DECLINING, or STABLE."""
        if len(self.seasons) < 2:
            return "STABLE"

        sorted_seasons = sorted(self.seasons, key=lambda x: x.season)
        first_half = sorted_seasons[: len(sorted_seasons) // 2]
        second_half = sorted_seasons[len(sorted_seasons) // 2 :]

        first_avg = sum(s.win_rate for s in first_half) / len(first_half)
        second_avg = sum(s.win_rate for s in second_half) / len(second_half)

        if second_avg > first_avg + 10:
            return "IMPROVING"
        if second_avg < first_avg - 10:
            return "DECLINING"
        return "STABLE"


@dataclass
class ClubHistory:
    """Aggregate historical data for a club across all teams."""

    club_name: str
    team_histories: dict[str, TeamHistory] = field(default_factory=dict)

    @property
    def total_teams(self) -> int:
        """Count of distinct teams."""
        return len(self.team_histories)

    @property
    def total_seasons_played(self) -> int:
        """Total team-seasons across all teams."""
        return sum(len(th.seasons) for th in self.team_histories.values())

    @property
    def overall_win_rate(self) -> float:
        """Aggregate win rate across all team-seasons."""
        total_wins = 0
        total_losses = 0
        for th in self.team_histories.values():
            for s in th.seasons:
                total_wins += s.wins
                total_losses += s.losses
        total = total_wins + total_losses
        return (total_wins / total * 100) if total > 0 else 0.0

    @property
    def promotion_rate(self) -> float:
        """Percentage of seasons resulting in promotion."""
        total = self.total_seasons_played
        if total == 0:
            return 0.0
        promotions = sum(
            1
            for th in self.team_histories.values()
            for s in th.seasons
            if s.actual_grade_change == "PROMOTED"
        )
        return promotions / total * 100

    @property
    def demotion_rate(self) -> float:
        """Percentage of seasons resulting in demotion."""
        total = self.total_seasons_played
        if total == 0:
            return 0.0
        demotions = sum(
            1
            for th in self.team_histories.values()
            for s in th.seasons
            if s.actual_grade_change == "DEMOTED"
        )
        return demotions / total * 100

    @property
    def grade_distribution(self) -> dict[str, int]:
        """Count of teams at each grade level (current season)."""
        dist: dict[str, int] = defaultdict(int)
        for th in self.team_histories.values():
            if th.seasons:
                latest = max(th.seasons, key=lambda x: x.season)
                grade = _enum_value(latest.grade) or "None"
                dist[grade] += 1
        return dict(dist)


class HistoricalAnalyzer:
    """Analyzer for historical season data."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize with optional data directory for persistence.

        Args:
            data_dir: Directory for storing/loading historical data.
        """
        self.data_dir = data_dir
        self.team_histories: dict[str, TeamHistory] = {}
        self.club_histories: dict[str, ClubHistory] = {}

    def add_season_data(
        self,
        season: str,
        teams: list[TeamSeason],
        recommendations: dict[str, str] | None = None,
        grade_changes: dict[str, str] | None = None,
    ) -> None:
        """Add a season's worth of data to historical records.

        Args:
            season: Season identifier (e.g., "2025-Winter", "2026-Summer").
            teams: List of TeamSeason objects for this season.
            recommendations: Dict mapping team_name to recommendation type.
            grade_changes: Dict mapping team_name to actual grade change.
        """
        recommendations = recommendations or {}
        grade_changes = grade_changes or {}

        for team in teams:
            # Calculate metrics
            wins = sum(1 for g in team.games if _enum_value(g.result) == "Won")
            losses = sum(1 for g in team.games if _enum_value(g.result) == "Lost")
            games = wins + losses
            win_rate = (wins / games * 100) if games > 0 else 0.0
            total_margin = sum(g.margin for g in team.games if _enum_value(g.result) != "DNP")
            avg_margin = (total_margin / games) if games > 0 else 0.0
            blowout_wins = sum(1 for g in team.games if g.margin >= 20)
            blowout_losses = sum(1 for g in team.games if g.margin <= -20)

            snapshot = SeasonSnapshot(
                season=season,
                team_name=team.team_name,
                club_name=_club_name(team.club_name),
                grade=team.assigned_grade,
                wins=wins,
                losses=losses,
                win_rate=round(win_rate, 1),
                avg_margin=round(avg_margin, 1),
                blowout_wins=blowout_wins,
                blowout_losses=blowout_losses,
                games_played=games,
                final_recommendation=recommendations.get(team.team_name),
                actual_grade_change=grade_changes.get(team.team_name),
            )

            # Add to team history
            if team.team_name not in self.team_histories:
                self.team_histories[team.team_name] = TeamHistory(
                    team_name=team.team_name,
                    club_name=_club_name(team.club_name),
                )
            self.team_histories[team.team_name].seasons.append(snapshot)

            # Add to club history
            club_name = _club_name(team.club_name)
            if club_name not in self.club_histories:
                self.club_histories[club_name] = ClubHistory(
                    club_name=club_name,
                )
            if team.team_name not in self.club_histories[club_name].team_histories:
                self.club_histories[club_name].team_histories[team.team_name] = self.team_histories[
                    team.team_name
                ]

    def get_team_history(self, team_name: str) -> TeamHistory | None:
        """Get historical data for a specific team."""
        return self.team_histories.get(team_name)

    def get_club_history(self, club_name: str) -> ClubHistory | None:
        """Get aggregate historical data for a club."""
        return self.club_histories.get(club_name)

    def get_season_comparison_df(self, team_name: str) -> pd.DataFrame:
        """Generate DataFrame comparing team across seasons.

        Args:
            team_name: Name of team to analyze.

        Returns:
            DataFrame with season-by-season comparison.
        """
        history = self.team_histories.get(team_name)
        if history is None or not history.seasons:
            return pd.DataFrame()

        data = []
        for s in sorted(history.seasons, key=lambda x: x.season):
            data.append(
                {
                    "Season": s.season,
                    "Grade": _enum_value(s.grade) or "None",
                    "W": s.wins,
                    "L": s.losses,
                    "Win%": s.win_rate,
                    "Avg Margin": s.avg_margin,
                    "Blowout W": s.blowout_wins,
                    "Blowout L": s.blowout_losses,
                    "Recommendation": s.final_recommendation or "N/A",
                    "Grade Change": s.actual_grade_change or "N/A",
                }
            )

        return pd.DataFrame(data)

    def get_club_summary_df(self) -> pd.DataFrame:
        """Generate DataFrame summarizing all clubs.

        Returns:
            DataFrame with club-level aggregate statistics.
        """
        data = []
        for club_name, club in self.club_histories.items():
            data.append(
                {
                    "Club": club_name,
                    "Teams": club.total_teams,
                    "Team-Seasons": club.total_seasons_played,
                    "Overall Win%": round(club.overall_win_rate, 1),
                    "Promotion Rate%": round(club.promotion_rate, 1),
                    "Demotion Rate%": round(club.demotion_rate, 1),
                }
            )

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("Overall Win%", ascending=False)
        return df

    def identify_grading_patterns(self) -> list[dict]:
        """Identify patterns in grading accuracy.

        Returns:
            List of pattern observations.
        """
        patterns = []

        # Find teams that consistently perform above/below grade
        for team_name, history in self.team_histories.items():
            if len(history.seasons) < 2:
                continue

            above_grade_seasons = sum(
                1 for s in history.seasons if s.win_rate > 65 and s.blowout_wins >= 2
            )
            below_grade_seasons = sum(
                1 for s in history.seasons if s.win_rate < 35 and s.blowout_losses >= 2
            )

            if above_grade_seasons >= len(history.seasons) * 0.7:
                patterns.append(
                    {
                        "type": "CONSISTENT_OVERPERFORMER",
                        "team": team_name,
                        "club": history.club_name,
                        "seasons": len(history.seasons),
                        "detail": f"Performed above grade in {above_grade_seasons}/{len(history.seasons)} seasons",
                    }
                )
            elif below_grade_seasons >= len(history.seasons) * 0.7:
                patterns.append(
                    {
                        "type": "CONSISTENT_UNDERPERFORMER",
                        "team": team_name,
                        "club": history.club_name,
                        "seasons": len(history.seasons),
                        "detail": f"Struggled at grade in {below_grade_seasons}/{len(history.seasons)} seasons",
                    }
                )

        # Find clubs with unusual promotion/demotion rates
        for club_name, club in self.club_histories.items():
            if club.total_seasons_played < 5:
                continue

            if club.promotion_rate > 30:
                patterns.append(
                    {
                        "type": "HIGH_PROMOTION_CLUB",
                        "club": club_name,
                        "detail": f"Promotion rate of {club.promotion_rate:.1f}% suggests teams may be consistently undergraded",
                    }
                )
            elif club.demotion_rate > 30:
                patterns.append(
                    {
                        "type": "HIGH_DEMOTION_CLUB",
                        "club": club_name,
                        "detail": f"Demotion rate of {club.demotion_rate:.1f}% suggests teams may be consistently overgraded",
                    }
                )

        return patterns

    def save_to_parquet(self, filepath: Path) -> None:
        """Save historical data to Parquet file.

        Args:
            filepath: Path to save Parquet file.
        """
        records = []
        for history in self.team_histories.values():
            for s in history.seasons:
                records.append(
                    {
                        "team_name": s.team_name,
                        "club_name": s.club_name,
                        "season": s.season,
                        "grade": _enum_value(s.grade),
                        "wins": s.wins,
                        "losses": s.losses,
                        "win_rate": s.win_rate,
                        "avg_margin": s.avg_margin,
                        "blowout_wins": s.blowout_wins,
                        "blowout_losses": s.blowout_losses,
                        "games_played": s.games_played,
                        "final_recommendation": s.final_recommendation,
                        "actual_grade_change": s.actual_grade_change,
                    }
                )

        df = pd.DataFrame(records)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(filepath, engine="pyarrow", index=False)

    def load_from_parquet(self, filepath: Path) -> None:
        """Load historical data from Parquet file.

        Args:
            filepath: Path to Parquet file.
        """
        if not filepath.exists():
            return

        df = pd.read_parquet(filepath, engine="pyarrow")

        for _, row in df.iterrows():
            grade_raw = _row_value(row, "grade")
            grade_text = str(grade_raw) if grade_raw is not None else None
            grade = Grade.from_string(grade_text) if grade_text else None
            club_raw = _row_value(row, "club_name")
            team_raw = _row_value(row, "team_name")
            season_raw = _row_value(row, "season")
            club_name = _club_name(str(club_raw) if club_raw is not None else None)
            team_name = str(team_raw) if team_raw is not None else "Unknown Team"
            snapshot = SeasonSnapshot(
                season=str(season_raw) if season_raw is not None else "Unknown Season",
                team_name=team_name,
                club_name=club_name,
                grade=grade,
                wins=int(_row_value(row, "wins") or 0),
                losses=int(_row_value(row, "losses") or 0),
                win_rate=float(_row_value(row, "win_rate") or 0.0),
                avg_margin=float(_row_value(row, "avg_margin") or 0.0),
                blowout_wins=int(_row_value(row, "blowout_wins") or 0),
                blowout_losses=int(_row_value(row, "blowout_losses") or 0),
                games_played=int(_row_value(row, "games_played") or 0),
                final_recommendation=_row_value(row, "final_recommendation"),
                actual_grade_change=_row_value(row, "actual_grade_change"),
            )

            # Add to team history
            if team_name not in self.team_histories:
                self.team_histories[team_name] = TeamHistory(
                    team_name=team_name,
                    club_name=club_name,
                )
            self.team_histories[team_name].seasons.append(snapshot)

            # Add to club history
            if club_name not in self.club_histories:
                self.club_histories[club_name] = ClubHistory(
                    club_name=club_name,
                )
            if team_name not in self.club_histories[club_name].team_histories:
                self.club_histories[club_name].team_histories[team_name] = self.team_histories[
                    team_name
                ]


def compare_seasons(
    current_season: str,
    current_teams: list[TeamSeason],
    historical_analyzer: HistoricalAnalyzer,
) -> pd.DataFrame:
    """Compare current season performance against historical averages.

    Args:
        current_season: Current season identifier.
        current_teams: List of current TeamSeason objects.
        historical_analyzer: Analyzer with historical data.

    Returns:
        DataFrame comparing current vs historical performance.
    """
    comparisons = []

    for team in current_teams:
        history = historical_analyzer.get_team_history(team.team_name)

        # Calculate current metrics
        wins = sum(1 for g in team.games if _enum_value(g.result) == "Won")
        losses = sum(1 for g in team.games if _enum_value(g.result) == "Lost")
        games = wins + losses
        current_win_rate = (wins / games * 100) if games > 0 else 0.0

        if history and history.seasons:
            historical_avg = history.avg_win_rate
            trend = history.trend
            seasons_played = len(history.seasons)
        else:
            historical_avg = None
            trend = "NEW"
            seasons_played = 0

        comparisons.append(
            {
                "Team": team.team_name,
                "Club": _club_name(team.club_name),
                "Grade": _enum_value(team.assigned_grade) or "None",
                "Current Win%": round(current_win_rate, 1),
                "Historical Avg Win%": round(historical_avg, 1) if historical_avg else "N/A",
                "Trend": trend,
                "Seasons on Record": seasons_played,
            }
        )

    df = pd.DataFrame(comparisons)
    if not df.empty:
        df = df.sort_values("Current Win%", ascending=False)
    return df
