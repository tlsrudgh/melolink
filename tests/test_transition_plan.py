import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mix_engine import FFmpegMixEngine
from song_analysis import SongAnalysis

from transition_planner import MixSettings, Transition, plan_transitions


class TransitionPlanTests(unittest.TestCase):
    def test_order_and_duration(self):
        analysis = {song_id: SongAnalysis(song_id, 6) for song_id in ("a", "b", "c")}
        plan = plan_transitions(["c", "a", "b"], analysis, MixSettings(2))
        self.assertEqual(plan.transitions, (Transition("c", "a", 2), Transition("a", "b", 2)))
        for order, duration in ((["a", "missing"], 2), (["a", "a"], 2), (["a", "b"], 6),
                                (["a", "b"], float("nan"))):
            with self.subTest(order=order, duration=duration), self.assertRaises(ValueError):
                plan_transitions(order, analysis, MixSettings(duration))

    def test_renderer_rejects_unsupported_plan_before_ffmpeg(self):
        analysis = {song_id: SongAnalysis(song_id, 6) for song_id in ("a", "b")}
        plan = plan_transitions(["a", "b"], analysis, MixSettings(2))
        with patch("mix_engine.create_mix") as render:
            for invalid in (replace(plan, version=99),
                            replace(plan, transitions=(Transition("a", "b", 2, "eq"),))):
                with self.assertRaises(ValueError):
                    FFmpegMixEngine().render(invalid, {}, Path("unused.wav"))
            render.assert_not_called()
