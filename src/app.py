"""
Basketball Grader Wizard — Main Streamlit Application

Professional dashboard for basketball team grading analysis.
Ingests DVBA Club Grading Book Excel files and generates
grade movement recommendations with supporting evidence.

Run with: streamlit run src/app.py
"""

import sys
from pathlib import Path

# ruff: noqa: E402
import pandas as pd
import streamlit as st

# Ensure project root is on path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings

# Import grading components
from src.cache import cache_team_data, invalidate_cache
from src.data.parser import GradingBookParser

# Import export functions
from src.exports.excel import export_recommendations_excel, export_standings_excel
from src.grading.overrides import OverrideManager
from src.grading.recommender import RecommendationEngine
from src.models.game_result import TeamSeason
from src.models.recommendation import Recommendation
from src.styles import apply_page_config, ford_header
from src.ui.charts import (
    create_blowout_frequency_chart,
    create_margin_trend_chart,
    create_win_loss_chart,
)

# Import UI components
from src.ui.comparison_view import render_comparison_view
from src.ui.filters import FilterState, apply_round_filter, render_sidebar_filters
from src.ui.historical_view import render_historical_view
from src.ui.matchups_view import render_matchups_panel
from src.ui.metrics_cards import render_kpi_cards
from src.ui.power_rating_view import render_power_rating_view
from src.ui.recommendations_view import render_recommendations_panel
from src.ui.sos_view import render_sos_analysis
from src.ui.standings_view import render_standings_table
from src.ui.team_deep_dive import render_team_deep_dive

# === Session State Initialization ===


def init_session_state() -> None:
    """Initialize all session state keys with defaults."""
    defaults = {
        "data_loaded": False,
        "teams": [],
        "recommendations": [],
        "filter_state": FilterState(),
        "current_season": "Autumn 2026",
        "max_round": 5,
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# === Data Loading ===


@st.cache_data(show_spinner="Parsing grading book...")
def parse_grading_book(file_path: Path) -> list[TeamSeason]:
    """Parse a Club Grading Book Excel file.

    Args:
        file_path: Path to the Excel file.

    Returns:
        List of TeamSeason objects.
    """
    parser = GradingBookParser(file_path)
    return parser.parse_all()


@st.cache_data(show_spinner="Generating recommendations...")
def generate_recommendations(_teams: list[TeamSeason]) -> list[Recommendation]:
    """Generate recommendations for all teams.

    Args:
        _teams: List of teams to analyze.

    Returns:
        List of recommendations.
    """
    engine = RecommendationEngine()
    return engine.generate_all_recommendations(_teams)


def should_process_upload(uploaded_file: object | None, process_clicked: bool) -> bool:
    """Return whether upload processing should run on this rerun.

    Args:
        uploaded_file: Uploaded file object from Streamlit uploader.
        process_clicked: Whether the process button was clicked this rerun.

    Returns:
        True only when both a file is present and user explicitly clicked process.
    """
    return uploaded_file is not None and process_clicked


# === Page Components ===


def render_upload_tab() -> None:
    """Render the data upload tab."""
    st.markdown("### 📤 Upload Club Grading Book")

    st.markdown(
        """
        Upload the DVBA Club Grading Book Excel file to analyze team performance
        and generate grade recommendations.

        **Supported format:** `.xlsx` files from the DVBA grading system
        """
    )

    settings = get_settings()

    uploaded_file = st.file_uploader(
        "Choose Excel file",
        type=["xlsx", "xls"],
        help="Upload the Club Grading Book Excel file",
        key="grading_book_upload",
    )

    process_upload = st.button(
        "Process Uploaded File",
        type="primary",
        disabled=uploaded_file is None,
        help="Parse and analyze the selected grading book",
        key="process_grading_book",
    )

    if should_process_upload(uploaded_file, process_upload):
        # Save uploaded file to a unique temp path to avoid PermissionError
        # when the original file is still open in another program (e.g. Excel)
        import tempfile

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(uploaded_file.name).suffix
        fd, tmp = tempfile.mkstemp(suffix=suffix, dir=settings.data_dir)
        temp_path = Path(tmp)
        try:
            with open(fd, "wb") as f:
                f.write(uploaded_file.getvalue())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        with st.spinner("Processing grading book..."):
            try:
                teams = parse_grading_book(temp_path)

                if teams:
                    # Detect max round from data
                    max_round = max(max((g.round_num for g in t.games), default=1) for t in teams)

                    st.session_state.teams = teams
                    st.session_state.max_round = max_round
                    st.session_state.data_loaded = True

                    # Pre-compute and cache metrics/SoS for performance
                    cache_team_data(teams)

                    # Generate recommendations
                    st.session_state.recommendations = generate_recommendations(teams)

                    st.success(
                        f"✅ Successfully loaded {len(teams)} teams across {max_round} rounds"
                    )
                    st.rerun()
                else:
                    st.error("No teams found in the uploaded file.")

            except Exception as e:
                st.error(f"❌ Error processing file: {e}")
                st.exception(e)


def _show_upload_preview(teams: list[TeamSeason]) -> None:
    """Show a preview of uploaded data.

    Args:
        teams: Parsed teams.
    """
    st.markdown("#### Preview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Teams", len(teams))

    with col2:
        total_games = sum(t.games_played for t in teams)
        st.metric("Total Games", total_games)

    with col3:
        age_groups = len(set(t.age_group for t in teams))
        st.metric("Age Groups", age_groups)

    with col4:
        divisions = len(set(t.division for t in teams))
        st.metric("Divisions", divisions)

    # Sheet summary
    with st.expander("📋 Sheet Summary"):
        sheets = {}
        for team in teams:
            key = team.sheet_name
            if key not in sheets:
                sheets[key] = {"teams": 0, "games": 0}
            sheets[key]["teams"] += 1
            sheets[key]["games"] += team.games_played

        df = pd.DataFrame(
            [
                {"Sheet": k, "Teams": v["teams"], "Games": v["games"]}
                for k, v in sorted(sheets.items())
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)


def render_standings_tab(
    teams: list[TeamSeason],
    recommendations: list[Recommendation],
) -> None:
    """Render the standings tab.

    Args:
        teams: Filtered teams.
        recommendations: All recommendations.
    """
    rec_dict = {r.team_name: r for r in recommendations}
    render_standings_table(teams, rec_dict)


def render_analysis_tab(teams: list[TeamSeason]) -> None:
    """Render the analysis tab with charts.

    Args:
        teams: Filtered teams.
    """
    st.markdown("### 📈 Performance Analysis")

    if not teams:
        st.info("No teams to display. Adjust filters or upload data.")
        return

    # Chart type selector
    chart_type = st.selectbox(
        "Select Chart",
        options=[
            "Win/Loss Breakdown",
            "Margin Trends",
            "Blowout Frequency by Division",
            "Blowout Frequency by Grade",
        ],
    )

    if chart_type == "Win/Loss Breakdown":
        fig = create_win_loss_chart(teams[:20])  # Limit for readability
        st.plotly_chart(fig, width="stretch")

    elif chart_type == "Margin Trends":
        selected_teams = st.multiselect(
            "Select teams to compare",
            options=[t.team_name for t in teams],
            default=[teams[0].team_name] if teams else [],
            max_selections=5,
        )
        if selected_teams:
            display_teams = [t for t in teams if t.team_name in selected_teams]
            fig = create_margin_trend_chart(display_teams, selected_teams)
            st.plotly_chart(fig, width="stretch")

    elif chart_type == "Blowout Frequency by Division":
        fig = create_blowout_frequency_chart(teams, group_by="division")
        st.plotly_chart(fig, width="stretch")

    elif chart_type == "Blowout Frequency by Grade":
        fig = create_blowout_frequency_chart(teams, group_by="grade")
        st.plotly_chart(fig, width="stretch")


def render_exports_tab(
    teams: list[TeamSeason],
    recommendations: list[Recommendation],
) -> None:
    """Render exports tab.

    Args:
        teams: Current teams.
        recommendations: Current recommendations.
    """
    st.markdown("### 📥 Export Reports")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Standings Export")
        st.markdown("Export current standings with all metrics to Excel.")

        if st.button("Generate Standings Excel", type="primary"):
            rec_dict = {r.team_name: r for r in recommendations}
            excel_bytes = export_standings_excel(teams, rec_dict)

            st.download_button(
                label="📥 Download Standings",
                data=excel_bytes,
                file_name="standings_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with col2:
        st.markdown("#### Recommendations Export")
        st.markdown("Export all recommendations with evidence to Excel.")

        if st.button("Generate Recommendations Excel", type="primary"):
            excel_bytes = export_recommendations_excel(recommendations)

            st.download_button(
                label="📥 Download Recommendations",
                data=excel_bytes,
                file_name="recommendations_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.divider()

    # Audit log export
    st.markdown("#### Audit Log")
    settings = get_settings()
    override_manager = OverrideManager(settings.data_dir)
    overrides = override_manager.get_all_overrides()

    if overrides:
        st.write(f"Total overrides: {len(overrides)}")
        if st.button("Export Audit Log"):
            from src.exports.excel import export_audit_log_excel

            excel_bytes = export_audit_log_excel(overrides)
            st.download_button(
                label="📥 Download Audit Log",
                data=excel_bytes,
                file_name="audit_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No audit records yet.")


def render_main_content() -> None:
    """Render the main content area."""
    settings = get_settings()

    ford_header(
        title="Basketball Grader Wizard",
        subtitle="DVBA Team Grading Analysis Dashboard",
    )

    # Check if data is loaded
    if not st.session_state.data_loaded:
        render_upload_tab()
        return

    # Get filtered teams
    teams = st.session_state.teams
    recommendations = st.session_state.recommendations

    # Auto-recover: recommendations empty but data is loaded (e.g. after a crash during upload)
    if teams and not recommendations:
        st.session_state.recommendations = generate_recommendations(teams)
        recommendations = st.session_state.recommendations

    # Apply filters from sidebar
    filter_state = st.session_state.get("filter_state", FilterState())

    # Filter teams
    filtered_teams = [t for t in teams if filter_state.matches_team(t)]

    # Apply round filter
    filtered_teams = apply_round_filter(filtered_teams, filter_state.selected_round)

    # Filter recommendations to match filtered teams
    filtered_team_names = {t.team_name for t in filtered_teams}
    filtered_recs = [r for r in recommendations if r.team_name in filtered_team_names]

    # KPI Cards
    override_manager = OverrideManager(settings.data_dir)
    overrides_count = len(override_manager.get_overrides_by_season(filter_state.season))
    render_kpi_cards(filtered_teams, filtered_recs, overrides_count)

    st.divider()

    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
        [
            "📊 Standings",
            "📈 SoS Analysis",
            "⚡ Power Ratings",
            "📋 Recommendations",
            "📅 Matchups",
            "🔍 Team Deep Dive",
            "🆚 Compare Teams",
            "📜 Historical",
            "📉 Charts",
            "📤 Upload",
            "📥 Exports",
        ]
    )

    with tab1:
        render_standings_tab(filtered_teams, filtered_recs)

    with tab2:
        render_sos_analysis(filtered_teams)

    with tab3:
        render_power_rating_view(filtered_teams)

    with tab4:
        render_recommendations_panel(filtered_recs, override_manager, filter_state.season)

    with tab5:
        render_matchups_panel(filtered_teams, filter_state.season, st.session_state.max_round)

    with tab6:
        rec_dict = {r.team_name: r for r in filtered_recs}
        render_team_deep_dive(filtered_teams, rec_dict)

    with tab7:
        render_comparison_view(filtered_teams)

    with tab8:
        render_historical_view(filtered_teams, filter_state.season)

    with tab9:
        render_analysis_tab(filtered_teams)

    with tab10:
        render_upload_tab()

    with tab11:
        render_exports_tab(filtered_teams, filtered_recs)


def render_sidebar() -> None:
    """Render the sidebar with filters."""
    # Display logo at top of sidebar
    logo_path = Path(__file__).parent.parent / "assets" / "Specter_Basketball_Management_2.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width="stretch")

    if st.session_state.data_loaded:
        teams = st.session_state.teams
        max_round = st.session_state.max_round
        render_sidebar_filters(teams, max_round)

        # Add clear data button
        st.sidebar.divider()
        if st.sidebar.button("🗑️ Clear Data", type="secondary"):
            invalidate_cache()
            st.session_state.data_loaded = False
            st.session_state.teams = []
            st.session_state.recommendations = []
            st.rerun()
    else:
        st.sidebar.markdown("### 🏀 Basketball Grader Wizard")
        st.sidebar.info("Upload a grading book to get started.")


# === Main Application ===


def main() -> None:
    """Main application entry point."""
    # Page config and theme (must be first Streamlit call)
    apply_page_config(
        page_title="Basketball Grader Wizard",
        page_icon="🏀",
        layout="wide",
    )

    # Initialize session state
    init_session_state()

    # Render components
    render_sidebar()
    render_main_content()


if __name__ == "__main__":
    main()
