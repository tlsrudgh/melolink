"""Build an engine-independent plan from a playlist and its analysis."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from song_analysis import SongAnalysis
from song_order import SongID

PLAN_VERSION = 1


@dataclass(frozen=True)
class MixSettings:
    crossfade_seconds: float


@dataclass(frozen=True)
class Transition:
    outgoing: SongID
    incoming: SongID
    seconds: float
    effect: str = "crossfade"


@dataclass(frozen=True)
class TransitionPlan:
    order: tuple[SongID, ...]
    transitions: tuple[Transition, ...]
    version: int = PLAN_VERSION


def plan_transitions(
    order: Sequence[SongID], analysis: Mapping[SongID, SongAnalysis], settings: MixSettings,
) -> TransitionPlan:
    seconds = settings.crossfade_seconds
    if not isfinite(seconds) or seconds <= 0:
        raise ValueError("크로스페이드 길이는 0초보다 커야 합니다.")
    if len(order) < 2 or len(set(order)) != len(order):
        raise ValueError("서로 다른 곡 ID가 2개 이상 필요합니다.")
    for song_id in order:
        song = analysis.get(song_id)
        if song is None or song.song_id != song_id:
            raise ValueError(f"곡 분석 정보를 찾을 수 없습니다. ({song_id})")
        if not isfinite(song.duration) or song.duration <= seconds:
            raise ValueError("모든 곡의 재생 시간은 크로스페이드 길이보다 길어야 합니다.")
    transitions = tuple(Transition(a, b, seconds) for a, b in zip(order, order[1:]))
    return TransitionPlan(tuple(order), transitions)
