"""Appeal document generator.

Generates formal appeal documents suitable for submission to DVBA.
Includes all evidence, SoS analysis, and justification.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.grading.metrics import calculate_team_metrics
from src.grading.strength_of_schedule import calculate_sos
from src.grading.transitive import find_transitive_chains
from src.models.game_result import ResultType, TeamSeason
from src.models.recommendation import Recommendation


def generate_appeal_document(
    team: TeamSeason,
    recommendation: Recommendation,
    all_teams: list[TeamSeason],
    output_path: Path | None = None,
) -> str:
    """Generate a formal appeal document for DVBA submission.

    Args:
        team: Team to generate appeal for.
        recommendation: The recommendation being appealed.
        all_teams: All teams for context.
        output_path: Optional path to save document.

    Returns:
        Appeal document as text string.
    """
    metrics = calculate_team_metrics(team)
    sos = calculate_sos(team)
    chains = find_transitive_chains(team.team_name, all_teams, max_depth=2, min_margin=15)

    lines = [
        "=" * 70,
        "DIAMOND VALLEY BASKETBALL ASSOCIATION",
        "GRADE APPEAL SUBMISSION",
        "=" * 70,
        "",
        f"Submission Date: {datetime.now().strftime('%d %B %Y')}",
        "",
        "-" * 70,
        "TEAM INFORMATION",
        "-" * 70,
        "",
        f"Team Name:        {team.team_name}",
        f"Club:             {team.club_name or 'N/A'}",
        f"Age Group:        U{team.age_group}",
        f"Gender:           {team.gender.value if hasattr(team.gender, 'value') else str(team.gender)}",
        f"Division:         {team.division}",
        f"Current Grade:    {team.assigned_grade.value if hasattr(team.assigned_grade, 'value') else str(team.assigned_grade) if team.assigned_grade else 'N/A'}",
        "",
        "-" * 70,
        "APPEAL REQUEST",
        "-" * 70,
        "",
        f"Requested Action: {recommendation.recommendation_type.value.upper() if hasattr(recommendation.recommendation_type, 'value') else str(recommendation.recommendation_type).upper()}",
        f"Proposed Grade:   {recommendation.recommended_grade or 'N/A'}",
        f"Confidence Level: {recommendation.confidence.value.upper() if hasattr(recommendation.confidence, 'value') else str(recommendation.confidence).upper()}",
        "",
        "Justification:",
        "",
        _wrap_text(recommendation.explanation, width=70),
        "",
        "-" * 70,
        "PERFORMANCE SUMMARY",
        "-" * 70,
        "",
        f"Games Played:     {metrics.games_played}",
        f"Record:           {metrics.wins} Wins - {metrics.losses} Losses",
        f"Win Rate:         {metrics.win_rate}%",
        "",
        f"Points For:       {metrics.points_for}",
        f"Points Against:   {metrics.points_against}",
        f"Total Margin:     {metrics.total_margin:+d}",
        f"Average Margin:   {metrics.avg_margin:+.1f} per game",
        "",
        "Blowout Analysis (20+ point margin):",
        f"  Blowout Wins:   {metrics.blowout_wins}",
        f"  Blowout Losses: {metrics.blowout_losses}",
        f"  Close Games:    {metrics.close_wins + metrics.close_losses} (5 pts or less)",
        "",
        "-" * 70,
        "STRENGTH OF SCHEDULE ANALYSIS",
        "-" * 70,
        "",
        f"SoS Score:        {sos.sos_score}/100 ({sos.schedule_difficulty})",
        f"Total Games:      {sos.total_games}",
        "",
        "Opponent Grade Distribution:",
        f"  vs Higher Grades: {sos.played_above_count} games",
        f"  vs Same Grade:    {sos.played_at_grade_count} games",
        f"  vs Lower Grades:  {sos.played_below_count} games",
        "",
    ]

    if sos.never_played_at_grade and team.assigned_grade:
        grade_str = team.assigned_grade.value if hasattr(team.assigned_grade, "value") else str(team.assigned_grade)
        lines.extend(
            [
                "*** GRADE COVERAGE WARNING ***",
                f"This team has NOT played any {grade_str}-grade opponents.",
                "Current grade placement cannot be validated from game data.",
                "",
            ]
        )

    lines.extend(
        [
            "-" * 70,
            "SUPPORTING EVIDENCE",
            "-" * 70,
            "",
        ]
    )

    for i, evidence in enumerate(recommendation.evidence, 1):
        lines.append(f"{i}. {evidence}")
    lines.append("")

    if recommendation.concerns:
        lines.extend(
            [
                "-" * 70,
                "NOTES AND CAVEATS",
                "-" * 70,
                "",
            ]
        )
        for concern in recommendation.concerns:
            lines.append(f"- {concern}")
        lines.append("")

    if chains:
        lines.extend(
            [
                "-" * 70,
                "TRANSITIVE VARIANCE ANALYSIS",
                "-" * 70,
                "",
                "The following transitive chains indicate potential grade mismatches:",
                "",
            ]
        )
        for i, chain in enumerate(chains[:5], 1):
            lines.append(f"Chain {i}:")
            for link in chain.links:
                lines.append(
                    f"  {link.winner} defeated {link.loser} by {link.margin} points (Round {link.round_num})"
                )
            lines.append(f"  Implied Total Variance: {chain.implied_variance} points")
            lines.append("")

    lines.extend(
        [
            "-" * 70,
            "DETAILED GAME RESULTS",
            "-" * 70,
            "",
        ]
    )

    for game in sorted(team.games, key=lambda g: g.round_num):
        if game.result != ResultType.DNP:
            result_icon = "W" if game.result == ResultType.WON else "L"
            opp_grade = game.opponent_grade.value if hasattr(game.opponent_grade, "value") else str(game.opponent_grade) if game.opponent_grade else "?"
            margin_indicator = ""
            if abs(game.margin) >= 20:
                margin_indicator = " [BLOWOUT]"
            elif abs(game.margin) <= 5:
                margin_indicator = " [CLOSE]"

            lines.append(
                f"Round {game.round_num}: [{result_icon}] vs {game.opponent_name} (Grade: {opp_grade})"
            )
            lines.append(
                f"         Score: {game.score_for} - {game.score_against} "
                f"(Margin: {game.margin:+d}){margin_indicator}"
            )
        else:
            lines.append(f"Round {game.round_num}: Did Not Play")

    lines.extend(
        [
            "",
            "-" * 70,
            "DECLARATION",
            "-" * 70,
            "",
            "This appeal is submitted based on objective performance data and",
            "Strength of Schedule analysis. All information provided is accurate",
            "as per the official DVBA Club Grading Book records.",
            "",
            "We request the DVBA Grading Committee review this submission and",
            "consider the requested grade adjustment.",
            "",
            "-" * 70,
            "",
            "Submitted by: _______________________________",
            "",
            "Club Representative: _______________________________",
            "",
            "Date: _______________________________",
            "",
            "=" * 70,
            "END OF APPEAL DOCUMENT",
            "=" * 70,
        ]
    )

    document = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(document)

    return document


def _wrap_text(text: str, width: int = 70) -> str:
    """Wrap text to specified width.

    Args:
        text: Text to wrap.
        width: Maximum line width.

    Returns:
        Wrapped text.
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


def generate_club_report(
    club_name: str,
    teams: list[TeamSeason],
    recommendations: list[Recommendation],
    output_path: Path | None = None,
) -> str:
    """Generate a club-wide report for all teams.

    Args:
        club_name: Club name.
        teams: All teams in the club.
        recommendations: Recommendations for club teams.
        output_path: Optional path to save report.

    Returns:
        Report as text string.
    """
    rec_dict = {r.team_name: r for r in recommendations}

    lines = [
        "=" * 70,
        f"CLUB REPORT: {club_name.upper()}",
        f"Generated: {datetime.now().strftime('%d %B %Y %H:%M')}",
        "=" * 70,
        "",
        f"Total Teams: {len(teams)}",
        "",
    ]

    # Summary counts
    promote = sum(1 for r in recommendations if (r.recommendation_type.value if hasattr(r.recommendation_type, "value") else str(r.recommendation_type)) == "promote")
    demote = sum(1 for r in recommendations if (r.recommendation_type.value if hasattr(r.recommendation_type, "value") else str(r.recommendation_type)) == "demote")
    review = sum(1 for r in recommendations if (r.recommendation_type.value if hasattr(r.recommendation_type, "value") else str(r.recommendation_type)) == "review_needed")

    lines.extend(
        [
            "Recommendations Summary:",
            f"  - Promote: {promote}",
            f"  - Demote: {demote}",
            f"  - Review Needed: {review}",
            "",
            "-" * 70,
            "TEAM DETAILS",
            "-" * 70,
            "",
        ]
    )

    for team in sorted(teams, key=lambda t: (t.age_group, t.gender.value if hasattr(t.gender, "value") else str(t.gender))):
        metrics = calculate_team_metrics(team)
        rec = rec_dict.get(team.team_name)

        lines.append(f"Team: {team.team_name}")
        lines.append(f"Grade: {team.assigned_grade.value if hasattr(team.assigned_grade, 'value') else str(team.assigned_grade) if team.assigned_grade else 'N/A'}")
        lines.append(
            f"Record: {metrics.wins}W-{metrics.losses}L (Margin: {metrics.avg_margin:+.1f})"
        )

        if rec:
            rec_type = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
            conf_val = rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence)
            lines.append(
                f"Status: {rec_type.upper()} ({conf_val})"
            )

        lines.append("")

    document = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(document)

    return document
