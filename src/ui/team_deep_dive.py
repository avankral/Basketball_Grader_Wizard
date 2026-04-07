"""Team deep dive analysis view.

Provides detailed analysis for a single team including:
- Complete game history
- SoS breakdown
- Transitive variance chains
- Appeal document generation
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.cache import get_team_metrics, get_team_sos
from src.grading.metrics import TeamMetrics, calculate_team_metrics
from src.grading.strength_of_schedule import StrengthOfSchedule, calculate_sos
from src.grading.transitive import find_transitive_chains
from src.models.game_result import ResultType, TeamSeason
from src.models.recommendation import Recommendation
from src.ui.charts import create_margin_trend_chart


def render_team_deep_dive(
    teams: list[TeamSeason],
    recommendations: dict[str, Recommendation] | None = None,
) -> None:
    """Render team deep dive analysis.

    Args:
        teams: All available teams.
        recommendations: Dict of recommendations by team name.
    """
    if not teams:
        st.info("No teams available. Upload data first.")
        return

    st.subheader("🔍 Team Deep Dive")

    # Team selector
    team_names = sorted([t.team_name for t in teams])
    selected_team_name = st.selectbox(
        "Select Team",
        options=team_names,
        key="deep_dive_team",
    )

    if not selected_team_name:
        return

    team = next(t for t in teams if t.team_name == selected_team_name)
    # Use cached data for performance
    metrics = get_team_metrics(team.team_name) or calculate_team_metrics(team)
    sos = get_team_sos(team.team_name) or calculate_sos(team)
    recommendation = recommendations.get(team.team_name) if recommendations else None

    # Team header
    _render_team_header(team, metrics, sos, recommendation)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Game History",
            "📈 Performance",
            "🔗 Transitive Analysis",
            "📄 Generate Appeal",
        ]
    )

    with tab1:
        _render_game_history(team)

    with tab2:
        _render_performance_analysis(team, metrics, sos, teams)

    with tab3:
        _render_transitive_analysis(team, teams)

    with tab4:
        _render_appeal_generator(team, metrics, sos, recommendation, teams)


def _render_team_header(
    team: TeamSeason,
    metrics: TeamMetrics,
    sos: StrengthOfSchedule,
    recommendation: Recommendation | None,
) -> None:
    """Render team header with key stats.

    Args:
        team: Team data.
        metrics: Team metrics.
        sos: SoS analysis.
        recommendation: Team recommendation if any.
    """
    # Recommendation badge
    if recommendation:
        rec_type = recommendation.recommendation_type.value if hasattr(recommendation.recommendation_type, "value") else str(recommendation.recommendation_type)
        conf_val = recommendation.confidence.value if hasattr(recommendation.confidence, "value") else str(recommendation.confidence)
        st.markdown(f"**Status:** {rec_type.upper()} (Confidence: {conf_val.title()})")

    # Key metrics in columns
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Grade", team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A")

    with col2:
        st.metric("Record", f"{metrics.wins}W - {metrics.losses}L")

    with col3:
        st.metric("Avg Margin", f"{metrics.avg_margin:+.1f}")

    with col4:
        st.metric("SoS Score", f"{sos.sos_score}/100")

    with col5:
        blowout_diff = metrics.blowout_wins - metrics.blowout_losses
        st.metric("Blowout +/-", f"{blowout_diff:+d}")


def _render_game_history(team: TeamSeason) -> None:
    """Render complete game history table.

    Args:
        team: Team data.
    """
    st.markdown("### Game History")

    if not team.games:
        st.info("No games recorded yet.")
        return

    rows = []
    for game in sorted(team.games, key=lambda g: g.round_num):
        if game.result == ResultType.DNP:
            rows.append(
                {
                    "Round": game.round_num,
                    "Result": "DNP",
                    "Opponent": "-",
                    "Score": "-",
                    "Margin": "-",
                    "Opp Grade": "-",
                    "Variance": "-",
                }
            )
        else:
            rows.append(
                {
                    "Round": game.round_num,
                    "Result": "✅ W" if game.result == ResultType.WON else "❌ L",
                    "Opponent": game.opponent_name,
                    "Score": f"{game.score_for} - {game.score_against}",
                    "Margin": f"{game.margin:+d}",
                    "Opp Grade": game.opponent_grade.value if hasattr(game.opponent_grade, "value") else str(game.opponent_grade) if game.opponent_grade else "?",
                    "Variance": (game.variance_class.value if hasattr(game.variance_class, "value") else str(game.variance_class)).replace("_", " ").title(),
                }
            )

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def _render_performance_analysis(
    team: TeamSeason,
    metrics: TeamMetrics,
    sos: StrengthOfSchedule,
    all_teams: list[TeamSeason],
) -> None:
    """Render performance analysis charts.

    Args:
        team: Team data.
        metrics: Team metrics.
        sos: SoS analysis.
        all_teams: All teams for comparison.
    """
    st.markdown("### Performance Analysis")

    # Margin trend chart
    st.markdown("#### Margin Trend")
    fig = create_margin_trend_chart([team], selected_teams=[team.team_name])
    st.plotly_chart(fig, width="stretch")

    # Detailed stats
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Performance Breakdown")
        st.write(f"- **Win Rate:** {metrics.win_rate}%")
        st.write(f"- **Weighted Win Rate:** {metrics.weighted_win_rate}%")
        st.write(f"- **Blowout Wins:** {metrics.blowout_wins}")
        st.write(f"- **Blowout Losses:** {metrics.blowout_losses}")
        st.write(f"- **Close Wins:** {metrics.close_wins}")
        st.write(f"- **Close Losses:** {metrics.close_losses}")

    with col2:
        st.markdown("#### Schedule Analysis")
        st.write(f"- **SoS Score:** {sos.sos_score}/100")
        st.write(f"- **Schedule Difficulty:** {sos.schedule_difficulty}")
        st.write(f"- **Played UP:** {sos.played_above_count} games")
        st.write(f"- **Played AT Grade:** {sos.played_at_grade_count} games")
        st.write(f"- **Played DOWN:** {sos.played_below_count} games")

        if sos.never_played_at_grade:
            st.warning("⚠️ Never played at assigned grade!")

    # Results by opponent grade
    st.markdown("#### Results by Opponent Grade")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**vs Higher Grades**")
        st.write(f"Wins: {metrics.results_vs_higher.get('W', 0)}")
        st.write(f"Losses: {metrics.results_vs_higher.get('L', 0)}")

    with col2:
        st.markdown("**vs Same Grade**")
        st.write(f"Wins: {metrics.results_vs_same.get('W', 0)}")
        st.write(f"Losses: {metrics.results_vs_same.get('L', 0)}")

    with col3:
        st.markdown("**vs Lower Grades**")
        st.write(f"Wins: {metrics.results_vs_lower.get('W', 0)}")
        st.write(f"Losses: {metrics.results_vs_lower.get('L', 0)}")


def _render_transitive_analysis(
    team: TeamSeason,
    all_teams: list[TeamSeason],
) -> None:
    """Render transitive variance chain analysis.

    Args:
        team: Team to analyze.
        all_teams: All teams for chain detection.
    """
    st.markdown("### Transitive Variance Analysis")
    st.markdown(
        "Transitive analysis detects hidden grade mismatches. "
        "If Team A beats Team B by 40, and Team B beats Team C by 30, "
        "this implies Team A vs Team C would be a ~70 point mismatch."
    )

    chains = find_transitive_chains(team.team_name, all_teams, max_depth=2, min_margin=15)

    if not chains:
        st.success("✅ No significant transitive variance detected.")
        return

    st.warning(f"⚠️ Found {len(chains)} transitive chain(s)")

    for i, chain in enumerate(chains, 1):
        with st.expander(
            f"Chain {i}: {chain.start_team} → {chain.end_team} ({chain.implied_variance} pts)"
        ):
            st.markdown("**Chain Path:**")
            for link in chain.links:
                st.write(
                    f"- {link.winner} def {link.loser} by {link.margin} (Round {link.round_num})"
                )

            st.markdown(f"**Implied Variance:** {chain.implied_variance} points")

            if chain.implied_variance >= 50:
                st.error("⚠️ This is a significant mismatch indicator!")
            else:
                st.warning("This is a moderate concern worth monitoring.")


def _render_appeal_generator(
    team: TeamSeason,
    metrics: TeamMetrics,
    sos: StrengthOfSchedule,
    recommendation: Recommendation | None,
    all_teams: list[TeamSeason],
) -> None:
    """Render appeal document generator.

    Args:
        team: Team data.
        metrics: Team metrics.
        sos: SoS analysis.
        recommendation: Team recommendation.
        all_teams: All teams for context.
    """
    st.markdown("### Generate Appeal Document")
    st.markdown(
        "Generate a formal appeal document for submission to DVBA. "
        "The document includes all evidence supporting a grade change."
    )

    if not recommendation or not recommendation.requires_action:
        st.info("No pending recommendation for this team. Appeal generation not needed.")
        return

    # Appeal preview
    st.markdown("#### Preview")

    appeal_text = _generate_appeal_text(team, metrics, sos, recommendation, all_teams)
    st.text_area("Appeal Document", value=appeal_text, height=400, disabled=True)

    # Download buttons
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📄 Download as Text",
            data=appeal_text,
            file_name=f"appeal_{team.team_name.replace(' ', '_')}.txt",
            mime="text/plain",
        )

    with col2:
        # Word document would require python-docx
        st.info("Word/PDF export available in full version.")


def _generate_appeal_text(
    team: TeamSeason,
    metrics: TeamMetrics,
    sos: StrengthOfSchedule,
    recommendation: Recommendation,
    all_teams: list[TeamSeason],
) -> str:
    """Generate appeal document text.

    Args:
        team: Team data.
        metrics: Team metrics.
        sos: SoS analysis.
        recommendation: Team recommendation.
        all_teams: All teams for context.

    Returns:
        Formatted appeal document text.
    """
    lines = [
        "=" * 60,
        "DVBA GRADE APPEAL SUBMISSION",
        "=" * 60,
        "",
        f"Team: {team.team_name}",
        f"Club: {team.club_name or 'N/A'}",
        f"Current Grade: {team.assigned_grade.value if hasattr(team.assigned_grade, 'value') else str(team.assigned_grade) if team.assigned_grade else 'N/A'}",
        f"Requested Action: {recommendation.recommendation_type.value if hasattr(recommendation.recommendation_type, 'value') else str(recommendation.recommendation_type).upper()}",
        f"Proposed Grade: {recommendation.recommended_grade or 'N/A'}",
        f"Submission Date: {recommendation.created_at.strftime('%Y-%m-%d')}",
        "",
        "-" * 60,
        "SUMMARY",
        "-" * 60,
        "",
        recommendation.explanation,
        "",
        "-" * 60,
        "PERFORMANCE DATA",
        "-" * 60,
        "",
        f"Record: {metrics.wins}W - {metrics.losses}L ({metrics.win_rate}% win rate)",
        f"Average Margin: {metrics.avg_margin:+.1f} points",
        f"Points For: {metrics.points_for}",
        f"Points Against: {metrics.points_against}",
        f"Total Margin: {metrics.total_margin:+d}",
        "",
        "Blowout Analysis (20+ point margin):",
        f"  - Blowout Wins: {metrics.blowout_wins}",
        f"  - Blowout Losses: {metrics.blowout_losses}",
        f"  - Close Games (5 pts or less): {metrics.close_wins + metrics.close_losses}",
        "",
        "-" * 60,
        "STRENGTH OF SCHEDULE",
        "-" * 60,
        "",
        f"SoS Score: {sos.sos_score}/100 ({sos.schedule_difficulty})",
        f"Total Games: {sos.total_games}",
        f"Games vs Higher-Graded Teams: {sos.played_above_count}",
        f"Games vs Same-Grade Teams: {sos.played_at_grade_count}",
        f"Games vs Lower-Graded Teams: {sos.played_below_count}",
        "",
    ]

    if sos.never_played_at_grade:
        grade_str = team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade) if team.assigned_grade else "N/A"
        lines.extend(
            [
                "WARNING: This team has not played any opponents at their assigned",
                f"grade level ({grade_str}). Grade placement cannot be validated.",
                "",
            ]
        )

    lines.extend(
        [
            "-" * 60,
            "SUPPORTING EVIDENCE",
            "-" * 60,
            "",
        ]
    )

    for evidence in recommendation.evidence:
        lines.append(f"• {evidence}")

    lines.append("")

    if recommendation.concerns:
        lines.extend(
            [
                "-" * 60,
                "CONCERNS/CAVEATS",
                "-" * 60,
                "",
            ]
        )
        for concern in recommendation.concerns:
            lines.append(f"⚠ {concern}")
        lines.append("")

    # Transitive variance
    chains = find_transitive_chains(team.team_name, all_teams, max_depth=2, min_margin=15)
    if chains:
        lines.extend(
            [
                "-" * 60,
                "TRANSITIVE VARIANCE ANALYSIS",
                "-" * 60,
                "",
            ]
        )
        for chain in chains[:3]:
            lines.append(str(chain))
        lines.append("")

    lines.extend(
        [
            "-" * 60,
            "GAME-BY-GAME RESULTS",
            "-" * 60,
            "",
        ]
    )

    for game in sorted(team.games, key=lambda g: g.round_num):
        if game.result != ResultType.DNP:
            result = "W" if game.result == ResultType.WON else "L"
            opp_grade = game.opponent_grade.value if hasattr(game.opponent_grade, "value") else str(game.opponent_grade) if game.opponent_grade else "?"
            lines.append(
                f"Rd {game.round_num}: {result} vs {game.opponent_name} ({opp_grade}) "
                f"- Score: {game.score_for}-{game.score_against} (Margin: {game.margin:+d})"
            )

    lines.extend(
        [
            "",
            "=" * 60,
            "END OF APPEAL DOCUMENT",
            "=" * 60,
        ]
    )

    return "\n".join(lines)
