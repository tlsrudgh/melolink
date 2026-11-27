from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest


def write_synthetic_wav(path: Path, duration: float, sample_rate: int = 22_050) -> Path:
    """Create a copyright-free sine wave in pytest's temporary directory."""
    times = np.arange(round(duration * sample_rate), dtype=np.float64) / sample_rate
    signal = 0.35 * np.sin(2 * np.pi * 440.0 * times)
    pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32767)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return path


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    return write_synthetic_wav(tmp_path / "synthetic.wav", duration=1.5)

