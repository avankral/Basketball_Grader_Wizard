"""Bye rotation management for fair scheduling.

Handles bye assignment when grades have odd team counts,
using round-robin rotation to ensure fairness.
"""

from __future__ import annotations

from collections import defaultdict

from src.models.game_result import TeamSeason
from src.models.matchup import ByeAssignment


class ByeRotationManager:
    """Manages bye assignments with round-robin rotation.

    Tracks which teams have received byes and ensures fair
    distribution across the season.
    """

    def __init__(self) -> None:
        """Initialize the bye rotation manager."""
        # Track bye history: team_name -> list of round numbers
        self._bye_history: dict[str, list[int]] = defaultdict(list)

    def load_history(self, assignments: list[ByeAssignment]) -> None:
        """Load existing bye history from storage.

        Args:
            assignments: Previously recorded bye assignments.
        """
        for assignment in assignments:
            self._bye_history[assignment.team_name].append(assignment.round_num)

    def assign_bye(
        self,
        teams_needing_bye: list[TeamSeason],
        round_num: int,
        reason: str = "odd_count",
    ) -> ByeAssignment | None:
        """Assign a bye to one team from the list.

        Uses round-robin logic to select the team that has had
        the fewest byes, with ties broken by longest time since
        last bye.

        Args:
            teams_needing_bye: Teams that could receive the bye.
            round_num: Current round number.
            reason: Reason for the bye assignment.

        Returns:
            ByeAssignment for selected team, or None if no teams provided.
        """
        if not teams_needing_bye:
            return None

        # Score each team based on bye history
        team_scores: list[tuple[TeamSeason, int, int]] = []

        for team in teams_needing_bye:
            bye_count = len(self._bye_history.get(team.team_name, []))

            # Calculate rounds since last bye (higher = longer wait)
            bye_rounds = self._bye_history.get(team.team_name, [])
            rounds_since_bye = round_num - max(bye_rounds) if bye_rounds else round_num

            team_scores.append((team, bye_count, rounds_since_bye))

        # Sort by: fewest byes first, then longest wait since last bye
        team_scores.sort(key=lambda x: (x[1], -x[2]))

        selected_team = team_scores[0][0]

        # Record the bye
        assignment = ByeAssignment(
            team_name=selected_team.team_name,
            round_num=round_num,
            reason=reason,
        )
        self._bye_history[selected_team.team_name].append(round_num)

        return assignment

    def assign_byes_for_groups(
        self,
        teams_by_grade: dict[str, list[TeamSeason]],
        round_num: int,
    ) -> list[ByeAssignment]:
        """Assign byes for all grades with odd team counts.

        Args:
            teams_by_grade: Teams grouped by grade.
            round_num: Current round number.

        Returns:
            List of bye assignments.
        """
        assignments: list[ByeAssignment] = []

        for _grade, teams in teams_by_grade.items():
            if len(teams) % 2 == 1:  # Odd number of teams
                assignment = self.assign_bye(teams, round_num, reason="odd_count")
                if assignment:
                    assignments.append(assignment)

        return assignments

    def get_team_bye_count(self, team_name: str) -> int:
        """Get the number of byes a team has received.

        Args:
            team_name: Name of the team.

        Returns:
            Number of byes received.
        """
        return len(self._bye_history.get(team_name, []))

    def get_team_bye_rounds(self, team_name: str) -> list[int]:
        """Get the rounds where a team had a bye.

        Args:
            team_name: Name of the team.

        Returns:
            List of round numbers.
        """
        return list(self._bye_history.get(team_name, []))

    def get_bye_summary(self) -> dict[str, int]:
        """Get summary of bye counts for all teams.

        Returns:
            Dictionary mapping team name to bye count.
        """
        return {team: len(rounds) for team, rounds in self._bye_history.items()}

    def clear_history(self) -> None:
        """Clear all bye history."""
        self._bye_history.clear()

    def remove_round(self, round_num: int) -> None:
        """Remove all bye assignments for a specific round.

        Useful when regenerating matchups for a round.

        Args:
            round_num: Round number to clear.
        """
        for team in self._bye_history:
            self._bye_history[team] = [r for r in self._bye_history[team] if r != round_num]
