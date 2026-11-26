"""Versioned audio features shared by recommendation and transition planning."""

import subprocess
from array import array
from dataclasses import dataclass, replace
from math import sqrt
from sys import byteorder

from song_order import SongID, UploadedSong

ANALYSIS_VERSION = 1
SAMPLE_RATE = 8000


@dataclass(frozen=True)
class AnalysisSettings:
    rms_window_seconds: int = 5


@dataclass(frozen=True)
class SegmentFeatures:
    start_seconds: float
    end_seconds: float
    rms: float


@dataclass(frozen=True)
class SongAnalysis:
    song_id: SongID
    duration: float
    segments: tuple[SegmentFeatures, ...] = ()
    beat_times: tuple[float, ...] | None = None
    analysis_version: int = ANALYSIS_VERSION


def analyze_song(song_id: SongID, song: UploadedSong, settings: AnalysisSettings) -> SongAnalysis:
    if settings.rms_window_seconds <= 0:
        raise ValueError("RMS 분석 구간은 0초보다 길어야 합니다.")
    command = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", song["path"],
        "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1",
    ]
    chunk_size = SAMPLE_RATE * settings.rms_window_seconds * 2
    segments = []
    frames = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        assert process.stdout is not None
        while chunk := process.stdout.read(chunk_size):
            samples = array("h")
            samples.frombytes(chunk)
            if byteorder == "big":
                samples.byteswap()
            end = frames + len(samples)
            rms = sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
            segments.append(SegmentFeatures(frames / SAMPLE_RATE, end / SAMPLE_RATE, rms))
            frames = end
        if process.wait() != 0 or not segments:
            raise ValueError(f'{song["name"]} 파일의 RMS를 분석하지 못했습니다.')
    return SongAnalysis(song_id, song["duration"], tuple(segments))


class AnalysisCache:
    def __init__(self) -> None:
        self._results: dict[tuple[tuple[str, bytes], int, AnalysisSettings], SongAnalysis] = {}

    def get(
        self, song_id: SongID, song: UploadedSong, content_key: tuple[str, bytes],
        settings: AnalysisSettings, *, analyze: bool = True,
    ) -> SongAnalysis:
        key = (content_key, ANALYSIS_VERSION, settings)
        if key not in self._results:
            if not analyze:
                return SongAnalysis(song_id, song["duration"])
            self._results[key] = analyze_song(song_id, song, settings)
        return replace(self._results[key], song_id=song_id)
