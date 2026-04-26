"""Head-to-head team comparison view.

Allows side-by-side comparison of two teams' metrics,
common opponent analysis, and predicted matchup outcomes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.grading.strength_of_schedule import calculate_sos

if TYPE_CHECKING:
    from src.models.game_result import TeamSeason

# Ford color palette
FORD_BLUE = "#00095B"
ACCENT_BLUE = "#1C69D4"
LIGHT_BLUE = "#E8F1FC"
SUCCESS_GREEN = "#198754"
WARNING_YELLOW = "#FFC107"
ERROR_RED = "#DC3545"


def render_comparison_view(teams: list[TeamSeason]) -> None:
    """Render the head-to-head comparison view.

    Args:
        teams: List of all teams available for comparison.
    """
    st.markdown("## 🆚 Head-to-Head Comparison")
    st.markdown("Select two teams to compare their performance side-by-side.")

    if not teams:
        st.warning("No team data available. Please upload data first.")
        return

    team_names = sorted([t.team_name for t in teams])
    team_dict = {t.team_name: t for t in teams}

    col1, col2 = st.columns(2)

    with col1:
        team_a_name = st.selectbox(
            "Select Team A",
            options=team_names,
            key="comparison_team_a",
        )

    with col2:
        # Filter out team A from options
        team_b_options = [n for n in team_names if n != team_a_name]
        team_b_name = st.selectbox(
            "Select Team B",
            options=team_b_options,
            key="comparison_team_b",
        )

    if team_a_name and team_b_name:
        team_a = team_dict[team_a_name]
        team_b = team_dict[team_b_name]

        # Calculate metrics
        metrics_a = calculate_team_metrics(team_a)
        metrics_b = calculate_team_metrics(team_b)

        # Calculate SoS
        sos_a = calculate_sos(team_a)
        sos_b = calculate_sos(team_b)

        # Display comparison
        st.divider()
        _render_side_by_side(team_a, team_b, metrics_a, metrics_b, sos_a, sos_b)

        st.divider()
        _render_common_opponents(team_a, team_b)

        st.divider()
        _render_predicted_matchup(metrics_a, metrics_b, sos_a, sos_b)

        st.divider()
        _render_comparison_charts(team_a, team_b, metrics_a, metrics_b)


def _render_side_by_side(
    team_a: TeamSeason,
    team_b: TeamSeason,
    metrics_a: TeamMetrics,
    metrics_b: TeamMetrics,
    sos_a,
    sos_b,
) -> None:
    """Render side-by-side metric comparison."""
    st.markdown("### 📊 Performance Comparison")

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(f"#### {team_a.team_name}")
        grade_a = (
            team_a.assigned_grade.value
            if hasattr(team_a.assigned_grade, "value")
            else str(team_a.assigned_grade)
            if team_a.assigned_grade
            else "N/A"
        )
        st.markdown(f"**Grade:** {grade_a}")
        st.markdown(f"**Club:** {team_a.club_name}")

    with col2:
        st.markdown("#### vs")

    with col3:
        st.markdown(f"#### {team_b.team_name}")
        grade_b = (
            team_b.assigned_grade.value
            if hasattr(team_b.assigned_grade, "value")
            else str(team_b.assigned_grade)
            if team_b.assigned_grade
            else "N/A"
        )
        st.markdown(f"**Grade:** {grade_b}")
        st.markdown(f"**Club:** {team_b.club_name}")

    # Metrics comparison table
    metrics_data = [
        {
            "Metric": "Record",
            team_a.team_name: f"{metrics_a.wins}W - {metrics_a.losses}L",
            team_b.team_name: f"{metrics_b.wins}W - {metrics_b.losses}L",
            "Better": _get_better(
                metrics_a.wins / max(metrics_a.games_played, 1),
                metrics_b.wins / max(metrics_b.games_played, 1),
                team_a.team_name,
                team_b.team_name,
            ),
        },
        {
            "Metric": "Win Rate",
            team_a.team_name: f"{metrics_a.win_rate:.1f}%",
            team_b.team_name: f"{metrics_b.win_rate:.1f}%",
            "Better": _get_better(
                metrics_a.win_rate, metrics_b.win_rate, team_a.team_name, team_b.team_name
            ),
        },
        {
            "Metric": "Avg Margin",
            team_a.team_name: f"{metrics_a.avg_margin:+.1f}",
            team_b.team_name: f"{metrics_b.avg_margin:+.1f}",
            "Better": _get_better(
                metrics_a.avg_margin, metrics_b.avg_margin, team_a.team_name, team_b.team_name
            ),
        },
        {
            "Metric": "Blowout Wins",
            team_a.team_name: str(metrics_a.blowout_wins),
            team_b.team_name: str(metrics_b.blowout_wins),
            "Better": _get_better(
                metrics_a.blowout_wins, metrics_b.blowout_wins, team_a.team_name, team_b.team_name
            ),
        },
        {
            "Metric": "Blowout Losses",
            team_a.team_name: str(metrics_a.blowout_losses),
            team_b.team_name: str(metrics_b.blowout_losses),
            "Better": _get_better(
                metrics_a.blowout_losses,
                metrics_b.blowout_losses,
                team_a.team_name,
                team_b.team_name,
                lower_is_better=True,
            ),
        },
        {
            "Metric": "Points For",
            team_a.team_name: str(metrics_a.points_for),
            team_b.team_name: str(metrics_b.points_for),
            "Better": _get_better(
                metrics_a.points_for, metrics_b.points_for, team_a.team_name, team_b.team_name
            ),
        },
        {
            "Metric": "Points Against",
            team_a.team_name: str(metrics_a.points_against),
            team_b.team_name: str(metrics_b.points_against),
            "Better": _get_better(
                metrics_a.points_against,
                metrics_b.points_against,
                team_a.team_name,
                team_b.team_name,
                lower_is_better=True,
            ),
        },
        {
            "Metric": "SoS Score",
            team_a.team_name: f"{sos_a.sos_score:.1f}",
            team_b.team_name: f"{sos_b.sos_score:.1f}",
            "Better": _get_better(
                sos_a.sos_score, sos_b.sos_score, team_a.team_name, team_b.team_name
            ),
        },
        {
            "Metric": "Schedule Difficulty",
            team_a.team_name: sos_a.schedule_difficulty,
            team_b.team_name: sos_b.schedule_difficulty,
            "Better": "-",
        },
    ]

    df = pd.DataFrame(metrics_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _get_better(
    val_a: float,
    val_b: float,
    name_a: str,
    name_b: str,
    lower_is_better: bool = False,
) -> str:
    """Determine which team has the better value."""
    if val_a == val_b:
        return "Tie"
    if lower_is_better:
        return name_a if val_a < val_b else name_b
    return name_a if val_a > val_b else name_b


def _render_common_opponents(team_a: TeamSeason, team_b: TeamSeason) -> None:
    """Render common opponent analysis."""
    st.markdown("### 🎯 Common Opponent Analysis")

    def _get_result_str(result) -> str:
        return result.value if hasattr(result, "value") else str(result)

    # Find common opponents
    opponents_a = {g.opponent_name: g for g in team_a.games if _get_result_str(g.result) != "DNP"}
    opponents_b = {g.opponent_name: g for g in team_b.games if _get_result_str(g.result) != "DNP"}

    common = set(opponents_a.keys()) & set(opponents_b.keys())

    if not common:
        st.info("No common opponents found between these teams.")
        return

    st.markdown(f"**{len(common)} common opponents found**")

    common_data = []
    total_margin_diff = 0

    for opp in sorted(common):
        game_a = opponents_a[opp]
        game_b = opponents_b[opp]

        margin_diff = game_a.margin - game_b.margin

        common_data.append(
            {
                "Opponent": opp,
                f"{team_a.team_name} Result": f"{'W' if _get_result_str(game_a.result) == 'Won' else 'L'} ({game_a.margin:+d})",
                f"{team_b.team_name} Result": f"{'W' if _get_result_str(game_b.result) == 'Won' else 'L'} ({game_b.margin:+d})",
                "Margin Diff": f"{margin_diff:+d}",
                "Advantage": team_a.team_name
                if margin_diff > 0
                else (team_b.team_name if margin_diff < 0 else "Even"),
            }
        )
        total_margin_diff += margin_diff

    df = pd.DataFrame(common_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Summary
    if total_margin_diff > 0:
        st.success(
            f"Based on common opponents, **{team_a.team_name}** has a **+{total_margin_diff}** point advantage"
        )
    elif total_margin_diff < 0:
        st.success(
            f"Based on common opponents, **{team_b.team_name}** has a **+{abs(total_margin_diff)}** point advantage"
        )
    else:
        st.info("Teams performed equally against common opponents")


def _render_predicted_matchup(
    metrics_a: TeamMetrics,
    metrics_b: TeamMetrics,
    sos_a,
    sos_b,
) -> None:
    """Render predicted matchup outcome."""
    st.markdown("### 🔮 Predicted Matchup")

    # Calculate prediction based on multiple factors
    # 1. Win rate difference
    win_rate_factor = (metrics_a.win_rate - metrics_b.win_rate) / 100

    # 2. Average margin difference
    margin_factor = (metrics_a.avg_margin - metrics_b.avg_margin) / 50

    # 3. SoS-adjusted factor (harder schedule = bonus)
    sos_factor = (sos_a.sos_score - sos_b.sos_score) / 100

    # 4. Blowout ratio
    blowout_a = metrics_a.blowout_wins - metrics_a.blowout_losses
    blowout_b = metrics_b.blowout_wins - metrics_b.blowout_losses
    blowout_factor = (blowout_a - blowout_b) / 10

    # Weighted combination
    raw_score = (
        win_rate_factor * 0.3 + margin_factor * 0.35 + sos_factor * 0.15 + blowout_factor * 0.2
    )

    # Convert to probability (sigmoid)
    import math

    probability_a = 1 / (1 + math.exp(-raw_score * 3))
    probability_b = 1 - probability_a

    # Predicted margin
    predicted_margin = int(raw_score * 15)

    # Display prediction
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label=f"{metrics_a.team_name} Win Probability",
            value=f"{probability_a * 100:.1f}%",
        )

    with col2:
        if predicted_margin > 0:
            st.metric(
                label="Predicted Winner",
                value=metrics_a.team_name,
                delta=f"+{abs(predicted_margin)} pts",
            )
        elif predicted_margin < 0:
            st.metric(
                label="Predicted Winner",
                value=metrics_b.team_name,
                delta=f"+{abs(predicted_margin)} pts",
            )
        else:
            st.metric(
                label="Predicted Outcome",
                value="Toss-up",
            )

    with col3:
        st.metric(
            label=f"{metrics_b.team_name} Win Probability",
            value=f"{probability_b * 100:.1f}%",
        )

    # Confidence level
    confidence_diff = abs(probability_a - probability_b)
    if confidence_diff > 0.5:
        confidence = "HIGH"
        conf_color = SUCCESS_GREEN
    elif confidence_diff > 0.25:
        confidence = "MEDIUM"
        conf_color = WARNING_YELLOW
    else:
        confidence = "LOW"
        conf_color = ERROR_RED

    st.markdown(
        f"**Prediction Confidence:** <span style='color:{conf_color}'>{confidence}</span>",
        unsafe_allow_html=True,
    )


def _render_comparison_charts(
    team_a: TeamSeason,
    team_b: TeamSeason,
    metrics_a: TeamMetrics,
    metrics_b: TeamMetrics,
) -> None:
    """Render comparison visualizations."""
    st.markdown("### 📈 Visual Comparison")

    tab1, tab2 = st.tabs(["Radar Chart", "Margin Timeline"])

    with tab1:
        _render_radar_chart(team_a, team_b, metrics_a, metrics_b)

    with tab2:
        _render_margin_timeline(team_a, team_b)


def _render_radar_chart(
    team_a: TeamSeason,
    team_b: TeamSeason,
    metrics_a: TeamMetrics,
    metrics_b: TeamMetrics,
) -> None:
    """Render radar chart comparing key metrics."""
    categories = ["Win Rate", "Avg Margin", "Blowout Wins", "Close Win%", "Offensive Rating"]

    # Normalize values to 0-100 scale
    def normalize_margin(val: float) -> float:
        # Map -30 to +30 margin to 0-100 scale
        return max(0, min(100, (val + 30) * (100 / 60)))

    def close_win_pct(m: TeamMetrics) -> float:
        close_total = m.close_wins + m.close_losses
        return (m.close_wins / close_total * 100) if close_total > 0 else 50

    def offensive_rating(m: TeamMetrics) -> float:
        # Points per game normalized
        if m.games_played == 0:
            return 50
        ppg = m.points_for / m.games_played
        return min(100, ppg * 2)

    values_a = [
        metrics_a.win_rate,
        normalize_margin(metrics_a.avg_margin),
        min(100, metrics_a.blowout_wins * 20),
        close_win_pct(metrics_a),
        offensive_rating(metrics_a),
    ]

    values_b = [
        metrics_b.win_rate,
        normalize_margin(metrics_b.avg_margin),
        min(100, metrics_b.blowout_wins * 20),
        close_win_pct(metrics_b),
        offensive_rating(metrics_b),
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values_a + [values_a[0]],  # Close the polygon
            theta=categories + [categories[0]],
            fill="toself",
            name=team_a.team_name,
            line_color=FORD_BLUE,
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=values_b + [values_b[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=team_b.team_name,
            line_color=ACCENT_BLUE,
        )
    )

    fig.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        showlegend=True,
        title="Performance Profile Comparison",
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_margin_timeline(team_a: TeamSeason, team_b: TeamSeason) -> None:
    """Render margin over time for both teams."""
    data = []

    def _get_result_str(result) -> str:
        return result.value if hasattr(result, "value") else str(result)

    for game in team_a.games:
        if _get_result_str(game.result) != "DNP":
            data.append(
                {
                    "Team": team_a.team_name,
                    "Round": game.round_num,
                    "Margin": game.margin,
                    "Opponent": game.opponent_name,
                }
            )

    for game in team_b.games:
        if _get_result_str(game.result) != "DNP":
            data.append(
                {
                    "Team": team_b.team_name,
                    "Round": game.round_num,
                    "Margin": game.margin,
                    "Opponent": game.opponent_name,
                }
            )

    if not data:
        st.info("No game data available")
        return

    df = pd.DataFrame(data)

    fig = go.Figure()

    for team_name, color in [(team_a.team_name, FORD_BLUE), (team_b.team_name, ACCENT_BLUE)]:
        team_df = df[df["Team"] == team_name].sort_values("Round")
        fig.add_trace(
            go.Scatter(
                x=team_df["Round"],
                y=team_df["Margin"],
                mode="lines+markers",
                name=team_name,
                line={"color": color},
                hovertemplate="%{text}<br>Round %{x}<br>Margin: %{y:+d}<extra></extra>",
                text=team_df["Opponent"],
            )
        )

    # Add zero line and blowout thresholds
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_hline(y=20, line_dash="dot", line_color=SUCCESS_GREEN, opacity=0.5)
    fig.add_hline(y=-20, line_dash="dot", line_color=ERROR_RED, opacity=0.5)

    fig.update_layout(
        title="Margin Progression by Round",
        xaxis_title="Round",
        yaxis_title="Point Margin",
        hovermode="x unified",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)
