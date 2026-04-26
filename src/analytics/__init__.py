"""Analytics module for advanced basketball grading analysis.

This module provides:
- Historical season comparison and trend analysis
- Cross-season performance tracking
- Club-level aggregate analytics
"""

from src.analytics.historical import (
    ClubHistory,
    HistoricalAnalyzer,
    SeasonSnapshot,
    TeamHistory,
    compare_seasons,
)

__all__ = [
    "ClubHistory",
    "HistoricalAnalyzer",
    "SeasonSnapshot",
    "TeamHistory",
    "compare_seasons",
]
