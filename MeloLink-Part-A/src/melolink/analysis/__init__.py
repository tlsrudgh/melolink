"""Public API for MeloLink's Part A audio analysis."""

from melolink.analysis.analyzer import (
    AudioAnalysisError,
    InvalidAudioFileError,
    UnsupportedAudioFormatError,
    analyze_audio,
)

from melolink.analysis.playlist import recommend_playlist, score_transition

__all__ = [
    "recommend_playlist",
    "score_transition",
    "AudioAnalysisError",
    "InvalidAudioFileError",
    "UnsupportedAudioFormatError",
    "analyze_audio",
]

