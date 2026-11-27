"""Contract for a playlist recommender consuming shared analysis."""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import sys

from song_analysis import SongAnalysis
from song_order import SongID, UploadedSong

# Mapping iteration follows the current playlist order. Return each ID once.
RecommendationProvider = Callable[[Mapping[SongID, SongAnalysis]], Sequence[SongID]]
recommendation_provider: RecommendationProvider | None = None

# Part A is distributed alongside the app with its own src-layout.
_PART_A_SRC = str(Path(__file__).resolve().parent / "MeloLink-Part-A" / "src")
if _PART_A_SRC not in sys.path:
    sys.path.insert(0, _PART_A_SRC)


def recommend_uploaded_songs(songs: Mapping[SongID, UploadedSong], cache: dict) -> list[SongID]:
    from melolink.analysis import AudioAnalysisError, analyze_audio, recommend_playlist

    ids = list(songs)
    tracks = []
    for song_id in ids:
        song = songs[song_id]
        # The uploader assigns one immutable path per distinct file in this session.
        path = song["path"]
        if path not in cache:
            try:
                analysis = analyze_audio(path)
            except (AudioAnalysisError, OSError) as error:
                raise ValueError(f'{song["name"]} 분석에 실패했습니다. {error}') from error
            cache[path] = {key: analysis[key] for key in ("track_id", "sample_rate_hz", "start", "end")}
        tracks.append(cache[path])
    indices = recommend_playlist(tracks)["track_indices"]
    if any(type(i) is not int for i in indices) or sorted(indices) != list(range(len(ids))):
        raise ValueError("추천 결과의 곡 번호가 업로드 목록과 일치하지 않습니다.")
    return [ids[i] for i in indices]
