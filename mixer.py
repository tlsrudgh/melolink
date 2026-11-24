import subprocess
import tempfile
from pathlib import Path


# 곡 2개 크로스 페이드 생성
def create_crossfade(
    first_song: str, second_song: str, duration: float = 5.0,
    output_path: str = "output/test_mix.wav",
) -> Path:
    """두 음악 파일을 크로스페이드하여 하나의 wav파일로 생성한다."""

    first = Path(first_song)
    second = Path(second_song)
    output = Path(output_path)

    #1. 입력파일 확인
    if not first.is_file():
        raise FileNotFoundError("첫 번째 음악 파일이 없습니다.: {first}")
    if not second.is_file():
        raise FileNotFoundError("두 번째 음악 파일이 없습니다.: {second}")

    #2. 크로스페이드 길이 확인
    if duration <= 0:
        raise ValueError("크로스페이드 길이는 0초보다 커야합니다.")

    #3. 출력 폴더 생성
    output.parent.mkdir(parents=True, exist_ok=True)

    #4. FFmpeg 실행 명령어
    command = [
        "ffmpeg",
        "-y",
        "-i", str(first),
        "-i", str(second),
        "-filter_complex", f"acrossfade=d={duration}",
        "-c:a", "pcm_s16le",
        str(output),
    ]

    #5. FFmpeg 실행
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return output

#음악 파일 길이 반환
def get_audio_duration(file_path: str) -> float:
    """ffprobe를 사용해 음악 파일 길이를 초 단위로 반환"""

    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())

# 여러 곡 크로스페이드 생성
def create_mix(
    song_paths: list[str],
    crossfade_seconds: float = 10.0,
    output_path: str = "output/mix.wav",
) -> Path:
    """여러 곡을 순차적으로 크로스페이드하여 WAV 파일로 생성한다."""

    if len(song_paths) < 2:
        raise ValueError("음악 파일이 최소 2개 필요합니다.")

    if crossfade_seconds <= 0:
        raise ValueError("크로스페이드 길이는 0초보다 커야 합니다.")

    songs = [Path(path) for path in song_paths]

    for song in songs:
        if not song.is_file():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {song}")

        if get_audio_duration(str(song)) <= crossfade_seconds:
            raise ValueError(
                f"{song.name}: 크로스페이드 시간보다 길어야 합니다."
            )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if any(output.resolve() == song.resolve() for song in songs):
        raise ValueError("출력 파일과 입력 파일의 경로가 같으면 안 됩니다.")

    # 중간 믹스 파일을 보관할 임시 폴더
    with tempfile.TemporaryDirectory() as temp_dir:
        current_mix = str(songs[0])

        for i, next_song in enumerate(songs[1:], start=1):
            is_last = i == len(songs) - 1

            # 마지막 연결은 최종 경로로, 그전에는 임시 파일로 저장
            next_output = (
                output
                if is_last
                else Path(temp_dir) / f"step_{i}.wav"
            )

            print(f"크로스페이드 {i}/{len(songs)-1} 처리 중")

            create_crossfade(
                first_song=current_mix,
                second_song=str(next_song),
                duration=crossfade_seconds,
                output_path=str(next_output),
            )

            current_mix = str(next_output)

    return output

if __name__ == "__main__":
    songs = [
        "data/songs/song1.mp3",
        "data/songs/song2.mp3",
        "data/songs/song3.mp3",
    ]

    crossfade = 10.0

    expected = (
        sum(get_audio_duration(song) for song in songs)
        - crossfade * (len(songs) - 1)
    )

    result = create_mix(
        song_paths=songs,
        crossfade_seconds=crossfade,
        output_path="output/final_mix.wav",
    )

    actual = get_audio_duration(str(result))

    print(f"\n예상 길이: {expected:.2f}초")
    print(f"실제 길이: {actual:.2f}초")
    print(f"오차: {actual - expected:+.2f}초")



