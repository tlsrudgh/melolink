"""Validate and render plans through the existing sequential FFmpeg mixer."""

from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from typing import Protocol

from mixer import create_mix
from song_order import SongID, UploadedSong
from transition_planner import PLAN_VERSION, TransitionPlan


class MixEngine(Protocol):
    def render(
        self, plan: TransitionPlan, catalog: Mapping[SongID, UploadedSong], output: Path,
    ) -> Path: ...


class FFmpegMixEngine:
    supported_effects = frozenset({"crossfade"})

    def render(
        self, plan: TransitionPlan, catalog: Mapping[SongID, UploadedSong], output: Path,
    ) -> Path:
        if plan.version != PLAN_VERSION:
            raise ValueError("지원하지 않는 전환 계획 버전입니다.")
        if any(step.effect not in self.supported_effects for step in plan.transitions):
            raise ValueError("FFmpeg 내보내기가 지원하지 않는 전환 효과입니다.")
        pairs = tuple(zip(plan.order, plan.order[1:]))
        if len(set(plan.order)) != len(plan.order) or not pairs or pairs != tuple(
            (step.outgoing, step.incoming) for step in plan.transitions
        ):
            raise ValueError("전환 계획과 곡 순서가 일치하지 않습니다.")
        seconds = plan.transitions[0].seconds
        if not isfinite(seconds) or seconds <= 0:
            raise ValueError("크로스페이드 길이는 0초보다 커야 합니다.")
        if any(step.seconds != seconds for step in plan.transitions):
            raise ValueError("FFmpeg 내보내기는 모든 전환에 같은 길이를 사용합니다.")
        if any(song_id not in catalog for song_id in plan.order):
            raise ValueError("전환 계획의 곡을 찾을 수 없습니다.")
        return create_mix([catalog[song_id]["path"] for song_id in plan.order], seconds, str(output))
