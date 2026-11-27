"""Directional transition scoring and open playlist ordering."""

from math import exp, log10
from typing import Any, Sequence

import numpy as np

_WEIGHTS = {"tempo": 0.35, "rms": 0.25, "mfcc": 0.25, "onset": 0.15}
_EXACT_LIMIT = 12


def score_transition(previous: dict[str, Any], following: dict[str, Any]) -> dict[str, Any]:
    """Compare the previous track's end with the following track's start."""
    end, start = previous["end"], following["start"]
    bpm_a, bpm_b = end["tempo_bpm"], start["tempo_bpm"]
    rms_a, rms_b = end["rms"]["mean"], start["rms"]["mean"]
    onset_a = end["rhythm"]["onset_strength_mean"]
    onset_b = start["rhythm"]["onset_strength_mean"]
    mfcc_a, mfcc_b = np.asarray(end["mfcc"]["mean"]), np.asarray(start["mfcc"]["mean"])
    if mfcc_a.shape != mfcc_b.shape:
        raise ValueError("Analyze all tracks with the same n_mfcc")
    if previous["sample_rate_hz"] != following["sample_rate_hz"]:
        raise ValueError("Analyze all tracks with the same sample_rate")

    # Compare loudness on a dB scale and omit tempo for regions without onsets.
    rms_gap_db = abs(20 * log10(max(rms_a, 1e-6) / max(rms_b, 1e-6)))
    # Leave the energy-dependent first coefficient to RMS when possible.
    first = 1 if mfcc_a.size > 1 else 0
    mfcc_gap = float(np.sqrt(np.mean((mfcc_a[first:] - mfcc_b[first:]) ** 2)))
    components = {
        "rms": exp(-rms_gap_db / 12),
        "mfcc": exp(-mfcc_gap / 30),
        "onset": 1 - abs(onset_a - onset_b) / max(onset_a, onset_b, 1e-9),
    }
    if min(bpm_a, bpm_b, onset_a, onset_b) > 0:
        components["tempo"] = exp(-abs(bpm_a - bpm_b) / 20)
    score = sum(_WEIGHTS[k] * v for k, v in components.items())
    return {"score": score / sum(_WEIGHTS[k] for k in components), "components": components}


def _exact_order(scores: list[list[float]]) -> tuple[int, ...]:
    # For each visited set and final track, keep its best partial path.
    count = len(scores)
    states: list[dict[int, tuple[float, tuple[int, ...]]]] = [
        {} for _ in range(1 << count)
    ]
    for index in range(count):
        states[1 << index][index] = (0.0, (index,))
    for mask, paths in enumerate(states):
        for last, (total, path) in paths.items():
            for index in range(count):
                bit = 1 << index
                if mask & bit:
                    continue
                target = states[mask | bit]
                candidate = total + scores[last][index]
                if index not in target or candidate > target[index][0]:
                    target[index] = (candidate, (*path, index))
    return max(states[-1].values(), key=lambda item: item[0])[1]


def _greedy_order(scores: list[list[float]]) -> tuple[int, ...]:
    def from_start(start: int) -> tuple[int, ...]:
        path = [start]
        remaining = set(range(len(scores))) - {start}
        while remaining:
            next_index = max(remaining, key=lambda index: (scores[path[-1]][index], -index))
            path.append(next_index)
            remaining.remove(next_index)
        return tuple(path)

    return max(
        (from_start(index) for index in range(len(scores))),
        key=lambda path: sum(scores[a][b] for a, b in zip(path, path[1:])),
    )


def recommend_playlist(tracks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Return input indices and transition details in recommended playback order."""
    count = len(tracks)
    transitions = {
        (a, b): score_transition(tracks[a], tracks[b])
        for a in range(count) for b in range(count) if a != b
    }
    scores = [
        [transitions[a, b]["score"] if a != b else 0.0 for b in range(count)]
        for a in range(count)
    ]
    exact = count <= _EXACT_LIMIT
    order = (_exact_order(scores) if exact else _greedy_order(scores)) if count else ()
    edges = [
        {"from_index": a, "to_index": b, **transitions[a, b]}
        for a, b in zip(order, order[1:])
    ]
    return {
        "schema_version": "1.0",
        "method": "exact" if exact else "greedy",
        "track_indices": list(order),
        "track_ids": [tracks[index]["track_id"] for index in order],
        "total_score": sum((edge["score"] for edge in edges), 0.0),
        "transitions": edges,
    }
