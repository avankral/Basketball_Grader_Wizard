"""Standings table view component.

Displays team standings with sortable columns and conditional
formatting based on recommendation status.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.cache import get_team_metrics, get_team_sos
from src.grading.metrics import calculate_team_metrics
from src.grading.strength_of_schedule import calculate_sos
from src.models.game_result import TeamSeason
from src.models.recommendation import Recommendation, RecommendationType


def render_standings_table(
    teams: list[TeamSeason],
    recommendations: dict[str, Recommendation] | None = None,
    show_sos: bool = True,
) -> pd.DataFrame:
    """Render standings table with sorting and filtering.

    Args:
        teams: Teams to display.
        recommendations: Dict mapping team name to recommendation.
        show_sos: Whether to include SoS columns.

    Returns:
        DataFrame with standings data.
    """
    if not teams:
        st.info("No teams match the current filters.")
        return pd.DataFrame()

    # Build standings data
    rows = []
    for team in teams:
        # Use cached data if available, fallback to computing
        metrics = get_team_metrics(team.team_name) or calculate_team_metrics(team)
        sos = get_team_sos(team.team_name) or calculate_sos(team)

        rec = recommendations.get(team.team_name) if recommendations else None

        row = {
            "Team": team.team_name,
            "Club": team.club_name or "",
            "Grade": team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "",
            "Division": team.division,
            "W": metrics.wins,
            "L": metrics.losses,
            "Win%": metrics.win_rate,
            "PF": metrics.points_for,
            "PA": metrics.points_against,
            "+/-": metrics.total_margin,
            "Avg Margin": round(metrics.avg_margin, 1),
            "Blowout W": metrics.blowout_wins,
            "Blowout L": metrics.blowout_losses,
        }

        if show_sos:
            row["SoS Score"] = sos.sos_score
            row["Schedule"] = sos.schedule_difficulty
            row["Grade Coverage"] = "✅" if sos.grade_coverage else "⚠️"

        if rec:
            row["Status"] = _get_status_emoji(rec.recommendation_type)
            rec_type = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
            conf_val = rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence)
            row["Recommendation"] = rec_type.title()
            row["Confidence"] = conf_val.title()
        else:
            row["Status"] = ""
            row["Recommendation"] = ""
            row["Confidence"] = ""

        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort by total margin descending by default
    df = df.sort_values("+/-", ascending=False)

    # Display options
    st.subheader("📊 Standings")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sort_col = st.selectbox(
            "Sort by",
            options=["+/-", "Win%", "Blowout W", "Blowout L", "SoS Score"],
            index=0,
        )
    with col2:
        sort_order = st.radio(
            "Order",
            options=["Descending", "Ascending"],
            horizontal=True,
        )
    with col3:
        filter_actions = st.checkbox("Actions only", value=False)

    # Apply sorting
    ascending = sort_order == "Ascending"
    df = df.sort_values(sort_col, ascending=ascending)

    # Filter to actions only if requested
    if filter_actions:
        df = df[df["Status"].isin(["🟢", "🔴", "⚠️"])]

    # Style the dataframe
    styled_df = _style_standings(df)

    # Display
    st.dataframe(
        styled_df,
        width="stretch",
        hide_index=True,
        height=min(len(df) * 35 + 38, 600),
    )

    # Export button
    if st.button("📥 Export to Excel"):
        _export_standings(df)

    return df


def _get_status_emoji(rec_type: RecommendationType | str) -> str:
    """Get status emoji for recommendation type.

    Args:
        rec_type: Recommendation type (enum or string).

    Returns:
        Emoji string.
    """
    # Handle both enum and string types
    rec_str = rec_type.value if hasattr(rec_type, "value") else str(rec_type)

    emoji_map = {
        "promote": "🟢",
        "demote": "🔴",
        "monitor": "👀",
        "review_needed": "⚠️",
        "no_change": "✅",
    }
    return emoji_map.get(rec_str, "")


def _style_standings(df: pd.DataFrame) -> pd.DataFrame:
    """Apply conditional formatting to standings DataFrame.

    Args:
        df: Standings DataFrame.

    Returns:
        Styled DataFrame.
    """

    def highlight_margin(val):
        """Color margins based on value."""
        if isinstance(val, (int, float)):
            if val >= 20:
                return "background-color: #d4edda"  # Light green
            elif val <= -20:
                return "background-color: #f8d7da"  # Light red
        return ""

    def highlight_status(val):
        """Color status column."""
        if val == "🟢":  # noqa: SIM116
            return "background-color: #d4edda"
        elif val == "🔴":
            return "background-color: #f8d7da"
        elif val == "⚠️":
            return "background-color: #fff3cd"
        return ""

    # Note: Streamlit dataframe doesn't support full styling,
    # but we return the df for potential future use
    return df


def _export_standings(df: pd.DataFrame) -> None:
    """Export standings to downloadable Excel.

    Args:
        df: Standings DataFrame.
    """
    import io
    from datetime import datetime

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Standings")

    st.download_button(
        label="Download Excel",
        data=buffer.getvalue(),
        file_name=f"standings_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
