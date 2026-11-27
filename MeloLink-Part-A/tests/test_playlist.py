import itertools
import json

import pytest

from melolink.analysis import analyze_audio, recommend_playlist, score_transition


def track(start, end):
    def region(value):
        return {
            "tempo_bpm": 80 + value * 20,
            "rms": {"mean": 0.1 * value},
            "mfcc": {"mean": [0, value * 15]},
            "rhythm": {"onset_strength_mean": value},
        }

    return {"track_id": "duplicate", "sample_rate_hz": 22050,
            "start": region(start), "end": region(end)}


def test_direction_and_identical_regions():
    a, b = track(1, 2), track(2, 3)
    assert score_transition(a, b)["score"] == pytest.approx(1)
    assert score_transition(b, a)["score"] < 1
    assert "tempo" not in score_transition(track(0, 0), a)["components"]


def test_exact_order_matches_brute_force():
    tracks = [track(3, 4), track(1, 2), track(4, 5), track(2, 3)]
    result = recommend_playlist(tracks)
    expected = max(
        sum(score_transition(a, b)["score"] for a, b in zip(order, order[1:]))
        for order in itertools.permutations(tracks)
    )
    assert result["total_score"] == pytest.approx(expected)
    assert result["track_indices"] == [1, 3, 0, 2]
    assert len(result["track_ids"]) == 4
    json.dumps(result, allow_nan=False)


def test_large_playlist_includes_each_input_once():
    result = recommend_playlist([track(i, i + 1) for i in range(13)])
    assert result["method"] == "greedy"
    assert sorted(result["track_indices"]) == list(range(13))
    assert len(result["transitions"]) == 12


def test_empty_and_real_analysis_result(wav_file):
    assert recommend_playlist([])["track_indices"] == []
    analyzed = analyze_audio(wav_file)
    assert recommend_playlist([analyzed])["transitions"] == []
    assert recommend_playlist([analyzed, analyzed])["total_score"] == pytest.approx(1)
