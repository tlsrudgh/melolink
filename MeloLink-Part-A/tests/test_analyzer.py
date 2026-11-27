from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from melolink.analysis import (
    InvalidAudioFileError,
    UnsupportedAudioFormatError,
    analyze_audio,
)
from conftest import write_synthetic_wav


def test_analyze_wav_returns_expected_structure(wav_file: Path) -> None:
    result = analyze_audio(wav_file)

    assert result["schema_version"] == "1.0"
    assert result["file_name"] == "synthetic.wav"
    assert len(result["track_id"]) == 64
    assert result["duration_seconds"] == pytest.approx(1.5, abs=0.01)
    assert isinstance(result["bpm"], float)
    for region_name in ("full", "start", "end"):
        region = result[region_name]
        assert set(region) == {"duration_seconds", "tempo_bpm", "rms", "mfcc", "rhythm"}
        assert len(region["mfcc"]["mean"]) == 13
        assert len(region["mfcc"]["std"]) == 13
        assert region["rms"]["values"]
        assert "onset_strength" in region["rhythm"]

    # Strict serialization rejects NaN/Infinity and proves JSON compatibility.
    json.dumps(result, allow_nan=False)


def test_short_audio_uses_available_samples(tmp_path: Path) -> None:
    short_file = write_synthetic_wav(tmp_path / "short.wav", duration=0.2)
    result = analyze_audio(short_file, segment_seconds=10.0)

    assert result["start"]["duration_seconds"] == pytest.approx(0.2, abs=0.01)
    assert result["end"]["duration_seconds"] == pytest.approx(0.2, abs=0.01)


def test_missing_path_raises_domain_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidAudioFileError, match="does not exist"):
        analyze_audio(tmp_path / "missing.wav")


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    unsupported = tmp_path / "audio.flac"
    unsupported.write_bytes(b"not audio")
    with pytest.raises(UnsupportedAudioFormatError, match="Unsupported"):
        analyze_audio(unsupported)


def test_invalid_wav_is_reported(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.wav"
    invalid.write_bytes(b"not audio")
    with pytest.raises(InvalidAudioFileError, match="Could not decode"):
        analyze_audio(invalid)


def test_mp3_when_ffmpeg_is_available(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is not installed, so the MP3 decoder test is unavailable")

    wav_path = write_synthetic_wav(tmp_path / "source.wav", duration=1.0)
    mp3_path = tmp_path / "synthetic.mp3"
    conversion = subprocess.run(
        [ffmpeg, "-loglevel", "error", "-y", "-i", str(wav_path), str(mp3_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if conversion.returncode != 0:
        pytest.skip(f"Installed FFmpeg cannot encode MP3: {conversion.stderr.strip()}")

    result = analyze_audio(mp3_path)
    assert result["file_name"] == "synthetic.mp3"
    assert result["duration_seconds"] == pytest.approx(1.0, abs=0.1)


@pytest.mark.parametrize("value", [0, -1])
def test_segment_length_must_be_positive(wav_file: Path, value: float) -> None:
    with pytest.raises(ValueError, match="segment_seconds"):
        analyze_audio(wav_file, segment_seconds=value)

