"""Tests for the grading module.

Tests for:
- Grade hierarchy and comparisons
- Strength of Schedule calculations
- Team metrics
- Transitive variance detection
- Recommendation engine
"""

import pytest

from src.grading.grades import (
    GRADE_ORDER,
    GRADE_RANK,
    can_demote,
    can_promote,
    get_grade_weight,
    grade_above,
    grade_below,
    grade_distance,
    grades_between,
    is_playing_down,
    is_playing_up,
)
from src.grading.metrics import calculate_team_metrics
from src.grading.power_rating import calculate_power_ratings
from src.grading.recommender import RecommendationEngine
from src.grading.strength_of_schedule import calculate_sos
from src.grading.transitive import TransitiveChain, TransitiveLink, find_transitive_chains
from src.models.game_result import (
    GameResult,
    Gender,
    Grade,
    ResultType,
    TeamSeason,
)
from src.models.recommendation import (
    Confidence,
    RecommendationType,
)

# === Grade Hierarchy Tests ===


class TestGradeHierarchy:
    """Tests for grade hierarchy functions."""

    def test_grade_order(self):
        """Test that grades are ordered correctly."""
        assert GRADE_ORDER[0] == Grade.A
        assert GRADE_ORDER[-1] == Grade.D3
        assert len(GRADE_ORDER) == 13

    def test_grade_rank(self):
        """Test grade rank mapping."""
        assert GRADE_RANK[Grade.A] == 1
        assert GRADE_RANK[Grade.D] == 10
        assert GRADE_RANK[Grade.D3] == 13
        assert GRADE_RANK[Grade.B1] < GRADE_RANK[Grade.B2]

    def test_grade_distance(self):
        """Test grade distance calculation."""
        assert grade_distance(Grade.A, Grade.A) == 0
        assert grade_distance(Grade.A, Grade.AR) == 1
        assert grade_distance(Grade.A, Grade.B1) == 2  # A -> AR -> B1
        assert grade_distance(Grade.A, Grade.D) == 9
        assert grade_distance(Grade.C1, Grade.B1) == 4

    def test_grade_above(self):
        """Test getting grade above."""
        assert grade_above(Grade.B1) == Grade.AR
        assert grade_above(Grade.AR) == Grade.A
        assert grade_above(Grade.D) == Grade.C3
        assert grade_above(Grade.A) is None

    def test_grade_below(self):
        """Test getting grade below."""
        assert grade_below(Grade.A) == Grade.AR
        assert grade_below(Grade.AR) == Grade.B1
        assert grade_below(Grade.C2) == Grade.C3
        assert grade_below(Grade.D3) is None

    def test_grades_between(self):
        """Test grades between two grades."""
        between = grades_between(Grade.A, Grade.C1)
        assert between == [Grade.AR, Grade.B1, Grade.B2, Grade.B3, Grade.B4]

        between = grades_between(Grade.B1, Grade.B2)
        assert between == []

    def test_can_promote(self):
        """Test promotion eligibility."""
        assert can_promote(Grade.B1) is True
        assert can_promote(Grade.D) is True
        assert can_promote(Grade.A) is False

    def test_can_demote(self):
        """Test demotion eligibility."""
        assert can_demote(Grade.A) is True
        assert can_demote(Grade.B1) is True
        assert can_demote(Grade.D) is True  # D is no longer the lowest grade
        assert can_demote(Grade.D3) is False  # D3 is the lowest grade

    def test_is_playing_up(self):
        """Test playing up detection."""
        assert is_playing_up(Grade.B1, Grade.A) is True
        assert is_playing_up(Grade.C1, Grade.B2) is True
        assert is_playing_up(Grade.A, Grade.B1) is False
        assert is_playing_up(Grade.B1, Grade.B1) is False

    def test_is_playing_down(self):
        """Test playing down detection."""
        assert is_playing_down(Grade.A, Grade.B1) is True
        assert is_playing_down(Grade.B1, Grade.C1) is True
        assert is_playing_down(Grade.B1, Grade.A) is False

    def test_grade_weight(self):
        """Test grade weight calculation."""
        # Playing up should give bonus
        weight = get_grade_weight(Grade.B1, Grade.A)
        assert weight > 1.0

        # Playing down should give penalty
        weight = get_grade_weight(Grade.A, Grade.B1)
        assert weight < 1.0

        # Same grade should be neutral
        weight = get_grade_weight(Grade.B1, Grade.B1)
        assert weight == 1.0


# === Strength of Schedule Tests ===


class TestStrengthOfSchedule:
    """Tests for SoS calculations."""

    @pytest.fixture
    def team_with_games(self) -> TeamSeason:
        """Create a team with game history."""
        games = [
            GameResult(
                team_name="Test Team",
                opponent_name="Opp A",
                opponent_grade=Grade.A,
                score_for=40,
                score_against=50,
                margin=-10,
                result=ResultType.LOST,
                round_num=1,
            ),
            GameResult(
                team_name="Test Team",
                opponent_name="Opp B",
                opponent_grade=Grade.B1,
                score_for=50,
                score_against=40,
                margin=10,
                result=ResultType.WON,
                round_num=2,
            ),
            GameResult(
                team_name="Test Team",
                opponent_name="Opp C",
                opponent_grade=Grade.B1,
                score_for=45,
                score_against=42,
                margin=3,
                result=ResultType.WON,
                round_num=3,
            ),
        ]

        return TeamSeason(
            team_name="Test Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

    def test_calculate_sos(self, team_with_games: TeamSeason):
        """Test SoS calculation."""
        sos = calculate_sos(team_with_games)

        assert sos.team_name == "Test Team"
        assert sos.total_games == 3
        assert sos.played_above_count == 1  # 1 game vs A
        assert sos.played_at_grade_count == 2  # 2 games vs B1
        assert sos.grade_coverage is True

    def test_sos_score_range(self, team_with_games: TeamSeason):
        """Test that SoS score is in valid range."""
        sos = calculate_sos(team_with_games)

        assert 0 <= sos.sos_score <= 100

    def test_never_played_at_grade(self):
        """Test detection of teams not playing at grade."""
        games = [
            GameResult(
                team_name="Test Team",
                opponent_name="Opp A",
                opponent_grade=Grade.A,
                score_for=40,
                score_against=50,
                margin=-10,
                result=ResultType.LOST,
                round_num=1,
            ),
        ]

        team = TeamSeason(
            team_name="Test Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.C1,  # Assigned C1 but played A
            games=games,
            sheet_name="B161",
        )

        sos = calculate_sos(team)
        assert sos.never_played_at_grade is True
        assert sos.grade_coverage is False


# === Team Metrics Tests ===


class TestTeamMetrics:
    """Tests for team metrics calculations."""

    @pytest.fixture
    def dominant_team(self) -> TeamSeason:
        """Create a dominant team with blowout wins."""
        games = [
            GameResult(
                team_name="Dominant Team",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=70,
                score_against=40,
                margin=30,
                result=ResultType.WON,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        return TeamSeason(
            team_name="Dominant Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

    @pytest.fixture
    def struggling_team(self) -> TeamSeason:
        """Create a struggling team with blowout losses."""
        games = [
            GameResult(
                team_name="Struggling Team",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=30,
                score_against=55,
                margin=-25,
                result=ResultType.LOST,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        return TeamSeason(
            team_name="Struggling Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

    def test_blowout_detection(self, dominant_team: TeamSeason):
        """Test blowout win detection."""
        metrics = calculate_team_metrics(dominant_team)

        assert metrics.blowout_wins == 4
        assert metrics.blowout_losses == 0
        assert metrics.is_dominant is True

    def test_struggling_detection(self, struggling_team: TeamSeason):
        """Test struggling team detection."""
        metrics = calculate_team_metrics(struggling_team)

        assert metrics.blowout_losses == 4
        assert metrics.blowout_wins == 0
        assert metrics.is_struggling is True

    def test_win_rate_calculation(self, dominant_team: TeamSeason):
        """Test win rate calculation."""
        metrics = calculate_team_metrics(dominant_team)

        assert metrics.wins == 4
        assert metrics.losses == 0
        assert metrics.win_rate == 100.0

    def test_margin_calculation(self, dominant_team: TeamSeason):
        """Test margin calculations."""
        metrics = calculate_team_metrics(dominant_team)

        assert metrics.total_margin == 120  # 4 * 30
        assert metrics.avg_margin == 30.0


# === Transitive Analysis Tests ===


class TestTransitiveAnalysis:
    """Tests for transitive variance detection."""

    def test_transitive_link(self):
        """Test TransitiveLink creation."""
        link = TransitiveLink(
            winner="Team A",
            loser="Team B",
            margin=40,
            round_num=1,
        )

        assert str(link) == "Team A def Team B by 40"

    def test_transitive_chain(self):
        """Test TransitiveChain properties."""
        links = [
            TransitiveLink(winner="A", loser="B", margin=40, round_num=1),
            TransitiveLink(winner="B", loser="C", margin=30, round_num=2),
        ]

        chain = TransitiveChain(links=links, start_team="A", end_team="C")

        assert chain.implied_variance == 70
        assert chain.chain_length == 2
        assert chain.is_significant is True

    def test_find_transitive_chains(self):
        """Test chain detection with multiple teams."""
        # Create teams with chain: A beats B (+40), B beats C (+30)
        team_a = TeamSeason(
            team_name="Team A",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.A,
            games=[
                GameResult(
                    team_name="Team A",
                    opponent_name="Team B",
                    opponent_grade=Grade.B1,
                    score_for=80,
                    score_against=40,
                    margin=40,
                    result=ResultType.WON,
                    round_num=1,
                )
            ],
            sheet_name="B161",
        )

        team_b = TeamSeason(
            team_name="Team B",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=[
                GameResult(
                    team_name="Team B",
                    opponent_name="Team C",
                    opponent_grade=Grade.C1,
                    score_for=70,
                    score_against=40,
                    margin=30,
                    result=ResultType.WON,
                    round_num=2,
                )
            ],
            sheet_name="B161",
        )

        team_c = TeamSeason(
            team_name="Team C",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.C1,
            games=[],
            sheet_name="B161",
        )

        all_teams = [team_a, team_b, team_c]
        chains = find_transitive_chains("Team A", all_teams, max_depth=2, min_margin=15)

        # Should find chain: A → B → C
        assert len(chains) >= 1
        significant_chains = [c for c in chains if c.implied_variance >= 40]
        assert len(significant_chains) >= 1


# === Recommendation Engine Tests ===


class TestRecommendationEngine:
    """Tests for recommendation generation."""

    @pytest.fixture
    def engine(self) -> RecommendationEngine:
        """Create recommendation engine."""
        return RecommendationEngine()

    @pytest.fixture
    def promote_candidate(self) -> TeamSeason:
        """Create a team that should be promoted."""
        games = [
            GameResult(
                team_name="Promote Me",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=70,
                score_against=45,
                margin=25,
                result=ResultType.WON,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        return TeamSeason(
            team_name="Promote Me",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

    @pytest.fixture
    def demote_candidate(self) -> TeamSeason:
        """Create a team that should be demoted."""
        games = [
            GameResult(
                team_name="Demote Me",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=35,
                score_against=60,
                margin=-25,
                result=ResultType.LOST,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        return TeamSeason(
            team_name="Demote Me",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

    def test_promote_recommendation(
        self,
        engine: RecommendationEngine,
        promote_candidate: TeamSeason,
    ):
        """Test fallback promotion recommendation without cohort context."""
        rec = engine.generate_recommendation(promote_candidate)

        assert rec.recommendation_type == RecommendationType.PROMOTE
        assert rec.recommended_grade == "AR"
        assert rec.confidence in (Confidence.HIGH, Confidence.MEDIUM)

    def test_promote_recommendation_uses_next_existing_cohort_grade(
        self,
        engine: RecommendationEngine,
        promote_candidate: TeamSeason,
    ):
        """Promotion should skip missing cohort grades like AR when absent."""
        promote_candidate = promote_candidate.model_copy(
            update={"team_name": "Jets U10 Boys 2", "age_group": 10}
        )
        cohort_teams = [
            promote_candidate,
            TeamSeason(
                team_name="Jets U10 Boys 1",
                gender=Gender.BOYS,
                age_group=10,
                division=1,
                assigned_grade=Grade.A,
                games=promote_candidate.games,
                sheet_name="B101",
            ),
            TeamSeason(
                team_name="Jets U10 Boys 3",
                gender=Gender.BOYS,
                age_group=10,
                division=2,
                assigned_grade=Grade.B2,
                games=promote_candidate.games,
                sheet_name="B102",
            ),
        ]

        rec = engine.generate_recommendation(promote_candidate, cohort_teams)

        assert rec.recommendation_type == RecommendationType.PROMOTE
        assert rec.recommended_grade == "A"


class TestPowerRatings:
    """Tests for power-rating grade suggestions."""

    def test_suggested_grade_uses_existing_cohort_grades(self):
        """Suggested grades should skip missing cohort grades like AR."""
        dominant_games = [
            GameResult(
                team_name="Jets U10 Boys 2",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=70,
                score_against=45,
                margin=25,
                result=ResultType.WON,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        teams = [
            TeamSeason(
                team_name="Jets U10 Boys 2",
                gender=Gender.BOYS,
                age_group=10,
                division=1,
                assigned_grade=Grade.B1,
                games=dominant_games,
                sheet_name="B101",
            ),
            TeamSeason(
                team_name="Jets U10 Boys 1",
                gender=Gender.BOYS,
                age_group=10,
                division=1,
                assigned_grade=Grade.A,
                games=[],
                sheet_name="B101",
            ),
            TeamSeason(
                team_name="Jets U10 Boys 3",
                gender=Gender.BOYS,
                age_group=10,
                division=2,
                assigned_grade=Grade.B2,
                games=[],
                sheet_name="B102",
            ),
        ]

        ratings = calculate_power_ratings(teams)

        assert ratings["Jets U10 Boys 2"].suggested_grade == Grade.A

    def test_demote_recommendation(
        self,
        engine: RecommendationEngine,
        demote_candidate: TeamSeason,
    ):
        """Test demotion recommendation."""
        rec = engine.generate_recommendation(demote_candidate)

        assert rec.recommendation_type == RecommendationType.DEMOTE
        assert rec.recommended_grade == "B2"
        assert rec.confidence in (Confidence.HIGH, Confidence.MEDIUM)

    def test_insufficient_data(self, engine: RecommendationEngine):
        """Test handling of insufficient data."""
        team = TeamSeason(
            team_name="New Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=[
                GameResult(
                    team_name="New Team",
                    opponent_name="Opp 1",
                    opponent_grade=Grade.B1,
                    score_for=50,
                    score_against=45,
                    margin=5,
                    result=ResultType.WON,
                    round_num=1,
                )
            ],
            sheet_name="B161",
        )

        rec = engine.generate_recommendation(team)

        assert rec.recommendation_type == RecommendationType.MONITOR
        assert rec.confidence == Confidence.LOW

    def test_recommendation_has_evidence(
        self,
        engine: RecommendationEngine,
        promote_candidate: TeamSeason,
    ):
        """Test that recommendations include evidence."""
        rec = engine.generate_recommendation(promote_candidate)

        assert len(rec.evidence) > 0
        assert rec.explanation != ""
        assert rec.team_name == "Promote Me"

    def test_no_change_for_balanced_team(self, engine: RecommendationEngine):
        """Test no change for appropriately graded team."""
        games = [
            GameResult(
                team_name="Balanced Team",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=45 + (i % 2) * 5,
                score_against=45 - (i % 2) * 5,
                margin=(i % 2) * 10 - 5,
                result=ResultType.WON if i % 2 else ResultType.LOST,
                round_num=i,
            )
            for i in range(1, 6)
        ]

        team = TeamSeason(
            team_name="Balanced Team",
            gender=Gender.BOYS,
            age_group=16,
            division=1,
            assigned_grade=Grade.B1,
            games=games,
            sheet_name="B161",
        )

        rec = engine.generate_recommendation(team)

        assert rec.recommendation_type == RecommendationType.NO_CHANGE
        assert rec.confidence == Confidence.HIGH


class TestPowerRatings:
    """Tests for power-rating grade suggestions."""

    def test_suggested_grade_uses_existing_cohort_grades(self):
        """Suggested grades should skip missing cohort grades like AR."""
        dominant_games = [
            GameResult(
                team_name="Jets U10 Boys 2",
                opponent_name=f"Opp {i}",
                opponent_grade=Grade.B1,
                score_for=70,
                score_against=45,
                margin=25,
                result=ResultType.WON,
                round_num=i,
            )
            for i in range(1, 5)
        ]

        teams = [
            TeamSeason(
                team_name="Jets U10 Boys 2",
                gender=Gender.BOYS,
                age_group=10,
                division=1,
                assigned_grade=Grade.B1,
                games=dominant_games,
                sheet_name="B101",
            ),
            TeamSeason(
                team_name="Jets U10 Boys 1",
                gender=Gender.BOYS,
                age_group=10,
                division=1,
                assigned_grade=Grade.A,
                games=[],
                sheet_name="B101",
            ),
            TeamSeason(
                team_name="Jets U10 Boys 3",
                gender=Gender.BOYS,
                age_group=10,
                division=2,
                assigned_grade=Grade.B2,
                games=[],
                sheet_name="B102",
            ),
        ]

        ratings = calculate_power_ratings(teams)

        assert ratings["Jets U10 Boys 2"].suggested_grade == Grade.A
