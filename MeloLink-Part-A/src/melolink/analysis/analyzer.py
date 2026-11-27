"""Extract JSON-compatible music features from local MP3 and WAV files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import librosa
import numpy as np

SUPPORTED_EXTENSIONS = {".mp3", ".wav"}
DEFAULT_SEGMENT_SECONDS = 10.0
DEFAULT_SAMPLE_RATE = 22_050
DEFAULT_MFCC_COUNT = 13


class AudioAnalysisError(Exception):
    """Base exception for audio analysis failures."""


class UnsupportedAudioFormatError(AudioAnalysisError):
    """Raised when a file extension is not supported."""


class InvalidAudioFileError(AudioAnalysisError):
    """Raised when a path is missing or audio decoding fails."""


def _file_sha256(path: Path) -> str:
    """Return a content-based identifier that is stable across computers."""
    digest = hashlib.sha256()
    with path.open("rb") as audio_file:
        for chunk in iter(lambda: audio_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(value: float | np.floating[Any]) -> float:
    """Convert a NumPy scalar to a finite built-in float for strict JSON."""
    converted = float(value)
    return converted if np.isfinite(converted) else 0.0


def _float_list(values: np.ndarray) -> list[float]:
    return [_finite_float(value) for value in np.asarray(values).ravel()]


def _analyze_region(y: np.ndarray, sample_rate: int, n_mfcc: int) -> dict[str, Any]:
    """Analyze one non-empty waveform region and return JSON-safe features."""
    # Centering permits analysis of clips shorter than the normal FFT window.
    rms = librosa.feature.rms(y=y, center=True)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sample_rate, n_mfcc=n_mfcc)
    onset = librosa.onset.onset_strength(y=y, sr=sample_rate)
    tempo = librosa.feature.tempo(onset_envelope=onset, sr=sample_rate)

    return {
        "duration_seconds": _finite_float(len(y) / sample_rate),
        "tempo_bpm": _finite_float(tempo[0]) if tempo.size else 0.0,
        "rms": {
            "mean": _finite_float(np.mean(rms)),
            "std": _finite_float(np.std(rms)),
            "values": _float_list(rms),
        },
        "mfcc": {
            "mean": _float_list(np.mean(mfcc, axis=1)),
            "std": _float_list(np.std(mfcc, axis=1)),
        },
        "rhythm": {
            "onset_strength_mean": _finite_float(np.mean(onset)) if onset.size else 0.0,
            "onset_strength_std": _finite_float(np.std(onset)) if onset.size else 0.0,
            "onset_strength": _float_list(onset),
        },
    }


def analyze_audio(
    file_path: str | Path,
    *,
    segment_seconds: float = DEFAULT_SEGMENT_SECONDS,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    n_mfcc: int = DEFAULT_MFCC_COUNT,
) -> dict[str, Any]:
    """Analyze a WAV/MP3 file, including its start and end regions.

    The returned dictionary contains only built-in JSON-compatible values and
    intentionally excludes machine-specific absolute paths.
    """
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise InvalidAudioFileError(f"Audio file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedAudioFormatError(
            f"Unsupported audio format '{path.suffix}'. Supported: MP3, WAV"
        )
    if segment_seconds <= 0:
        raise ValueError("segment_seconds must be greater than 0")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than 0")
    if n_mfcc <= 0:
        raise ValueError("n_mfcc must be greater than 0")

    try:
        waveform, loaded_sample_rate = librosa.load(
            path, sr=sample_rate, mono=True, dtype=np.float32
        )
    except Exception as exc:
        raise InvalidAudioFileError(f"Could not decode audio file: {path.name}") from exc

    if waveform.size == 0:
        raise InvalidAudioFileError(f"Audio file is empty: {path.name}")

    segment_samples = min(waveform.size, max(1, round(segment_seconds * loaded_sample_rate)))
    full_features = _analyze_region(waveform, loaded_sample_rate, n_mfcc)
    start_features = _analyze_region(waveform[:segment_samples], loaded_sample_rate, n_mfcc)
    end_features = _analyze_region(waveform[-segment_samples:], loaded_sample_rate, n_mfcc)

    return {
        "schema_version": "1.0",
        "track_id": _file_sha256(path),
        "file_name": path.name,
        "duration_seconds": _finite_float(len(waveform) / loaded_sample_rate),
        "sample_rate_hz": int(loaded_sample_rate),
        "bpm": full_features["tempo_bpm"],
        "segment_seconds_requested": _finite_float(segment_seconds),
        "full": full_features,
        "start": start_features,
        "end": end_features,
    }


def main() -> None:
    """Command-line entry point for easy manual analysis."""
    parser = argparse.ArgumentParser(description="Analyze a local MP3 or WAV file")
    parser.add_argument("audio_file", type=Path)
    parser.add_argument("--segment-seconds", type=float, default=DEFAULT_SEGMENT_SECONDS)
    args = parser.parse_args()
    result = analyze_audio(args.audio_file, segment_seconds=args.segment_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

