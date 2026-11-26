from collections.abc import Callable, Mapping, Sequence
from typing import TypedDict


SongID = str


class UploadedSong(TypedDict):
    name: str
    path: str
    duration: float
    format: str


# An optimizer adapter receives songs keyed by their session upload IDs.
# Return every supplied ID once, in playback order (a list or tuple).
OrderProvider = Callable[[Mapping[str, UploadedSong]], Sequence[str]]
optimizer_provider: OrderProvider | None = None


def mock_song_order(songs_by_id: Mapping[str, UploadedSong]) -> list[str]:
    """Reverse the provided order to exercise integration without audio analysis."""
    return list(reversed(songs_by_id))


def validate_song_order(
    song_order: Sequence[str], songs_by_id: Mapping[str, UploadedSong]
) -> list[str]:
    if not isinstance(song_order, Sequence) or isinstance(song_order, (str, bytes, bytearray)):
        raise ValueError("곡 순서는 곡 ID의 목록이어야 합니다.")

    order = list(song_order)
    if any(not isinstance(song_id, str) for song_id in order):
        raise ValueError("곡 ID는 문자열이어야 합니다.")
    if len(set(order)) != len(order):
        raise ValueError("곡 순서에 중복 ID가 있습니다.")
    if set(order) != set(songs_by_id):
        raise ValueError("곡 순서에는 현재 업로드한 유효한 곡의 ID가 모두 포함되어야 합니다.")
    return order
