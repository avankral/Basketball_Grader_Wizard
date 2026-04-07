"""Build a shareable static website from a DVBA grading workbook.

This script parses the Excel file, computes metrics/recommendations,
creates a static HTML dashboard, and packages it as a zip archive.
"""

from __future__ import annotations

import argparse
import html
import zipfile
from pathlib import Path

import pandas as pd

from src.data.parser import GradingBookParser
from src.grading.metrics import calculate_team_metrics
from src.grading.recommender import RecommendationEngine
from src.grading.strength_of_schedule import calculate_sos
from src.models.game_result import TeamSeason
from src.models.recommendation import Recommendation


def _enum_to_str(value: object | None) -> str:
    """Convert enum/string/None values to display text.

    Args:
        value: Value to convert.

    Returns:
        String representation suitable for HTML rendering.
    """
    if value is None:
        return "N/A"
    if hasattr(value, "value"):
      return str(value.value)
    return str(value)


def _build_summary_dataframe(
    teams: list[TeamSeason],
    recommendations: list[Recommendation],
) -> pd.DataFrame:
    """Build a summary dataframe for the website table.

    Args:
        teams: Parsed team season data.
        recommendations: Engine recommendations for teams.

    Returns:
        DataFrame with one row per team.
    """
    rec_by_team = {r.team_name: r for r in recommendations}
    rows: list[dict[str, object]] = []

    for team in teams:
        metrics = calculate_team_metrics(team)
        sos = calculate_sos(team)
        rec = rec_by_team.get(team.team_name)

        rows.append(
            {
                "Team": team.team_name,
                "Club": team.club_name or "",
                "Sheet": team.sheet_name,
                "Gender": _enum_to_str(team.gender),
                "Age Group": team.age_group,
                "Division": team.division,
                "Current Grade": _enum_to_str(team.assigned_grade),
                "Wins": metrics.wins,
                "Losses": metrics.losses,
                "Win Rate %": metrics.win_rate,
                "Avg Margin": metrics.avg_margin,
                "Blowout Wins": metrics.blowout_wins,
                "Blowout Losses": metrics.blowout_losses,
                "SoS Score": sos.sos_score,
                "Schedule": sos.schedule_difficulty,
                "Recommendation": _enum_to_str(rec.recommendation_type) if rec else "N/A",
                "Recommended Grade": rec.recommended_grade if rec else "N/A",
                "Confidence": _enum_to_str(rec.confidence) if rec else "N/A",
            }
        )

    df = pd.DataFrame(rows)
    return df.sort_values(["Age Group", "Gender", "Division", "Team"]).reset_index(drop=True)


def _render_table_html(df: pd.DataFrame) -> str:
    """Render dataframe as an HTML table.

    Args:
        df: Dataframe to render.

    Returns:
        HTML table markup.
    """
    headers = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)

    body_rows: list[str] = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row.tolist())
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        "<table>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _render_site_html(
    source_file: Path,
    total_teams: int,
    total_games: int,
    recommendation_count: int,
    table_html: str,
) -> str:
    """Build final static HTML page.

    Args:
        source_file: XLS source path.
        total_teams: Number of teams parsed.
        total_games: Number of played games.
        recommendation_count: Count of non-no_change recommendations.
        table_html: Rendered summary table.

    Returns:
        Complete HTML page as string.
    """
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Basketball Grader - Shared Report</title>
  <style>
    :root {{
      --primary-blue: #00095B;
      --accent-blue: #1C69D4;
      --light-blue: #E8F1FC;
      --light-gray: #F5F5F5;
      --ink: #1F2937;
      --ok: #198754;
      --warn: #FFC107;
      --err: #DC3545;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      color: var(--ink);
      background: linear-gradient(170deg, #ffffff 0%, var(--light-blue) 60%, #f0f3f8 100%);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px 16px 36px;
    }}
    .hero {{
      background: var(--primary-blue);
      color: #fff;
      border-radius: 14px;
      padding: 20px 22px;
      box-shadow: 0 8px 18px rgba(0, 9, 91, 0.22);
    }}
    .hero h1 {{ margin: 0 0 6px; font-size: 30px; }}
    .hero p {{ margin: 0; opacity: 0.95; }}
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .kpi {{
      background: #fff;
      border-radius: 10px;
      padding: 12px;
      border: 1px solid #d8e3f3;
    }}
    .kpi .label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; }}
    .kpi .value {{ font-size: 26px; font-weight: 700; color: var(--primary-blue); margin-top: 4px; }}
    .panel {{
      margin-top: 16px;
      background: rgba(255, 255, 255, 0.94);
      border: 1px solid #dbe4f1;
      border-radius: 12px;
      overflow: hidden;
    }}
    .panel-head {{
      background: var(--light-gray);
      border-bottom: 1px solid #dbe4f1;
      padding: 10px 12px;
      font-weight: 600;
    }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; min-width: 1300px; width: 100%; }}
    th, td {{ border-bottom: 1px solid #edf1f6; padding: 8px 10px; text-align: left; font-size: 13px; }}
    th {{ position: sticky; top: 0; background: #0e1a72; color: #fff; z-index: 1; }}
    tr:nth-child(even) td {{ background: #fbfdff; }}
    .foot {{ margin-top: 12px; font-size: 12px; color: #6b7280; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>Basketball Grader Shared Website</h1>
      <p>Generated from source file: {html.escape(source_file.name)}</p>
    </section>

    <section class=\"kpi-row\">
      <article class=\"kpi\"><div class=\"label\">Teams</div><div class=\"value\">{total_teams}</div></article>
      <article class=\"kpi\"><div class=\"label\">Games</div><div class=\"value\">{total_games}</div></article>
      <article class=\"kpi\"><div class=\"label\">Actions Needed</div><div class=\"value\">{recommendation_count}</div></article>
    </section>

    <section class=\"panel\">
      <div class=\"panel-head\">Team Summary</div>
      <div class=\"table-wrap\">{table_html}</div>
    </section>

    <div class=\"foot\">Static export generated by Basketball Grader Wizard.</div>
  </div>
</body>
</html>
"""


def build_shareable_site(source_xlsx: Path, output_dir: Path, zip_path: Path) -> None:
    """Build website files and zip package.

    Args:
        source_xlsx: Input grading workbook path.
        output_dir: Directory where website files are written.
        zip_path: Final zip archive path.
    """
    parser = GradingBookParser(source_xlsx)
    teams = parser.parse_all()

    engine = RecommendationEngine()
    recommendations = engine.generate_all_recommendations(teams)

    df = _build_summary_dataframe(teams, recommendations)
    table_html = _render_table_html(df)

    total_games = int(sum(t.games_played for t in teams))
    actions_needed = sum(
        1
        for rec in recommendations
        if _enum_to_str(rec.recommendation_type) in {"promote", "demote", "review_needed"}
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    index_html = _render_site_html(
        source_file=source_xlsx,
        total_teams=len(teams),
        total_games=total_games,
        recommendation_count=actions_needed,
        table_html=table_html,
    )

    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    df.to_csv(output_dir / "team_summary.csv", index=False)

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(output_dir / "index.html", arcname="index.html")
        zf.write(output_dir / "team_summary.csv", arcname="team_summary.csv")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build shareable static website + zip")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data") / "Autumn 2026 Club Grading Book Rd5.xlsx",
        help="Path to source XLS/XLSX grading file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("shareable_site"),
        help="Output directory for website files.",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=Path("shareable_site.zip"),
        help="Output zip archive path.",
    )
    args = parser.parse_args()

    build_shareable_site(args.source, args.out_dir, args.zip)
    print(f"Website generated: {args.out_dir / 'index.html'}")
    print(f"CSV generated: {args.out_dir / 'team_summary.csv'}")
    print(f"Zip generated: {args.zip}")


if __name__ == "__main__":
    main()
