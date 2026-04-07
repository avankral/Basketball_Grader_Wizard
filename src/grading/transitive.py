"""Transitive variance chain detection.

Identifies hidden grade mismatches through transitive analysis:
If Team A beats Team B by 40, and Team B beats Team C by 30,
this implies a potential 70+ point variance between A and C.

This is critical for detecting teams placed in the wrong grade
before they actually play each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.game_result import GameResult, ResultType, TeamSeason


@dataclass
class TransitiveLink:
    """A single link in a transitive chain.

    Represents one game result connecting two teams.
    """

    winner: str
    loser: str
    margin: int
    round_num: int

    def __str__(self) -> str:
        return f"{self.winner} def {self.loser} by {self.margin}"


@dataclass
class TransitiveChain:
    """A chain of game results implying transitive variance.

    Attributes:
        links: Sequence of game results forming the chain.
        implied_variance: Total implied point differential across chain.
        start_team: Team at start of chain.
        end_team: Team at end of chain.
        confidence: How reliable this chain is (affected by date spread, etc.).
    """

    links: list[TransitiveLink] = field(default_factory=list)
    start_team: str = ""
    end_team: str = ""

    @property
    def implied_variance(self) -> int:
        """Total implied point differential across the chain."""
        return sum(link.margin for link in self.links)

    @property
    def chain_length(self) -> int:
        """Number of games in the chain."""
        return len(self.links)

    @property
    def is_significant(self) -> bool:
        """Check if chain implies a significant mismatch (40+ points)."""
        return self.implied_variance >= 40

    def __str__(self) -> str:
        if not self.links:
            return "Empty chain"

        parts = []
        for link in self.links:
            parts.append(f"{link.winner} def {link.loser} ({link.margin})")

        chain_str = " → ".join(parts)
        return f"{chain_str} = {self.implied_variance} point implied variance"

    def get_summary(self) -> str:
        """Generate human-readable summary for reports."""
        if not self.links:
            return "No transitive chain detected."

        return (
            f"Transitive analysis: {self.start_team} → {self.end_team}\n"
            f"Chain: {self}\n"
            f"Implied variance: {self.implied_variance} points"
        )


def find_transitive_chains(
    target_team: str,
    all_teams: list[TeamSeason],
    max_depth: int = 2,
    min_margin: int = 15,
) -> list[TransitiveChain]:
    """Find transitive variance chains involving a target team.

    Searches for paths where:
    1. Team A beat Team B by significant margin
    2. Team B beat Team C by significant margin
    3. This implies Team A vs Team C would be a mismatch

    Args:
        target_team: Team name to analyze.
        all_teams: All teams in the grading group.
        max_depth: Maximum chain length (default 2 = A→B→C).
        min_margin: Minimum margin to consider significant (default 15).

    Returns:
        List of TransitiveChain objects representing detected variance paths.
    """
    chains: list[TransitiveChain] = []

    # Build a lookup of all game results
    game_lookup: dict[str, list[GameResult]] = {}
    for team in all_teams:
        game_lookup[team.team_name] = [
            g for g in team.games if g.result != ResultType.DNP and g.margin >= min_margin
        ]

    # Find chains starting from target team's wins
    target_games = game_lookup.get(target_team, [])

    for game in target_games:
        if game.result != ResultType.WON or game.margin < min_margin:
            continue

        # Start a chain: target_team beat opponent
        initial_link = TransitiveLink(
            winner=target_team,
            loser=game.opponent_name,
            margin=game.margin,
            round_num=game.round_num,
        )

        # Look for chains extending from the opponent
        _extend_chain(
            current_chain=[initial_link],
            current_team=game.opponent_name,
            game_lookup=game_lookup,
            chains=chains,
            visited={target_team, game.opponent_name},
            max_depth=max_depth,
            min_margin=min_margin,
            start_team=target_team,
        )

    # Also find chains where target team is on the receiving end
    for team in all_teams:
        if team.team_name == target_team:
            continue

        for game in team.games:
            if (
                game.opponent_name == target_team
                and game.result == ResultType.WON
                and game.margin >= min_margin
            ):
                # Other team beat target team - extend backwards
                initial_link = TransitiveLink(
                    winner=team.team_name,
                    loser=target_team,
                    margin=game.margin,
                    round_num=game.round_num,
                )

                _extend_chain(
                    current_chain=[initial_link],
                    current_team=target_team,
                    game_lookup=game_lookup,
                    chains=chains,
                    visited={team.team_name, target_team},
                    max_depth=max_depth,
                    min_margin=min_margin,
                    start_team=team.team_name,
                )

    # Filter to significant chains only
    return [c for c in chains if c.is_significant]


def _extend_chain(
    current_chain: list[TransitiveLink],
    current_team: str,
    game_lookup: dict[str, list[GameResult]],
    chains: list[TransitiveChain],
    visited: set[str],
    max_depth: int,
    min_margin: int,
    start_team: str,
) -> None:
    """Recursively extend a transitive chain.

    Args:
        current_chain: Chain built so far.
        current_team: Team to extend from (lost in last link).
        game_lookup: All game results by team.
        chains: Output list to append complete chains to.
        visited: Teams already in chain (avoid cycles).
        max_depth: Maximum chain length.
        min_margin: Minimum margin for links.
        start_team: Original team at chain start.
    """
    # If chain is at max depth, record it
    if len(current_chain) >= max_depth:
        chain = TransitiveChain(
            links=current_chain.copy(),
            start_team=start_team,
            end_team=current_chain[-1].loser,
        )
        if chain.is_significant:
            chains.append(chain)
        return

    # Look for wins by current_team (the loser in last link)
    current_games = game_lookup.get(current_team, [])

    for game in current_games:
        if (
            game.result != ResultType.WON
            or game.margin < min_margin
            or game.opponent_name in visited
        ):
            continue

        # Extend the chain
        link = TransitiveLink(
            winner=current_team,
            loser=game.opponent_name,
            margin=game.margin,
            round_num=game.round_num,
        )

        new_chain = current_chain + [link]
        new_visited = visited | {game.opponent_name}

        # Record this chain
        chain = TransitiveChain(
            links=new_chain.copy(),
            start_team=start_team,
            end_team=game.opponent_name,
        )
        if chain.is_significant:
            chains.append(chain)

        # Continue extending if not at max depth
        if len(new_chain) < max_depth:
            _extend_chain(
                current_chain=new_chain,
                current_team=game.opponent_name,
                game_lookup=game_lookup,
                chains=chains,
                visited=new_visited,
                max_depth=max_depth,
                min_margin=min_margin,
                start_team=start_team,
            )
