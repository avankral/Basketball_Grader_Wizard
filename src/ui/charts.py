"""Plotly chart components for the dashboard.

Provides visualizations for:
- Margin trends over rounds
- Grade distribution heatmaps
- Strength of Schedule comparisons
- Win/loss analysis
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.grading.grades import GRADE_ORDER
from src.grading.metrics import TeamMetrics
from src.grading.strength_of_schedule import StrengthOfSchedule
from src.models.game_result import ResultType, TeamSeason

# Shared color palette
PRIMARY_BLUE = "#00095B"
ACCENT_BLUE = "#1C69D4"
LIGHT_BLUE = "#E8F1FC"
SUCCESS_GREEN = "#198754"
WARNING_YELLOW = "#FFC107"
ERROR_RED = "#DC3545"


def create_margin_trend_chart(
    teams: list[TeamSeason],
    selected_teams: list[str] | None = None,
) -> go.Figure:
    """Create a line chart showing margin trends over rounds.

    Args:
        teams: Teams to include in chart.
        selected_teams: Optional list of team names to highlight.

    Returns:
        Plotly Figure object.
    """
    # Prepare data
    data = []
    for team in teams:
        for game in team.games:
            if game.result != ResultType.DNP:
                data.append(
                    {
                        "Team": team.team_name,
                        "Round": game.round_num,
                        "Margin": game.margin,
                        "Opponent": game.opponent_name,
                        "Result": game.result.value if hasattr(game.result, "value") else str(game.result),
                    }
                )

    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No game data available", showarrow=False)
        return fig

    df = pd.DataFrame(data)

    # Create figure
    fig = px.line(
        df,
        x="Round",
        y="Margin",
        color="Team",
        markers=True,
        hover_data=["Opponent", "Result"],
        title="Margin Trend by Round",
    )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    # Add blowout threshold lines
    fig.add_hline(y=20, line_dash="dot", line_color=SUCCESS_GREEN, annotation_text="Blowout Win")
    fig.add_hline(y=-20, line_dash="dot", line_color=ERROR_RED, annotation_text="Blowout Loss")

    # Highlight selected teams if provided
    if selected_teams:
        for trace in fig.data:
            if trace.name not in selected_teams:
                trace.opacity = 0.3

    fig.update_layout(
        xaxis_title="Round",
        yaxis_title="Point Margin",
        legend_title="Team",
        hovermode="x unified",
        template="plotly_white",
    )

    return fig


def create_grade_distribution_chart(
    sos_list: list[StrengthOfSchedule],
) -> go.Figure:
    """Create a heatmap showing opponent grade distribution.

    Args:
        sos_list: SoS analysis for multiple teams.

    Returns:
        Plotly Figure object with heatmap.
    """
    # Build data matrix
    team_names = [sos.team_name for sos in sos_list]
    grade_values = [g.value for g in GRADE_ORDER]

    matrix = []
    for sos in sos_list:
        row = [sos.grade_distribution.get(g, 0) for g in grade_values]
        matrix.append(row)

    if not matrix:
        fig = go.Figure()
        fig.add_annotation(text="No SoS data available", showarrow=False)
        return fig

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=grade_values,
            y=team_names,
            colorscale=[[0, LIGHT_BLUE], [0.5, ACCENT_BLUE], [1, PRIMARY_BLUE]],
            text=[[f"{v}%" for v in row] for row in matrix],
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="Team: %{y}<br>Opponent Grade: %{x}<br>Games: %{z}%<extra></extra>",
        )
    )

    fig.update_layout(
        title="Opponent Grade Distribution (%)",
        xaxis_title="Opponent Grade",
        yaxis_title="Team",
        template="plotly_white",
    )

    return fig


def create_sos_distribution_chart(
    teams: list[TeamSeason],
    metrics_list: list[TeamMetrics],
    sos_list: list[StrengthOfSchedule],
) -> go.Figure:
    """Create a scatter plot of SoS score vs win rate.

    Args:
        teams: Team data.
        metrics_list: Metrics for each team.
        sos_list: SoS for each team.

    Returns:
        Plotly Figure object.
    """
    # Prepare data
    data = []
    for team, metrics, sos in zip(teams, metrics_list, sos_list, strict=False):
        data.append(
            {
                "Team": team.team_name,
                "Grade": team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A",
                "SoS Score": sos.sos_score,
                "Win Rate": metrics.win_rate,
                "Games Played": metrics.games_played,
                "Blowout Wins": metrics.blowout_wins,
                "Blowout Losses": metrics.blowout_losses,
            }
        )

    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False)
        return fig

    df = pd.DataFrame(data)

    fig = px.scatter(
        df,
        x="SoS Score",
        y="Win Rate",
        color="Grade",
        size="Games Played",
        hover_data=["Team", "Blowout Wins", "Blowout Losses"],
        title="Strength of Schedule vs Win Rate",
        color_discrete_sequence=[PRIMARY_BLUE, ACCENT_BLUE, SUCCESS_GREEN, WARNING_YELLOW, ERROR_RED],
    )

    # Add reference lines
    fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% Win Rate")
    fig.add_vline(x=50, line_dash="dash", line_color="gray", annotation_text="Average SoS")

    fig.update_layout(
        xaxis_title="Strength of Schedule Score (higher = harder)",
        yaxis_title="Win Rate (%)",
        template="plotly_white",
    )

    return fig


def create_win_loss_chart(teams: list[TeamSeason]) -> go.Figure:
    """Create a stacked bar chart of wins/losses by team.

    Args:
        teams: Teams to display.

    Returns:
        Plotly Figure object.
    """
    # Prepare data
    data = []
    for team in teams:
        wins = sum(1 for g in team.games if g.result == ResultType.WON)
        losses = sum(1 for g in team.games if g.result == ResultType.LOST)
        blowout_wins = sum(1 for g in team.games if g.result == ResultType.WON and g.margin >= 20)
        blowout_losses = sum(
            1 for g in team.games if g.result == ResultType.LOST and g.margin <= -20
        )

        data.append(
            {
                "Team": team.team_name,
                "Grade": team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A",
                "Close Wins": wins - blowout_wins,
                "Blowout Wins": blowout_wins,
                "Close Losses": losses - blowout_losses,
                "Blowout Losses": blowout_losses,
            }
        )

    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No game data available", showarrow=False)
        return fig

    df = pd.DataFrame(data)
    df = df.sort_values("Blowout Wins", ascending=False)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Blowout Wins",
            x=df["Team"],
            y=df["Blowout Wins"],
            marker_color=PRIMARY_BLUE,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Close Wins",
            x=df["Team"],
            y=df["Close Wins"],
            marker_color=ACCENT_BLUE,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Close Losses",
            x=df["Team"],
            y=-df["Close Losses"],
            marker_color=WARNING_YELLOW,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Blowout Losses",
            x=df["Team"],
            y=-df["Blowout Losses"],
            marker_color=ERROR_RED,
        )
    )

    fig.update_layout(
        title="Win/Loss Breakdown by Team",
        xaxis_title="Team",
        yaxis_title="Games",
        barmode="relative",
        template="plotly_white",
        xaxis_tickangle=-45,
    )

    return fig


def create_blowout_frequency_chart(
    teams: list[TeamSeason],
    group_by: str = "division",
) -> go.Figure:
    """Create a bar chart showing blowout frequency by grouping.

    Args:
        teams: Teams to analyze.
        group_by: How to group teams ("division", "grade", "age_group").

    Returns:
        Plotly Figure object.
    """
    # Aggregate data by grouping
    data = []
    for team in teams:
        blowout_wins = sum(1 for g in team.games if g.result == ResultType.WON and g.margin >= 20)
        blowout_losses = sum(
            1 for g in team.games if g.result == ResultType.LOST and g.margin <= -20
        )

        if group_by == "division":
            key = f"Division {team.division}"
        elif group_by == "grade":
            key = team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A"
        else:
            key = f"U{team.age_group}"

        data.append(
            {
                "Group": key,
                "Blowout Wins": blowout_wins,
                "Blowout Losses": blowout_losses,
            }
        )

    df = pd.DataFrame(data)
    grouped = df.groupby("Group").sum().reset_index()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Blowout Wins",
            x=grouped["Group"],
            y=grouped["Blowout Wins"],
            marker_color=SUCCESS_GREEN,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Blowout Losses",
            x=grouped["Group"],
            y=grouped["Blowout Losses"],
            marker_color=ERROR_RED,
        )
    )

    fig.update_layout(
        title=f"Blowout Frequency by {group_by.title()}",
        xaxis_title=group_by.title(),
        yaxis_title="Number of Blowouts",
        barmode="group",
        template="plotly_white",
    )

    return fig
