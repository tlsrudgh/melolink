"""Analyze a directory of local audio and export its recommended order."""

import argparse
import json
from pathlib import Path

from melolink.analysis.analyzer import (
    SUPPORTED_EXTENSIONS,
    AudioAnalysisError,
    analyze_audio,
)
from melolink.analysis.playlist import recommend_playlist


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend a playlist from a folder of MP3/WAV files")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, help="Write UTF-8 JSON to a new file")
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("directory must be an existing folder")

    paths = sorted(
        (path for path in args.directory.iterdir()
         if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda path: (path.name.casefold(), path.name),
    )
    tracks = []
    failures = []
    for path in paths:
        try:
            tracks.append(analyze_audio(path))
        except (AudioAnalysisError, OSError) as exc:
            failures.append({"file_name": path.name, "error": str(exc)})

    report = {
        "schema_version": "1.0",
        # Recommendation indices refer to this successful-input list.
        "tracks": [
            {key: track[key] for key in ("track_id", "file_name", "duration_seconds", "bpm")}
            for track in tracks
        ],
        "failures": failures,
        "recommendation": recommend_playlist(tracks),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        try:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(payload)
        except OSError as exc:
            parser.error(f"cannot create output file: {exc}")
    return 0 if tracks else 1


if __name__ == "__main__":
    raise SystemExit(main())
