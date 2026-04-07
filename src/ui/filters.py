"""Sidebar filter components for the dashboard.

Provides reactive filters for:
- Season selection
- Round selection
- Gender filter
- Age group filter
- Division filter
- Grade filter
- Club focus
"""

from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st

from src.models.game_result import Grade, TeamSeason


@dataclass
class FilterState:
    """Current state of all sidebar filters.

    Stored in st.session_state for persistence across reruns.
    """

    season: str = "Autumn 2026"
    max_round: int = 5
    selected_round: int = 5  # Current round to display
    genders: list[str] = field(default_factory=lambda: ["Boys", "Girls"])
    age_groups: list[int] = field(default_factory=list)
    divisions: list[int] = field(default_factory=list)
    grades: list[str] = field(default_factory=list)
    club_focus: str | None = None
    show_recommendations_only: bool = False

    def matches_team(self, team: TeamSeason) -> bool:
        """Check if a team matches the current filter state.

        Args:
            team: Team to check.

        Returns:
            True if team matches all active filters.
        """
        # Gender filter
        gender_val = team.gender.value if hasattr(team.gender, "value") else str(team.gender)
        if gender_val not in self.genders:
            return False

        # Age group filter
        if self.age_groups and team.age_group not in self.age_groups:
            return False

        # Division filter
        if self.divisions and team.division not in self.divisions:
            return False

        # Grade filter
        if self.grades:
            team_grade = (
                team.assigned_grade.value
                if hasattr(team.assigned_grade, "value")
                else str(team.assigned_grade)
            ) if team.assigned_grade else None
            if team_grade not in self.grades:
                return False

        # Club focus filter
        if self.club_focus and (  # noqa: SIM103
            not team.club_name or self.club_focus.lower() not in team.club_name.lower()
        ):
            return False

        return True


def render_sidebar_filters(
    teams: list[TeamSeason],
    max_round: int = 5,
) -> FilterState:
    """Render sidebar filters and return current filter state.

    Uses proper Streamlit widget keys to avoid rerun loops.

    Args:
        teams: All available teams (for extracting filter options).
        max_round: Maximum round number in data.

    Returns:
        FilterState with current selections.
    """
    st.sidebar.header("🏀 Filters")

    # Initialize widget defaults in session state if not present
    if "filter_season" not in st.session_state:
        st.session_state.filter_season = "Autumn 2026"
    if "filter_round" not in st.session_state:
        st.session_state.filter_round = max_round
    if "filter_genders" not in st.session_state:
        st.session_state.filter_genders = ["Boys", "Girls"]
    if "filter_age_groups" not in st.session_state:
        st.session_state.filter_age_groups = []
    if "filter_divisions" not in st.session_state:
        st.session_state.filter_divisions = []
    if "filter_grades" not in st.session_state:
        st.session_state.filter_grades = []
    if "filter_club_focus" not in st.session_state:
        st.session_state.filter_club_focus = "All Clubs"
    if "filter_recs_only" not in st.session_state:
        st.session_state.filter_recs_only = False

    # Season selector - use key, read from session_state
    seasons = ["Autumn 2026", "Summer 2025", "Autumn 2025"]
    st.sidebar.selectbox(
        "Season",
        options=seasons,
        key="filter_season",
    )

    # Round slider - clamp to max_round
    if st.session_state.filter_round > max_round:
        st.session_state.filter_round = max_round

    st.sidebar.slider(
        "Round",
        min_value=1,
        max_value=max_round,
        key="filter_round",
        help="Filter data up to this round",
    )

    st.sidebar.divider()

    # Gender filter
    gender_options = ["Boys", "Girls"]
    st.sidebar.multiselect(
        "Gender",
        options=gender_options,
        key="filter_genders",
    )

    # Extract unique age groups and divisions from teams
    available_ages = sorted(set(t.age_group for t in teams))
    available_divisions = sorted(set(t.division for t in teams))
    available_grades = sorted(
        set(
            t.assigned_grade.value if hasattr(t.assigned_grade, "value") else str(t.assigned_grade)
            for t in teams
            if t.assigned_grade
        ),
        key=lambda g: Grade.from_string(g).rank if Grade.from_string(g) else 99,
    )
    available_clubs = sorted(set(t.club_name for t in teams if t.club_name))

    # Age group filter
    st.sidebar.multiselect(
        "Age Group",
        options=available_ages,
        key="filter_age_groups",
        format_func=lambda x: f"U{x}",
        help="Leave empty for all age groups",
    )

    # Division filter
    st.sidebar.multiselect(
        "Division",
        options=available_divisions,
        key="filter_divisions",
        help="Leave empty for all divisions",
    )

    # Grade filter
    st.sidebar.multiselect(
        "Grade",
        options=available_grades,
        key="filter_grades",
        help="Leave empty for all grades",
    )

    st.sidebar.divider()

    # Club focus
    club_options = ["All Clubs"] + available_clubs
    st.sidebar.selectbox(
        "Club Focus",
        options=club_options,
        key="filter_club_focus",
        help="Focus on a specific club's teams",
    )

    # Recommendations toggle
    st.sidebar.checkbox(
        "Show recommendations only",
        key="filter_recs_only",
        help="Only show teams with pending recommendations",
    )

    # Build FilterState from session state values
    state = FilterState(
        season=st.session_state.filter_season,
        max_round=max_round,
        selected_round=st.session_state.filter_round,
        genders=st.session_state.filter_genders,
        age_groups=st.session_state.filter_age_groups,
        divisions=st.session_state.filter_divisions,
        grades=st.session_state.filter_grades,
        club_focus=(
            None
            if st.session_state.filter_club_focus == "All Clubs"
            else st.session_state.filter_club_focus
        ),
        show_recommendations_only=st.session_state.filter_recs_only,
    )

    # Store for other components
    st.session_state.filter_state = state

    # Display filter summary
    _display_filter_summary(state, teams)

    return state


def _display_filter_summary(state: FilterState, teams: list[TeamSeason]) -> None:
    """Display a summary of active filters in the sidebar.

    Args:
        state: Current filter state.
        teams: All teams for counting matches.
    """
    matching_teams = [t for t in teams if state.matches_team(t)]

    st.sidebar.divider()
    st.sidebar.caption(f"📊 Showing {len(matching_teams)} of {len(teams)} teams")

    if state.club_focus:
        st.sidebar.info(f"🎯 Focused on: {state.club_focus}")


def apply_round_filter(
    teams: list[TeamSeason],
    max_round: int,
) -> list[TeamSeason]:
    """Filter games to only include rounds up to max_round.

    Args:
        teams: Teams with full game history.
        max_round: Maximum round to include.

    Returns:
        Teams with games filtered to selected rounds.
    """
    filtered_teams = []

    for team in teams:
        filtered_games = [g for g in team.games if g.round_num <= max_round]
        # Use model_copy to avoid Pydantic validation issues with nested models
        filtered_team = team.model_copy(update={"games": filtered_games})
        filtered_teams.append(filtered_team)

    return filtered_teams
