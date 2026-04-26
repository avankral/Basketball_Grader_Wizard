"""Matchups panel component for round scheduling optimizer.

Displays:
- Round analysis with variance metrics
- High variance games identified
- Recommended matchups with approval workflow
- Historical learning statistics
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import get_settings
from src.data.matchup_storage import MatchupStorage
from src.grading.matchup_learner import MatchupLearner
from src.grading.matchup_optimizer import MatchupOptimizer
from src.grading.round_analyzer import RoundAnalyzer
from src.models.game_result import TeamSeason
from src.models.matchup import (
    MatchupConfidence,
    MatchupRecommendation,
    MatchupStatus,
    MatchupType,
    RoundAnalysis,
)


def _init_matchup_session_state() -> None:
    """Initialize matchup-related session state."""
    defaults = {
        "matchup_round_analysis": None,
        "matchup_recommendations": [],
        "variance_threshold_override": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def render_matchups_panel(
    teams: list[TeamSeason],
    season: str = "Autumn 2026",
    max_round: int = 5,
) -> None:
    """Render the matchups panel.

    Args:
        teams: List of all teams.
        season: Current season identifier.
        max_round: Maximum round number in data.
    """
    _init_matchup_session_state()

    if not teams:
        st.info("No teams available. Upload data to generate matchups.")
        return

    st.subheader("📅 Round Scheduling Optimizer")
    st.markdown(
        "Analyze round results and generate optimized matchups to reduce variance within grades."
    )

    settings = get_settings()
    storage = MatchupStorage(settings.data_dir)
    learner = MatchupLearner(storage)

    # Configuration section
    with st.expander("⚙️ Configuration", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            variance_threshold = st.slider(
                "Variance Threshold (%)",
                min_value=20.0,
                max_value=80.0,
                value=settings.variance_threshold_percent,
                step=5.0,
                help="Games with variance above this threshold are flagged as high-variance",
            )
            st.session_state.variance_threshold_override = variance_threshold

        with col2:
            cross_grade_trigger = st.slider(
                "Cross-Grade Trigger (%)",
                min_value=25.0,
                max_value=70.0,
                value=settings.cross_grade_margin_trigger,
                step=5.0,
                help="Margin that triggers cross-grade consideration",
            )

    # Historical learning stats
    _render_learning_stats(learner, season)

    st.divider()

    # Round selection
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        analyze_round = st.selectbox(
            "Select Round to Analyze",
            options=list(range(1, max_round + 1)),
            index=max(0, max_round - 1),
            format_func=lambda x: f"Round {x}",
        )
    with col2:
        next_round = analyze_round + 1
        st.markdown(f"**Generating matchups for:** Round {next_round}")
    with col3:
        analyze_clicked = st.button("🔍 Analyze", type="primary")

    # Show team summary
    with st.expander("📋 Teams Summary", expanded=False):
        from collections import Counter

        grade_counts = Counter(
            t.assigned_grade.value
            if hasattr(t.assigned_grade, "value") and t.assigned_grade
            else str(t.assigned_grade)
            if t.assigned_grade
            else "Unknown"
            for t in teams
        )
        st.write(f"**Total teams:** {len(teams)}")
        st.write("**By grade:**", dict(grade_counts))

    # Run analysis if requested
    if analyze_clicked:
        with st.spinner("Analyzing round..."):
            try:
                analyzer = RoundAnalyzer(
                    variance_threshold=st.session_state.variance_threshold_override
                )
                analysis = analyzer.analyze_round(analyze_round, teams)
                st.session_state.matchup_round_analysis = analysis

                # Generate matchups for next round
                optimizer = MatchupOptimizer(
                    variance_threshold=st.session_state.variance_threshold_override,
                    cross_grade_trigger=cross_grade_trigger,
                )
                matchups = optimizer.generate_matchups(next_round, teams, analysis)
                st.session_state.matchup_recommendations = matchups
                st.success(f"Generated {len(matchups)} matchup recommendations")
            except Exception as e:
                st.error(f"Error during analysis: {e}")
                import traceback

                st.code(traceback.format_exc())

    # Display analysis results
    analysis: RoundAnalysis | None = st.session_state.matchup_round_analysis
    matchups: list[MatchupRecommendation] = st.session_state.matchup_recommendations

    if analysis:
        _render_round_analysis(analysis)
        st.divider()

        if matchups:
            _render_matchup_recommendations(matchups, storage, season)
        else:
            st.info(
                f"No matchups generated for Round {analysis.round_num + 1}. "
                "This may occur if there are insufficient teams or all teams are in the same grade."
            )
    else:
        st.info("Click **Analyze** to generate matchup recommendations based on round results.")


def _render_learning_stats(learner: MatchupLearner, season: str) -> None:
    """Render historical learning statistics.

    Args:
        learner: MatchupLearner instance.
        season: Current season.
    """
    stats = learner.get_accuracy_stats(season)

    if stats.total_predictions > 0:
        st.markdown("#### 📊 Prediction Performance")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Predictions", stats.total_predictions)
        with col2:
            st.metric("Accuracy", f"{stats.accuracy_rate:.1f}%")
        with col3:
            st.metric("Weighted Accuracy", f"{stats.weighted_accuracy_rate:.1f}%")
        with col4:
            st.metric("Variance Reduced", f"{stats.variance_reduction_rate:.1f}%")

        # Improvement suggestions
        suggestions = learner.get_improvement_suggestions(season)
        if suggestions:
            with st.expander("💡 Insights"):
                for suggestion in suggestions:
                    st.info(suggestion)


def _render_round_analysis(analysis: RoundAnalysis) -> None:
    """Render round analysis results.

    Args:
        analysis: RoundAnalysis object.
    """
    st.markdown(f"### Round {analysis.round_num} Analysis")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Games", analysis.total_games)
    with col2:
        st.metric("High Variance Games", analysis.high_variance_count)
    with col3:
        st.metric("Avg Variance %", f"{analysis.avg_variance_percentage:.1f}%")
    with col4:
        if analysis.grade_std_devs:
            avg_std = sum(analysis.grade_std_devs.values()) / len(analysis.grade_std_devs)
            st.metric("Avg Grade Std Dev", f"{avg_std:.1f}")

    # Grade standard deviations
    if analysis.grade_std_devs:
        with st.expander("📊 Variance by Grade"):
            df = pd.DataFrame(
                [
                    {"Grade": grade, "Std Dev (pts)": std}
                    for grade, std in sorted(analysis.grade_std_devs.items())
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

    # High variance games
    if analysis.high_variance_games:
        st.markdown("#### ⚠️ High Variance Games")
        hvg_data = []
        for hvg in analysis.high_variance_games:
            game = hvg.game
            winner = game.team_name if game.margin > 0 else game.opponent_name
            loser = game.opponent_name if game.margin > 0 else game.team_name
            hvg_data.append(
                {
                    "Winner": winner,
                    "Loser": loser,
                    "Score": f"{game.score_for} - {game.score_against}",
                    "Margin": abs(game.margin),
                    "Variance %": f"{hvg.variance_percentage:.1f}%",
                    "Winner Action": hvg.winner_should.replace("_", " ").title(),
                    "Loser Action": hvg.loser_should.replace("_", " ").title(),
                }
            )

        df = pd.DataFrame(hvg_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Variance %": st.column_config.TextColumn(
                    "Variance %",
                    help="Margin as percentage of total points",
                ),
                "Winner Action": st.column_config.TextColumn(
                    "Winner Should",
                    help="Recommended action for winning team",
                ),
                "Loser Action": st.column_config.TextColumn(
                    "Loser Should",
                    help="Recommended action for losing team",
                ),
            },
        )
    else:
        st.success("No high variance games detected in this round.")


def _render_matchup_recommendations(
    matchups: list[MatchupRecommendation],
    storage: MatchupStorage,
    season: str,
) -> None:
    """Render matchup recommendations with approval workflow.

    Args:
        matchups: List of matchup recommendations.
        storage: MatchupStorage for persistence.
        season: Current season.
    """
    st.markdown(f"### Recommended Matchups for Round {matchups[0].round_num if matchups else '?'}")

    # Categorize matchups
    pending = [m for m in matchups if m.status == MatchupStatus.PENDING]
    cross_grade = [m for m in matchups if m.is_cross_grade]
    same_grade = [m for m in matchups if not m.is_cross_grade]

    # Summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Matchups", len(matchups))
    with col2:
        st.metric("Cross-Grade", len(cross_grade))
    with col3:
        st.metric("Same-Grade", len(same_grade))
    with col4:
        st.metric("Pending Approval", len(pending))

    # Bulk actions
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("✅ Accept All", type="primary", disabled=len(pending) == 0):
            for m in pending:
                m.status = MatchupStatus.APPROVED
            storage.save_matchups(matchups, season)
            st.success(f"Approved {len(pending)} matchups")
            st.rerun()
    with col2:
        if st.button("❌ Reject All", disabled=len(pending) == 0):
            for m in pending:
                m.status = MatchupStatus.REJECTED
            storage.save_matchups(matchups, season)
            st.warning(f"Rejected {len(pending)} matchups")
            st.rerun()
    with col3:
        # Excel export button
        from src.exports.excel import export_matchups_excel

        round_num = matchups[0].round_num if matchups else 1
        # Only export approved matchups
        export_matchups = [m for m in matchups if m.status == MatchupStatus.APPROVED]
        if export_matchups:
            excel_bytes = export_matchups_excel(export_matchups, round_num)
            st.download_button(
                label=f"📥 Export Round {round_num} Matchups",
                data=excel_bytes,
                file_name=f"round_{round_num}_matchups.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("Approve matchups to enable export")

    # Tabs for different views
    tab_all, tab_cross, tab_same = st.tabs(
        [
            f"All ({len(matchups)})",
            f"Cross-Grade ({len(cross_grade)})",
            f"Same-Grade ({len(same_grade)})",
        ]
    )

    with tab_all:
        _render_matchups_table(matchups, storage, season, "all")

    with tab_cross:
        if cross_grade:
            _render_matchups_table(cross_grade, storage, season, "cross")
        else:
            st.info("No cross-grade matchups recommended.")

    with tab_same:
        if same_grade:
            _render_matchups_table(same_grade, storage, season, "same")
        else:
            st.info("No same-grade matchups recommended.")


def _render_matchups_table(
    matchups: list[MatchupRecommendation],
    storage: MatchupStorage,
    season: str,
    table_key: str,
) -> None:
    """Render matchups as interactive table.

    Args:
        matchups: Matchups to display.
        storage: MatchupStorage instance.
        season: Current season.
        table_key: Unique key for this table.
    """
    if not matchups:
        return

    for i, matchup in enumerate(matchups):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 2])

            with col1:
                grade_a = (
                    (
                        matchup.team_a_grade.value
                        if hasattr(matchup.team_a_grade, "value")
                        else str(matchup.team_a_grade)
                    )
                    if matchup.team_a_grade
                    else "?"
                )
                st.markdown(f"**{matchup.team_a_name}**")
                st.caption(f"Grade: {grade_a} | Margin: {matchup.team_a_recent_margin or 0:+.1f}")

            with col2:
                grade_b = (
                    (
                        matchup.team_b_grade.value
                        if hasattr(matchup.team_b_grade, "value")
                        else str(matchup.team_b_grade)
                    )
                    if matchup.team_b_grade
                    else "?"
                )
                st.markdown(f"**{matchup.team_b_name}**")
                st.caption(f"Grade: {grade_b} | Margin: {matchup.team_b_recent_margin or 0:+.1f}")

            with col3:
                type_str = (
                    matchup.matchup_type.value
                    if isinstance(matchup.matchup_type, MatchupType)
                    else matchup.matchup_type
                )
                type_display = type_str.replace("_", " ").title()
                if matchup.is_cross_grade:
                    st.warning(type_display)
                else:
                    st.info(type_display)

            with col4:
                conf_str = (
                    matchup.confidence.value
                    if isinstance(matchup.confidence, MatchupConfidence)
                    else matchup.confidence
                )
                conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf_str, "⚪")
                st.markdown(f"{conf_emoji} {conf_str.title()}")

            with col5:
                status_str = (
                    matchup.status.value
                    if isinstance(matchup.status, MatchupStatus)
                    else matchup.status
                )
                if status_str == "pending":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✅", key=f"approve_{table_key}_{i}", help="Approve"):
                            matchup.status = MatchupStatus.APPROVED
                            storage.save_matchups([matchup], season)
                            st.rerun()
                    with col_b:
                        if st.button("❌", key=f"reject_{table_key}_{i}", help="Reject"):
                            matchup.status = MatchupStatus.REJECTED
                            storage.save_matchups([matchup], season)
                            st.rerun()
                elif status_str == "approved":
                    st.success("Approved")
                else:
                    st.error("Rejected")

            # Show justification for cross-grade matchups
            if matchup.justification:
                with st.expander("📝 Justification"):
                    st.write(matchup.justification)
                    if matchup.variance_reduction_estimate > 0:
                        st.caption(
                            f"Estimated variance reduction: {matchup.variance_reduction_estimate:.0f}%"
                        )

            st.divider()
