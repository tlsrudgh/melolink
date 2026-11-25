import shutil
import struct
import unittest
import wave
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import song_order

APP = Path(__file__).resolve().parents[1] / "app.py"


def audio_upload(song_id, sample):
    upload = BytesIO()
    with wave.open(upload, "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(struct.pack("<h", sample) * 48000)
    upload.name = "same-name.wav"
    upload.file_id = song_id
    return upload


class SongOrderValidationTests(unittest.TestCase):
    def test_rejects_invalid_orders(self):
        songs = {"a": {}, "b": {}}
        for order in (None, "ab", b"ab", {"a", "b"}, ["a"], ["a", "a"], ["a", "c"], ["a", 1]):
            with self.subTest(order=order), self.assertRaises(ValueError):
                song_order.validate_song_order(order, songs)
        self.assertEqual(song_order.validate_song_order(("b", "a"), songs), ["b", "a"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class SongOrderAppTests(unittest.TestCase):
    def setUp(self):
        self.uploads = [audio_upload("a", 1000), audio_upload("b", 2000)]
        uploader = patch("streamlit.file_uploader", return_value=self.uploads)
        uploader.start()
        self.addCleanup(uploader.stop)
        self.app = AppTest.from_file(str(APP)).run()
        self.addCleanup(self.app.session_state.work_dir.cleanup)
        self.assertFalse(self.app.exception)

    def click(self, label):
        button = next(button for button in self.app.button if button.label == label)
        button.click().run()
        self.assertFalse(self.app.exception)

    def check_mix(self, first_sample, last_sample):
        self.click("믹스 만들기")
        output = Path(self.app.session_state.work_dir.name) / "melolink_mix.wav"
        with wave.open(str(output), "rb") as audio:
            self.assertEqual(audio.getnframes(), 56000)
            self.assertEqual(struct.unpack("<h", audio.readframes(1))[0], first_sample)
            audio.setpos(audio.getnframes() - 1)
            self.assertEqual(struct.unpack("<h", audio.readframes(1))[0], last_sample)
        self.assertTrue(self.app.get("audio"))
        self.assertTrue(self.app.get("download_button"))

    def test_mock_order_manual_adjustment_and_upload_changes(self):
        self.check_mix(1000, 2000)
        self.click("테스트용 순서 적용")
        self.assertEqual(self.app.session_state.song_order, ["b", "a"])
        self.assertIn("테스트용", self.app.success[0].value)
        self.assertFalse(self.app.get("download_button"))
        self.check_mix(2000, 1000)

        self.app.button(key="up_a").click().run()
        self.assertEqual(self.app.session_state.song_order, ["a", "b"])
        self.assertFalse(self.app.get("download_button"))
        self.check_mix(1000, 2000)

        self.uploads.pop(0)
        self.app.run()
        self.assertEqual(self.app.session_state.song_order, ["b"])
        self.assertFalse(self.app.get("download_button"))
        self.assertTrue(all(button.disabled for button in self.app.button))

    def test_valid_provider_output_is_applied_and_no_change_keeps_mix(self):
        def provider(songs):
            self.assertEqual(songs["a"]["name"], songs["b"]["name"])
            self.assertNotEqual(songs["a"]["path"], songs["b"]["path"])
            self.assertTrue(Path(songs["a"]["path"]).is_file())
            return ["b", "a"]

        with patch.object(song_order, "optimizer_provider", provider):
            self.app.run()
            self.check_mix(1000, 2000)
            self.click("자동 추천 순서 적용")
            self.assertFalse(self.app.get("download_button"))
            self.check_mix(2000, 1000)
            self.click("자동 추천 순서 적용")
            self.assertTrue(self.app.get("download_button"))

    def test_invalid_provider_output_preserves_order_and_mix(self):
        self.check_mix(1000, 2000)
        with patch.object(song_order, "optimizer_provider", lambda songs: ["a", "unknown"]):
            self.app.run()
            self.click("자동 추천 순서 적용")
        self.assertEqual(self.app.session_state.song_order, ["a", "b"])
        self.assertTrue(self.app.error)
        self.assertFalse(self.app.success)
        self.assertTrue(self.app.get("download_button"))

    def test_corrupt_upload_blocks_recommendation_and_mix(self):
        self.check_mix(1000, 2000)
        invalid = BytesIO(b"not a wav")
        invalid.name = "bad.wav"
        invalid.file_id = "bad"
        self.uploads.append(invalid)
        self.app.run()
        self.assertTrue(self.app.error)
        self.assertFalse(self.app.get("download_button"))
        for button in self.app.button:
            if button.label in {"테스트용 순서 적용", "믹스 만들기"}:
                self.assertTrue(button.disabled)
