"""Historical season comparison and analytics view.

Displays cross-season analysis including:
- Team performance trends over multiple seasons
- Grade progression history
- Club-level aggregate performance
- Pattern identification
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.historical import (
    HistoricalAnalyzer,
    compare_seasons,
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

# Default path for historical data
HISTORICAL_DATA_PATH = Path("data/historical_seasons.parquet")


def render_historical_view(
    teams: list[TeamSeason],
    current_season: str = "Current",
) -> None:
    """Render the historical analysis view.

    Args:
        teams: Current season team data.
        current_season: Current season identifier.
    """
    st.markdown("## 📜 Historical Analysis")
    st.markdown(
        "Track team and club performance across multiple seasons. "
        "Identify patterns in grade progression and grading accuracy."
    )

    # Initialize analyzer
    analyzer = _get_or_create_analyzer()

    # Sidebar actions for historical data management
    with st.sidebar:
        st.markdown("### Historical Data")

        if st.button("💾 Save Current Season"):
            _save_current_season(analyzer, teams, current_season)

        if st.button("📂 Load Historical Data"):
            _load_historical_data(analyzer)

        st.markdown(f"**Seasons on record:** {len(_get_unique_seasons(analyzer))}")

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Current vs Historical",
            "📈 Team Trends",
            "🏢 Club Analysis",
            "🔍 Pattern Detection",
        ]
    )

    with tab1:
        _render_current_vs_historical(teams, current_season, analyzer)

    with tab2:
        _render_team_trends(analyzer)

    with tab3:
        _render_club_analysis(analyzer)

    with tab4:
        _render_pattern_detection(analyzer)


def _get_or_create_analyzer() -> HistoricalAnalyzer:
    """Get or create the historical analyzer from session state."""
    if "historical_analyzer" not in st.session_state:
        analyzer = HistoricalAnalyzer(data_dir=Path("data"))
        # Try to load existing data
        if HISTORICAL_DATA_PATH.exists():
            try:
                analyzer.load_from_parquet(HISTORICAL_DATA_PATH)
            except Exception as e:
                st.warning(f"Could not load historical data: {e}")
        st.session_state.historical_analyzer = analyzer
    return st.session_state.historical_analyzer


def _get_unique_seasons(analyzer: HistoricalAnalyzer) -> list[str]:
    """Get list of unique seasons in the analyzer."""
    seasons = set()
    for history in analyzer.team_histories.values():
        for s in history.seasons:
            seasons.add(s.season)
    return sorted(seasons)


def _save_current_season(
    analyzer: HistoricalAnalyzer,
    teams: list[TeamSeason],
    season: str,
) -> None:
    """Save current season to historical data."""
    if not teams:
        st.error("No team data to save")
        return

    # Get season name from user
    season_name = st.session_state.get("save_season_name", season)

    analyzer.add_season_data(season_name, teams)

    try:
        HISTORICAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        analyzer.save_to_parquet(HISTORICAL_DATA_PATH)
        st.success(f"✅ Season '{season_name}' saved to historical data")
    except Exception as e:
        st.error(f"Error saving: {e}")


def _load_historical_data(analyzer: HistoricalAnalyzer) -> None:
    """Load historical data from file."""
    if HISTORICAL_DATA_PATH.exists():
        try:
            analyzer.load_from_parquet(HISTORICAL_DATA_PATH)
            st.success(f"✅ Loaded historical data with {len(analyzer.team_histories)} teams")
        except Exception as e:
            st.error(f"Error loading: {e}")
    else:
        st.info("No historical data file found. Save a season first.")


def _render_current_vs_historical(
    teams: list[TeamSeason],
    current_season: str,
    analyzer: HistoricalAnalyzer,
) -> None:
    """Render current vs historical comparison."""
    st.markdown("### Current Season vs Historical Performance")

    if not teams:
        st.warning("No current season data available")
        return

    if not analyzer.team_histories:
        st.info("No historical data available. Save previous seasons to enable comparison.")
        # Still show current season summary
        st.markdown("#### Current Season Summary")
        _render_current_season_summary(teams)
        return

    # Generate comparison
    comparison_df = compare_seasons(current_season, teams, analyzer)

    if comparison_df.empty:
        st.info("No comparison data available")
        return

    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    # Highlight significant changes
    st.markdown("#### Notable Changes")

    for _, row in comparison_df.iterrows():
        if row["Historical Avg Win%"] == "N/A":
            continue

        current = row["Current Win%"]
        historical = float(row["Historical Avg Win%"])
        diff = current - historical

        if abs(diff) > 15:
            direction = "📈 improved" if diff > 0 else "📉 declined"
            color = SUCCESS_GREEN if diff > 0 else ERROR_RED
            st.markdown(
                f"- **{row['Team']}** has {direction} by "
                f"<span style='color:{color}'>{abs(diff):.1f}%</span> from historical average",
                unsafe_allow_html=True,
            )


def _render_current_season_summary(teams: list[TeamSeason]) -> None:
    """Render summary of current season."""

    def _get_result_str(result) -> str:
        return result.value if hasattr(result, "value") else str(result)

    data = []
    for team in teams:
        wins = sum(1 for g in team.games if _get_result_str(g.result) == "Won")
        losses = sum(1 for g in team.games if _get_result_str(g.result) == "Lost")
        games = wins + losses
        win_rate = (wins / games * 100) if games > 0 else 0

        data.append(
            {
                "Team": team.team_name,
                "Club": team.club_name,
                "Grade": team.assigned_grade.value
                if hasattr(team.assigned_grade, "value")
                else str(team.assigned_grade)
                if team.assigned_grade
                else "N/A",
                "W": wins,
                "L": losses,
                "Win%": round(win_rate, 1),
            }
        )

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("Win%", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_team_trends(analyzer: HistoricalAnalyzer) -> None:
    """Render team performance trends over seasons."""
    st.markdown("### Team Performance Trends")

    if not analyzer.team_histories:
        st.info("No historical data available")
        return

    # Team selector
    team_names = sorted(analyzer.team_histories.keys())
    selected_team = st.selectbox(
        "Select Team",
        options=team_names,
        key="historical_team_select",
    )

    if not selected_team:
        return

    history = analyzer.get_team_history(selected_team)
    if not history or not history.seasons:
        st.info("No historical data for this team")
        return

    # Team info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Club", history.club_name)
    with col2:
        st.metric("Seasons Played", len(history.seasons))
    with col3:
        st.metric("Avg Win Rate", f"{history.avg_win_rate:.1f}%")
    with col4:
        st.metric("Trend", history.trend)

    # Season-by-season table
    st.markdown("#### Season History")
    comparison_df = analyzer.get_season_comparison_df(selected_team)
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    # Trend chart
    if len(history.seasons) > 1:
        st.markdown("#### Performance Over Time")

        seasons = sorted(history.seasons, key=lambda x: x.season)
        chart_data = pd.DataFrame(
            [
                {
                    "Season": s.season,
                    "Win Rate": s.win_rate,
                    "Avg Margin": s.avg_margin,
                    "Grade": s.grade.value
                    if hasattr(s.grade, "value")
                    else str(s.grade)
                    if s.grade
                    else "N/A",
                }
                for s in seasons
            ]
        )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=chart_data["Season"],
                y=chart_data["Win Rate"],
                mode="lines+markers",
                name="Win Rate (%)",
                line={"color": FORD_BLUE},
                yaxis="y1",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=chart_data["Season"],
                y=chart_data["Avg Margin"],
                mode="lines+markers",
                name="Avg Margin",
                line={"color": ACCENT_BLUE},
                yaxis="y2",
            )
        )

        fig.update_layout(
            title=f"{selected_team} - Performance Trend",
            xaxis_title="Season",
            yaxis={"title": "Win Rate (%)", "side": "left"},
            yaxis2={"title": "Avg Margin", "side": "right", "overlaying": "y"},
            hovermode="x unified",
            template="plotly_white",
        )

        st.plotly_chart(fig, use_container_width=True)

        # Grade progression
        st.markdown("#### Grade Progression")
        grades = history.grade_progression
        grade_str = " → ".join([f"{s}: {g}" for s, g in grades])
        st.markdown(f"**{grade_str}**")


def _render_club_analysis(analyzer: HistoricalAnalyzer) -> None:
    """Render club-level aggregate analysis."""
    st.markdown("### Club Performance Analysis")

    if not analyzer.club_histories:
        st.info("No historical data available")
        return

    # Club summary table
    club_df = analyzer.get_club_summary_df()
    if club_df.empty:
        st.info("No club data available")
        return

    st.dataframe(club_df, use_container_width=True, hide_index=True)

    # Club comparison chart
    st.markdown("#### Club Comparison")

    fig = px.bar(
        club_df,
        x="Club",
        y="Overall Win%",
        color="Overall Win%",
        color_continuous_scale=[[0, ERROR_RED], [0.5, WARNING_YELLOW], [1, SUCCESS_GREEN]],
        title="Club Win Rates",
    )

    fig.update_layout(
        xaxis_title="Club",
        yaxis_title="Overall Win Rate (%)",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Promotion/Demotion rates
    if "Promotion Rate%" in club_df.columns and "Demotion Rate%" in club_df.columns:
        st.markdown("#### Grade Change Rates by Club")

        fig2 = go.Figure()

        fig2.add_trace(
            go.Bar(
                name="Promotion Rate",
                x=club_df["Club"],
                y=club_df["Promotion Rate%"],
                marker_color=SUCCESS_GREEN,
            )
        )

        fig2.add_trace(
            go.Bar(
                name="Demotion Rate",
                x=club_df["Club"],
                y=club_df["Demotion Rate%"],
                marker_color=ERROR_RED,
            )
        )

        fig2.update_layout(
            barmode="group",
            xaxis_title="Club",
            yaxis_title="Rate (%)",
            template="plotly_white",
        )

        st.plotly_chart(fig2, use_container_width=True)


def _render_pattern_detection(analyzer: HistoricalAnalyzer) -> None:
    """Render grading pattern analysis."""
    st.markdown("### Pattern Detection")
    st.markdown("Identifies patterns in grading accuracy based on historical data.")

    if not analyzer.team_histories:
        st.info("No historical data available for pattern analysis")
        return

    patterns = analyzer.identify_grading_patterns()

    if not patterns:
        st.success("✅ No significant grading patterns detected")
        return

    # Group patterns by type
    pattern_types = {}
    for p in patterns:
        ptype = p["type"]
        if ptype not in pattern_types:
            pattern_types[ptype] = []
        pattern_types[ptype].append(p)

    # Display patterns
    for ptype, items in pattern_types.items():
        icon = "📈" if "OVER" in ptype or "PROMOTION" in ptype else "📉"
        st.markdown(f"#### {icon} {ptype.replace('_', ' ').title()}")

        for item in items:
            if "team" in item:
                st.markdown(f"- **{item['team']}** ({item['club']}): {item['detail']}")
            elif "club" in item:
                st.markdown(f"- **{item['club']}**: {item['detail']}")

    # Recommendations based on patterns
    st.markdown("---")
    st.markdown("#### 💡 Recommendations")

    recommendations = []

    if "CONSISTENT_OVERPERFORMER" in pattern_types:
        recommendations.append(
            "Review initial grade assignments for teams with multiple seasons of overperformance"
        )

    if "CONSISTENT_UNDERPERFORMER" in pattern_types:
        recommendations.append(
            "Consider earlier intervention for struggling teams to improve experience"
        )

    if "HIGH_PROMOTION_CLUB" in pattern_types:
        recommendations.append(
            "Investigate if certain clubs consistently request lower grades than appropriate"
        )

    if "HIGH_DEMOTION_CLUB" in pattern_types:
        recommendations.append("Review grading process for clubs with high demotion rates")

    if recommendations:
        for rec in recommendations:
            st.markdown(f"- {rec}")
    else:
        st.info("No specific recommendations based on current patterns")
