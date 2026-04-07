"""Strength of Schedule analysis view.

Displays SoS metrics with visualizations showing:
- Opponent grade distribution
- Grade coverage warnings
- Schedule difficulty comparisons
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.cache import get_all_metrics, get_all_sos
from src.grading.strength_of_schedule import StrengthOfSchedule
from src.models.game_result import TeamSeason
from src.ui.charts import create_grade_distribution_chart, create_sos_distribution_chart


def render_sos_analysis(
    teams: list[TeamSeason],
    selected_team: str | None = None,
) -> None:
    """Render Strength of Schedule analysis view.

    Args:
        teams: Teams to analyze.
        selected_team: Optional team to highlight.
    """
    if not teams:
        st.info("No teams available for SoS analysis.")
        return

    st.subheader("📈 Strength of Schedule Analysis")

    # Use cached data for performance
    sos_list = get_all_sos(teams)
    metrics_list = get_all_metrics(teams)

    # Key insights at top
    _render_sos_insights(sos_list)

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "🎯 Grade Distribution", "⚠️ Warnings"])

    with tab1:
        _render_sos_overview(teams, metrics_list, sos_list)

    with tab2:
        _render_grade_distribution(teams, sos_list, selected_team)

    with tab3:
        _render_sos_warnings(teams, sos_list)


def _render_sos_insights(sos_list: list[StrengthOfSchedule]) -> None:
    """Render key SoS insights as metric cards.

    Args:
        sos_list: SoS analysis for all teams.
    """
    valid_sos = [s for s in sos_list if s.total_games > 0]

    if not valid_sos:
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_sos = sum(s.sos_score for s in valid_sos) / len(valid_sos)
        st.metric(
            "Avg SoS Score",
            f"{avg_sos:.1f}",
            help="Average strength of schedule across all teams",
        )

    with col2:
        hardest = max(valid_sos, key=lambda s: s.sos_score)
        st.metric(
            "Hardest Schedule",
            f"{hardest.sos_score:.1f}",
            delta=hardest.team_name[:20],
            delta_color="off",
        )

    with col3:
        easiest = min(valid_sos, key=lambda s: s.sos_score)
        st.metric(
            "Easiest Schedule",
            f"{easiest.sos_score:.1f}",
            delta=easiest.team_name[:20],
            delta_color="off",
        )

    with col4:
        no_coverage = sum(1 for s in valid_sos if s.never_played_at_grade)
        st.metric(
            "Grade Coverage Issues",
            no_coverage,
            help="Teams that never played at their assigned grade",
        )


def _render_sos_overview(
    teams: list[TeamSeason],
    metrics_list: list,
    sos_list: list[StrengthOfSchedule],
) -> None:
    """Render SoS overview chart.

    Args:
        teams: Team data.
        metrics_list: Metrics for each team.
        sos_list: SoS for each team.
    """
    st.markdown("### SoS Score vs Win Rate")
    st.markdown(
        "Teams in the **upper left** have high win rates against easy schedules. "
        "Teams in the **lower right** are struggling against hard schedules."
    )

    fig = create_sos_distribution_chart(teams, metrics_list, sos_list)
    st.plotly_chart(fig, width="stretch")

    # SoS table
    st.markdown("### SoS Summary Table")

    rows = []
    for team, sos in zip(teams, sos_list, strict=False):
        rows.append(
            {
                "Team": team.team_name,
                "Grade": team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A",
                "SoS Score": sos.sos_score,
                "Difficulty": sos.schedule_difficulty,
                "Games": sos.total_games,
                "Played UP": sos.played_above_count,
                "Played AT Grade": sos.played_at_grade_count,
                "Played DOWN": sos.played_below_count,
                "Grade Coverage": "✅" if sos.grade_coverage else "⚠️ No",
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("SoS Score", ascending=False)

    st.dataframe(df, width="stretch", hide_index=True)


def _render_grade_distribution(
    teams: list[TeamSeason],
    sos_list: list[StrengthOfSchedule],
    selected_team: str | None = None,
) -> None:
    """Render opponent grade distribution heatmap.

    Args:
        teams: Team data.
        sos_list: SoS for each team.
        selected_team: Team to highlight.
    """
    st.markdown("### Opponent Grade Distribution")
    st.markdown(
        "Shows what percentage of each team's games were against each grade level. "
        "Look for teams with no games at their assigned grade."
    )

    # Filter to teams with games
    valid_sos = [s for s in sos_list if s.total_games > 0]

    if not valid_sos:
        st.info("No game data available for grade distribution analysis.")
        return

    fig = create_grade_distribution_chart(valid_sos)
    st.plotly_chart(fig, width="stretch")

    # Team selector for detailed view
    team_names = [s.team_name for s in valid_sos]
    selected = st.selectbox(
        "Select team for detailed breakdown",
        options=team_names,
        index=team_names.index(selected_team) if selected_team in team_names else 0,
    )

    if selected:
        sos = next(s for s in valid_sos if s.team_name == selected)
        team = next(t for t in teams if t.team_name == selected)

        st.markdown(f"#### {selected}")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                "**Assigned Grade:** "
                + (team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A")
            )
            st.markdown(f"**SoS Score:** {sos.sos_score}/100")
            st.markdown(f"**Schedule Difficulty:** {sos.schedule_difficulty}")

        with col2:
            st.markdown("**Games Breakdown:**")
            st.write(f"- Played UP: {sos.played_above_count}")
            st.write(f"- Played AT Grade: {sos.played_at_grade_count}")
            st.write(f"- Played DOWN: {sos.played_below_count}")

        if sos.never_played_at_grade and team.assigned_grade:
            grade_str = team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade)
            st.warning(
                f"⚠️ This team has not played any {grade_str}-grade opponents. "
                "Grade placement cannot be validated."
            )


def _render_sos_warnings(
    teams: list[TeamSeason],
    sos_list: list[StrengthOfSchedule],
) -> None:
    """Render SoS warnings for teams with grade coverage issues.

    Args:
        teams: Team data.
        sos_list: SoS for each team.
    """
    st.markdown("### ⚠️ Grade Coverage Warnings")
    st.markdown(
        "These teams have not played any opponents at their assigned grade level. "
        "Their grade placement cannot be validated from current data."
    )

    warnings = []
    for team, sos in zip(teams, sos_list, strict=False):
        if sos.never_played_at_grade and team.assigned_grade and sos.total_games > 0:
            grade_str = team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade)
            warnings.append(
                {
                    "Team": team.team_name,
                    "Assigned Grade": grade_str,
                    "Games Played": sos.total_games,
                    "Played UP": sos.played_above_count,
                    "Played DOWN": sos.played_below_count,
                    "Issue": f"0 games vs {grade_str} opponents",
                }
            )

    if not warnings:
        st.success("✅ All teams have played at their assigned grade level.")
        return

    df = pd.DataFrame(warnings)
    st.dataframe(df, width="stretch", hide_index=True)

    st.info(
        f"**{len(warnings)} team(s)** require grade coverage review. "
        "Consider scheduling these teams against opponents at their assigned grade."
    )
