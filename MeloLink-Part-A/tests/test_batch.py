import json
import subprocess
import sys


def test_batch_exports_successes_and_failures(wav_file):
    directory = wav_file.parent
    (directory / "broken.mp3").write_bytes(b"bad audio")
    (directory / "notes.txt").touch()
    output = directory / "playlist.json"
    command = [
        sys.executable, "-m", "melolink.analysis.batch", str(directory),
        "--output", str(output),
    ]
    subprocess.run(command, check=True, capture_output=True)
    contents = output.read_text(encoding="utf-8")
    report = json.loads(contents)
    assert [track["file_name"] for track in report["tracks"]] == [wav_file.name]
    assert [failure["file_name"] for failure in report["failures"]] == ["broken.mp3"]
    assert report["recommendation"]["track_indices"] == [0]

    repeated = subprocess.run(command, capture_output=True)
    assert repeated.returncode != 0
    assert output.read_text(encoding="utf-8") == contents


def test_batch_empty_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "melolink.analysis.batch", str(tmp_path)],
        capture_output=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["recommendation"]["track_indices"] == []
