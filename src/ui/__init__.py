"""UI components module.

Contains reusable Streamlit components for the dashboard:
- Sidebar filters
- Metric cards
- Charts and visualizations
- Data views
- Matchup recommendations
"""

from src.ui.charts import (
    create_grade_distribution_chart,
    create_margin_trend_chart,
    create_sos_distribution_chart,
    create_win_loss_chart,
)
from src.ui.filters import FilterState, render_sidebar_filters
from src.ui.matchups_view import render_matchups_panel
from src.ui.metrics_cards import render_kpi_cards, render_team_summary_card
from src.ui.recommendations_view import render_recommendations_panel
from src.ui.sos_view import render_sos_analysis
from src.ui.standings_view import render_standings_table
from src.ui.team_deep_dive import render_team_deep_dive

__all__ = [
    "FilterState",
    "render_sidebar_filters",
    "render_kpi_cards",
    "render_team_summary_card",
    "create_margin_trend_chart",
    "create_grade_distribution_chart",
    "create_sos_distribution_chart",
    "create_win_loss_chart",
    "render_standings_table",
    "render_sos_analysis",
    "render_recommendations_panel",
    "render_matchups_panel",
    "render_team_deep_dive",
]
