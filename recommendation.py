"""Contract for a playlist recommender consuming shared analysis."""

from collections.abc import Callable, Mapping, Sequence

from song_analysis import SongAnalysis
from song_order import SongID

# Mapping iteration follows the current playlist order. Return each ID once.
RecommendationProvider = Callable[[Mapping[SongID, SongAnalysis]], Sequence[SongID]]
recommendation_provider: RecommendationProvider | None = None
