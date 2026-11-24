import json
import subprocess
import uuid
from pathlib import Path

#오디오 파일 검사
def validate_audio(file_path: str) -> dict:
    """오디오 파일을 검사하고 파일 정보 반환"""

    path = Path(file_path)
   
    #1. 파일 존재 여부 검사
    if not path.is_file():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다. {path}")
    #2. 확장자 검사
    if path.suffix.lower() not in {".mp3", ".wav"}:
        raise ValueError("MP3 또는 WAV 파일만 사용할 수 있습니다.")
    #3. ffprobe로 실제 오디오 정보 검사
    command = [
        "ffprobe", 
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type",
        "-of", "json",
        str(path),
    ]

    result = subprocess.run(
        command, 
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ValueError(f"오디오 파일 분석에 실패했습니다.: {path.name}")
    
    #4. FFProbe 결과를 python 딕셔너리로 변환
    try:
        info = json.loads(result.stdout)

        audio_streams = [
            stream
            for stream in info.get("streams", [])
            if stream.get("codec_type") == "audio"
        ]

        if not audio_streams:
            raise ValueError("오디오 스트링이 없습니다.")

        duration = float(info["format"]["duration"])

        if duration <= 0:
            raise ValueError("음악 길이가 유호하지 않습니다.")
        
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"올바른 오디오 파일이 아닙니다: {path.name}") from error

    #5. 검증된 파일 정보 반환
    return {
        "name": path.name,
        "path": str(path),
        "duration": duration,
        "format": path.suffix.lower(),
    }

#업로드한 음악 임시 저장

def save_uploaded_audio(uploaded_file, save_dir: str) -> dict:
    """업로드된 오디오를 저장·검증하고 파일 정보를 반환"""

    # 1. 업로드 파일 형식 확인
    original_name = Path(uploaded_file.name).name
    extension = Path(original_name).suffix.lower()

    if extension not in {".mp3", ".wav"}:
        raise ValueError("MP3 또는 WAV 파일만 업로드할 수 있습니다.")

    # 2. 저장 폴더 생성
    folder = Path(save_dir)
    folder.mkdir(parents=True, exist_ok=True)

    # 3. 고유한 파일명 생성
    unique_name = f"{uuid.uuid4().hex}{extension}"
    saved_path = folder / unique_name

    # 4. 업로드 파일 저장
    try:
        with saved_path.open("wb") as file:
            file.write(uploaded_file.getvalue())

        # 5. 저장된 파일 검증
        audio_info = validate_audio(str(saved_path))

    except Exception:
        # 저장 또는 검증에 실패했다면 파일 삭제
        saved_path.unlink(missing_ok=True)
        raise

    # 6. 업로드 파일 정보 반환
    audio_info["name"] = original_name
    return audio_info
 
if __name__ == "__main__":
    from io import BytesIO

    source = Path("data/songs/song1.mp3")

    class TestUpload(BytesIO):
        def __init__(self, file_path):
            super().__init__(file_path.read_bytes())
            self.name = file_path.name

    uploaded = TestUpload(source)

    result = save_uploaded_audio(
        uploaded_file=uploaded,
        save_dir="data/uploads",
    )

    print("업로드 파일 저장 및 검증 성공")
    print(f"원본 파일명: {result['name']}")
    print(f"저장 경로: {result['path']}")
    print(f"재생 경로: {result['duration']:.2f}초")