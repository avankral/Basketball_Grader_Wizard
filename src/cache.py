"""Performance caching module for computed metrics and analysis.

This module provides centralized caching of expensive calculations
to avoid recomputation on every UI render. Data is computed once
when loaded and stored in session state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.grading.strength_of_schedule import StrengthOfSchedule, calculate_sos

if TYPE_CHECKING:
    from src.models.game_result import TeamSeason


@dataclass
class CachedTeamData:
    """Pre-computed data for a single team."""

    metrics: TeamMetrics
    sos: StrengthOfSchedule


def compute_all_team_data(teams: list[TeamSeason]) -> dict[str, CachedTeamData]:
    """Compute metrics and SoS for all teams at once.

    This is called once when data is loaded and cached in session state.

    Args:
        teams: List of all teams.

    Returns:
        Dict mapping team_name to CachedTeamData.
    """
    result = {}
    for team in teams:
        metrics = calculate_team_metrics(team)
        sos = calculate_sos(team)
        result[team.team_name] = CachedTeamData(metrics=metrics, sos=sos)
    return result


def get_cached_data() -> dict[str, CachedTeamData]:
    """Get cached team data from session state.

    Returns:
        Dict mapping team_name to CachedTeamData, or empty dict if not cached.
    """
    return st.session_state.get("cached_team_data", {})


def get_team_metrics(team_name: str) -> TeamMetrics | None:
    """Get cached metrics for a team.

    Args:
        team_name: Name of the team.

    Returns:
        TeamMetrics if cached, None otherwise.
    """
    cached = get_cached_data()
    if team_name in cached:
        return cached[team_name].metrics
    return None


def get_team_sos(team_name: str) -> StrengthOfSchedule | None:
    """Get cached SoS for a team.

    Args:
        team_name: Name of the team.

    Returns:
        StrengthOfSchedule if cached, None otherwise.
    """
    cached = get_cached_data()
    if team_name in cached:
        return cached[team_name].sos
    return None


def get_all_metrics(teams: list[TeamSeason]) -> list[TeamMetrics]:
    """Get cached metrics for a list of teams.

    Falls back to computing if not cached.

    Args:
        teams: List of teams.

    Returns:
        List of TeamMetrics in same order as teams.
    """
    cached = get_cached_data()
    result = []
    for team in teams:
        if team.team_name in cached:
            result.append(cached[team.team_name].metrics)
        else:
            # Fallback to computing (shouldn't happen in normal use)
            result.append(calculate_team_metrics(team))
    return result


def get_all_sos(teams: list[TeamSeason]) -> list[StrengthOfSchedule]:
    """Get cached SoS for a list of teams.

    Falls back to computing if not cached.

    Args:
        teams: List of teams.

    Returns:
        List of StrengthOfSchedule in same order as teams.
    """
    cached = get_cached_data()
    result = []
    for team in teams:
        if team.team_name in cached:
            result.append(cached[team.team_name].sos)
        else:
            # Fallback to computing (shouldn't happen in normal use)
            result.append(calculate_sos(team))
    return result


def invalidate_cache() -> None:
    """Clear all cached data.

    Call when data is reloaded or cleared.
    """
    if "cached_team_data" in st.session_state:
        del st.session_state["cached_team_data"]


def cache_team_data(teams: list[TeamSeason]) -> None:
    """Compute and cache data for all teams.

    Args:
        teams: List of teams to cache.
    """
    st.session_state["cached_team_data"] = compute_all_team_data(teams)
