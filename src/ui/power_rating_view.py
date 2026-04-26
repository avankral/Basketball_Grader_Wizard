"""Power Rating visualization and analysis view.

Displays ELO-based power ratings with:
- Current ratings vs expected by grade
- Rating trajectory over season
- Grade mismatch detection
- Rating distribution by grade
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.grading.grades import GRADE_ORDER
from src.grading.power_rating import (
    GRADE_BASE_RATINGS,
    TeamPowerRating,
    calculate_power_ratings,
    get_rating_comparison,
)

if TYPE_CHECKING:
    from src.models.game_result import TeamSeason

# Ford color palette
FORD_BLUE = "#00095B"
ACCENT_BLUE = "#1C69D4"
LIGHT_BLUE = "#E8F1FC"
SUCCESS_GREEN = "#198754"
WARNING_YELLOW = "#FFC107"
ERROR_RED = "#DC3545"


def render_power_rating_view(teams: list[TeamSeason]) -> None:
    """Render the power rating analysis view.

    Args:
        teams: List of TeamSeason objects to analyze.
    """
    st.markdown("## ⚡ Power Ratings")
    st.markdown(
        "ELO-based power rating system that dynamically adjusts based on "
        "game outcomes, margin of victory, and opponent strength."
    )

    if not teams:
        st.warning("No team data available. Please upload data first.")
        return

    # Calculate power ratings
    with st.spinner("Calculating power ratings..."):
        ratings = calculate_power_ratings(teams)

    # Summary metrics
    _render_summary_metrics(ratings)

    st.divider()

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Rating Table",
            "📈 Rating Trends",
            "⚠️ Grade Mismatches",
            "📉 Distribution",
        ]
    )

    with tab1:
        _render_rating_table(ratings)

    with tab2:
        _render_rating_trends(ratings)

    with tab3:
        _render_grade_mismatches(ratings)

    with tab4:
        _render_rating_distribution(ratings)


def _render_summary_metrics(ratings: dict[str, TeamPowerRating]) -> None:
    """Render summary metric cards."""
    # Calculate summary stats
    rated_teams = [r for r in ratings.values() if r.games_rated >= 3]

    if not rated_teams:
        st.info("Not enough data for summary metrics (need teams with 3+ games)")
        return

    highest = max(rated_teams, key=lambda x: x.current_rating)
    lowest = min(rated_teams, key=lambda x: x.current_rating)
    avg_rating = sum(r.current_rating for r in rated_teams) / len(rated_teams)

    severe_mismatches = sum(1 for r in rated_teams if r.grade_mismatch_severity == "SEVERE")
    moderate_mismatches = sum(1 for r in rated_teams if r.grade_mismatch_severity == "MODERATE")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="🏆 Highest Rated",
            value=f"{highest.current_rating:.0f}",
            help=highest.team_name,
        )

    with col2:
        st.metric(
            label="📉 Lowest Rated",
            value=f"{lowest.current_rating:.0f}",
            help=lowest.team_name,
        )

    with col3:
        st.metric(
            label="📊 Average Rating",
            value=f"{avg_rating:.0f}",
        )

    with col4:
        st.metric(
            label="⚠️ Severe Mismatches",
            value=severe_mismatches,
            delta=f"{moderate_mismatches} moderate",
            delta_color="inverse" if severe_mismatches > 0 else "off",
        )

    with col5:
        st.metric(
            label="📋 Teams Rated",
            value=len(rated_teams),
            help="Teams with 3+ games rated",
        )


def _render_rating_table(ratings: dict[str, TeamPowerRating]) -> None:
    """Render sortable rating table."""
    st.markdown("### All Team Ratings")

    comparisons = get_rating_comparison(ratings)

    if not comparisons:
        st.info("No teams with sufficient games for rating")
        return

    df = pd.DataFrame(comparisons)

    # Add visual indicators
    def style_mismatch(val: str) -> str:
        colors = {
            "NONE": "",
            "MINOR": f"background-color: {LIGHT_BLUE}",
            "MODERATE": f"background-color: {WARNING_YELLOW}",
            "SEVERE": f"background-color: {ERROR_RED}; color: white",
        }
        return colors.get(val, "")

    def style_trend(val: str) -> str:
        colors = {
            "RISING": f"color: {SUCCESS_GREEN}",
            "FALLING": f"color: {ERROR_RED}",
            "STABLE": "",
        }
        return colors.get(val, "")

    # Display with formatting
    st.dataframe(
        df.style.map(style_mismatch, subset=["mismatch_severity"]).map(
            style_trend, subset=["trend"]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "team_name": st.column_config.TextColumn("Team", width="medium"),
            "assigned_grade": st.column_config.TextColumn("Grade", width="small"),
            "current_rating": st.column_config.NumberColumn("Rating", format="%.1f"),
            "expected_rating": st.column_config.NumberColumn("Expected", format="%.1f"),
            "rating_diff": st.column_config.NumberColumn("Diff", format="%+.1f"),
            "suggested_grade": st.column_config.TextColumn("Suggested", width="small"),
            "mismatch_severity": st.column_config.TextColumn("Mismatch", width="small"),
            "trend": st.column_config.TextColumn("Trend", width="small"),
            "peak_rating": st.column_config.NumberColumn("Peak", format="%.1f"),
            "lowest_rating": st.column_config.NumberColumn("Low", format="%.1f"),
            "games_rated": st.column_config.NumberColumn("Games", width="small"),
        },
    )

    # Download option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Ratings CSV",
        data=csv,
        file_name="power_ratings.csv",
        mime="text/csv",
    )


def _render_rating_trends(ratings: dict[str, TeamPowerRating]) -> None:
    """Render rating trajectory charts."""
    st.markdown("### Rating Trends Over Season")

    # Team selector
    team_names = sorted([name for name, r in ratings.items() if r.games_rated >= 2])

    if not team_names:
        st.info("Not enough data for trend visualization")
        return

    selected_teams = st.multiselect(
        "Select teams to compare",
        options=team_names,
        default=team_names[:5] if len(team_names) >= 5 else team_names,
        max_selections=10,
    )

    if not selected_teams:
        st.info("Select at least one team to view trends")
        return

    # Build trend data
    trend_data = []
    for team_name in selected_teams:
        rating = ratings[team_name]
        for snap in rating.rating_history:
            trend_data.append(
                {
                    "Team": team_name,
                    "Round": snap.round_num,
                    "Rating": snap.rating,
                    "Change": snap.rating_change,
                    "Opponent": snap.game_opponent or "Initial",
                    "Result": snap.game_result or "",
                }
            )

    df = pd.DataFrame(trend_data)

    # Line chart
    fig = px.line(
        df,
        x="Round",
        y="Rating",
        color="Team",
        markers=True,
        hover_data=["Opponent", "Result", "Change"],
        title="Power Rating Progression",
    )

    # Add grade baseline references
    for grade in [g for g in GRADE_ORDER if g.value in ["A", "B1", "C1", "D"]]:
        expected = GRADE_BASE_RATINGS[grade]
        fig.add_hline(
            y=expected,
            line_dash="dot",
            line_color="gray",
            opacity=0.5,
            annotation_text=f"Grade {grade.value}",
            annotation_position="right",
        )

    fig.update_layout(
        xaxis_title="Round",
        yaxis_title="Power Rating",
        hovermode="x unified",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_grade_mismatches(ratings: dict[str, TeamPowerRating]) -> None:
    """Render grade mismatch analysis."""
    st.markdown("### Grade Mismatch Analysis")
    st.markdown(
        "Teams whose power rating significantly differs from their assigned grade's expected rating."
    )

    comparisons = get_rating_comparison(ratings)
    mismatches = [c for c in comparisons if c["mismatch_severity"] in ["MODERATE", "SEVERE"]]

    if not mismatches:
        st.success("✅ No significant grade mismatches detected")
        return

    # Separate overperformers and underperformers
    overperformers = [c for c in mismatches if c["rating_diff"] > 0]
    underperformers = [c for c in mismatches if c["rating_diff"] < 0]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📈 Overperforming (Consider Promotion)")
        if overperformers:
            for team in sorted(overperformers, key=lambda x: x["rating_diff"], reverse=True):
                severity_icon = "🔴" if team["mismatch_severity"] == "SEVERE" else "🟡"
                st.markdown(
                    f"{severity_icon} **{team['team_name']}** ({team['assigned_grade']})\n"
                    f"- Rating: {team['current_rating']:.0f} (+{team['rating_diff']:.0f} above expected)\n"
                    f"- Suggested: {team['suggested_grade']}\n"
                    f"- Trend: {team['trend']}"
                )
        else:
            st.info("No teams significantly overperforming")

    with col2:
        st.markdown("#### 📉 Underperforming (Consider Demotion)")
        if underperformers:
            for team in sorted(underperformers, key=lambda x: x["rating_diff"]):
                severity_icon = "🔴" if team["mismatch_severity"] == "SEVERE" else "🟡"
                st.markdown(
                    f"{severity_icon} **{team['team_name']}** ({team['assigned_grade']})\n"
                    f"- Rating: {team['current_rating']:.0f} ({team['rating_diff']:.0f} below expected)\n"
                    f"- Suggested: {team['suggested_grade']}\n"
                    f"- Trend: {team['trend']}"
                )
        else:
            st.info("No teams significantly underperforming")


def _render_rating_distribution(ratings: dict[str, TeamPowerRating]) -> None:
    """Render rating distribution by grade."""
    st.markdown("### Rating Distribution by Grade")

    # Prepare box plot data including team names
    box_data = []
    for team_rating in ratings.values():
        if team_rating.assigned_grade and team_rating.games_rated >= 2:
            grade_key = (
                team_rating.assigned_grade.value
                if hasattr(team_rating.assigned_grade, "value")
                else str(team_rating.assigned_grade)
            )
            box_data.append(
                {
                    "Grade": grade_key,
                    "Rating": team_rating.current_rating,
                    "Team": team_rating.team_name,
                }
            )

    if not box_data:
        st.info("Not enough data for distribution chart")
        return

    df = pd.DataFrame(box_data)

    # Create box plot
    fig = go.Figure()

    # Add expected rating line for each grade
    grade_order = [g.value for g in GRADE_ORDER if g.value in df["Grade"].unique()]

    for grade in grade_order:
        grade_enum = next((g for g in GRADE_ORDER if g.value == grade), None)
        if grade_enum:
            expected = GRADE_BASE_RATINGS.get(grade_enum, 1500)
            grade_df = df[df["Grade"] == grade]

            fig.add_trace(
                go.Box(
                    y=grade_df["Rating"],
                    name=grade,
                    boxpoints="all",
                    jitter=0.3,
                    marker_color=ACCENT_BLUE,
                    customdata=grade_df["Team"],
                    hovertemplate=("<b>%{customdata}</b><br>Rating: %{y:.1f}<br><extra></extra>"),
                )
            )

    fig.update_layout(
        title="Power Rating Distribution by Assigned Grade",
        xaxis_title="Assigned Grade",
        yaxis_title="Power Rating",
        showlegend=False,
        template="plotly_white",
    )

    # Add expected rating reference lines
    for grade in GRADE_ORDER:
        expected = GRADE_BASE_RATINGS.get(grade, 1500)
        fig.add_hline(
            y=expected,
            line_dash="dot",
            line_color="gray",
            opacity=0.3,
        )

    st.plotly_chart(fig, use_container_width=True)

    # Interpretation
    st.markdown(
        """
        **How to interpret this chart:**
        - Each box shows the rating distribution for teams at that grade
        - The horizontal dotted lines show expected ratings for each grade
        - Wide spread within a grade indicates inconsistent team skill levels
        - Teams outside their grade's expected range may be misgraded
        """
    )
