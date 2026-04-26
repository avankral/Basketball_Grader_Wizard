"""KPI metric cards for the dashboard.

Displays key performance indicators in Ford Blue styled cards.
"""

from __future__ import annotations

import streamlit as st

from src.grading.metrics import TeamMetrics
from src.grading.strength_of_schedule import StrengthOfSchedule
from src.models.game_result import TeamSeason
from src.models.recommendation import Recommendation, RecommendationType


def _get_rec_type_str(rec_type: RecommendationType | str) -> str:
    """Normalize recommendation type to string for comparison."""
    return rec_type.value if hasattr(rec_type, "value") else str(rec_type)


def render_kpi_cards(
    teams: list[TeamSeason],
    recommendations: list[Recommendation],
    overrides_count: int = 0,
) -> None:
    """Render main KPI cards at top of dashboard.

    Args:
        teams: All teams in current filter.
        recommendations: All recommendations.
        overrides_count: Number of overrides applied this season.
    """
    # Calculate metrics
    total_teams = len(teams)
    total_games = sum(t.games_played for t in teams)

    pending_recs = [
        r
        for r in recommendations
        if _get_rec_type_str(r.recommendation_type) in ("promote", "demote", "review_needed")
    ]
    promote_count = sum(
        1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "promote"
    )
    demote_count = sum(
        1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "demote"
    )
    review_count = sum(
        1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "review_needed"
    )

    # Render cards in columns
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Teams",
            value=total_teams,
            help="Teams matching current filters",
        )

    with col2:
        st.metric(
            label="Games Played",
            value=total_games,
            help="Total games across all teams",
        )

    with col3:
        st.metric(
            label="Pending Actions",
            value=len(pending_recs),
            delta=f"↑{promote_count} ↓{demote_count} ⚠{review_count}",
            delta_color="off",
            help="Recommendations requiring action",
        )

    with col4:
        # Calculate grade mismatch count
        mismatch_count = sum(
            1
            for r in recommendations
            if r.strength_of_schedule_note
            and "Never played at assigned grade" in r.strength_of_schedule_note
        )
        st.metric(
            label="Grade Mismatches",
            value=mismatch_count,
            help="Teams not playing at assigned grade level",
        )

    with col5:
        st.metric(
            label="Overrides Applied",
            value=overrides_count,
            help="Admin overrides this season",
        )


def render_team_summary_card(
    team: TeamSeason,
    metrics: TeamMetrics,
    sos: StrengthOfSchedule,
    recommendation: Recommendation | None = None,
) -> None:
    """Render a detailed summary card for a single team.

    Args:
        team: Team data.
        metrics: Calculated metrics.
        sos: Strength of schedule analysis.
        recommendation: Optional recommendation for this team.
    """
    # Determine card style based on recommendation
    if recommendation:
        rec_type = _get_rec_type_str(recommendation.recommendation_type)
        if rec_type == "promote":
            border_color = "#198754"  # Success green
            icon = "🟢"
        elif rec_type == "demote":
            border_color = "#DC3545"  # Error red
            icon = "🔴"
        elif rec_type == "review_needed":
            border_color = "#FFC107"  # Warning yellow
            icon = "⚠️"
        elif rec_type == "monitor":
            border_color = "#1C69D4"  # Accent blue
            icon = "👀"
        else:
            border_color = "#00095B"  # Ford blue
            icon = "✅"
    else:
        border_color = "#00095B"
        icon = ""

    # Create card with custom styling
    st.markdown(
        f"""
        <div style="
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            background-color: #F5F5F5;
        ">
            <h3 style="margin: 0 0 8px 0; color: #00095B;">
                {icon} {team.team_name}
            </h3>
            <p style="margin: 4px 0; color: #666;">
                <strong>Grade:</strong> {team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A"} |
                <strong>Division:</strong> {team.division} |
                <strong>Club:</strong> {team.club_name or "Unknown"}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Stats columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Performance**")
        st.write(f"Record: {metrics.wins}W - {metrics.losses}L")
        st.write(f"Win Rate: {metrics.win_rate}%")
        st.write(f"Avg Margin: {metrics.avg_margin:+.1f}")

    with col2:
        st.markdown("**Blowouts**")
        st.write(f"🟢 Blowout Wins: {metrics.blowout_wins}")
        st.write(f"🔴 Blowout Losses: {metrics.blowout_losses}")
        st.write(f"Close Games: {metrics.close_wins + metrics.close_losses}")

    with col3:
        st.markdown("**Schedule**")
        st.write(f"SoS Score: {sos.sos_score}/100")
        st.write(f"Difficulty: {sos.schedule_difficulty}")
        if sos.never_played_at_grade:
            st.warning("⚠️ Never played at assigned grade")

    # Show recommendation if present
    if recommendation and recommendation.requires_action:
        st.divider()
        confidence_colors = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        conf_val = recommendation.confidence.value if hasattr(recommendation.confidence, "value") else str(recommendation.confidence)
        rec_type = recommendation.recommendation_type.value if hasattr(recommendation.recommendation_type, "value") else str(recommendation.recommendation_type)
        conf_icon = confidence_colors.get(conf_val, "")

        st.markdown(f"**Recommendation:** {rec_type.upper()}")
        st.markdown(f"**Confidence:** {conf_icon} {conf_val.title()}")
        st.info(recommendation.explanation)
