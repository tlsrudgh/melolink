# MeloLink

MeloLink는 로컬 MP3/WAV 음악의 특성을 분석하고, 곡 사이의 자연스러운 연결 순서를 추천한 뒤 연속 믹스를 만드는 2인 팀 프로젝트입니다. 현재 A 파트의 음악 분석과 재생 순서 추천을 제공합니다.

## 역할 구분

- **A 파트(현재 구현):** 오디오 로딩, BPM·RMS·MFCC·온셋 강도 추출, 전체/시작/끝 구간 분석
- **A 파트(현재 구현):** 곡 간 연결 적합도 계산, 재생 순서 최적화, 추천 결과 반환
- **B 파트(미구현):** Streamlit UI, 크로스페이드, 오디오 믹싱, 결과 파일 출력

`src/melolink/analysis`와 `src/melolink/mixing`을 경계로 두 파트를 분리했습니다. `mixing`은 통합 위치만 예약했으며 B 기능은 포함하지 않습니다.

## 개발 환경 설정

지원 Python 버전은 **3.12 이상 3.15 미만**입니다. 현재 검증 환경은 Windows 11 / Python 3.14입니다. MP3는 Librosa의 오디오 백엔드가 읽을 수 있어야 하며, Windows에서는 [FFmpeg](https://ffmpeg.org/)를 설치하고 `ffmpeg -version`이 실행되는 구성을 권장합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

동일한 고정 버전을 단순 설치하려면 다음 명령도 사용할 수 있습니다.

```powershell
python -m pip install -r requirements.txt
```

## 음악 분석 실행

Python에서 호출:

```python
from melolink.analysis import analyze_audio

result = analyze_audio("my_song.mp3")
custom = analyze_audio("my_song.wav", segment_seconds=15.0)
```

설치 후 명령줄에서 JSON 출력:

```powershell
melolink-analyze "C:\Music\my_song.mp3"
melolink-analyze "C:\Music\my_song.wav" --segment-seconds 15
```

기본 구간 길이는 10초입니다. 파일이 더 짧으면 실제 파일 전체를 시작/끝 구간으로 사용합니다. 지원하지 않는 확장자, 없는 경로, 디코딩 불가능한 파일은 구분된 예외로 보고합니다.

## 분석 결과 구조

결과는 `json.dumps(result, allow_nan=False)`로 직렬화할 수 있는 딕셔너리입니다.

```text
schema_version             결과 스키마 버전
track_id                   파일 내용의 SHA-256 (컴퓨터와 경로에 독립적)
file_name                  경로를 제외한 파일명
duration_seconds           전체 길이
sample_rate_hz             분석 샘플레이트
bpm                        전체 구간 BPM
segment_seconds_requested  요청한 시작/끝 구간 길이
full / start / end
  duration_seconds
  tempo_bpm
  rms: mean, std, values
  mfcc: mean[13], std[13]
  rhythm: onset_strength_mean, onset_strength_std, onset_strength[]
```

절대 파일 경로는 결과에 넣지 않습니다. RMS와 온셋 강도는 시간 프레임별 배열이며, MFCC는 각 계수의 평균/표준편차 배열로 요약해 다른 곡과 비교하기 쉽게 구성했습니다.

## 테스트

```powershell
python -m pytest
```

테스트 음원은 실행 중 임시 폴더에 생성되는 합성 사인파이므로 저장소에 저작권 음원이 남지 않습니다. WAV, 짧은 파일, 잘못된 경로/형식/내용, JSON 구조를 검사합니다. MP3 테스트는 FFmpeg로 합성 WAV를 변환하며, FFmpeg가 없거나 MP3 인코딩을 지원하지 않으면 이유를 표시하고 건너뜁니다.

## 재생 순서 추천 및 B 파트 연동

```python
from melolink.analysis import analyze_audio, recommend_playlist

paths = ["song-a.wav", "song-b.mp3", "song-c.wav"]
tracks = [analyze_audio(path) for path in paths]
recommendation = recommend_playlist(tracks)
ordered_paths = [paths[i] for i in recommendation["track_indices"]]
```

`score_transition(previous, following)`은 앞 곡의 끝과 뒤 곡의 시작을 비교합니다. 점수는 0~1이며 기준 가중치는 BPM 35%, RMS 25%, MFCC 25%, 온셋 강도 15%입니다. 온셋이 없는 구간은 BPM을 제외하고 나머지 가중치를 재정규화합니다. 분석 옵션은 곡마다 동일하게 사용하는 것이 좋습니다. 점수와 가중치는 청취 검증을 거치기 전의 초기 기준입니다.

`recommend_playlist()`는 인접 연결 점수 합을 기준으로 12곡까지 정확한 최적해를 구하고, 13곡부터는 각 곡에서 시작하는 탐욕 탐색 결과 중 최고 점수 순서를 사용합니다. JSON 호환 결과의 `track_indices`로 B 파트에서 원본 파일 목록을 재정렬할 수 있습니다. 동일한 파일이 여러 번 들어와도 각 입력 위치가 보존됩니다. 결과에는 `track_ids`, `total_score`, `method`, 연결별 `transitions`도 포함됩니다.

B 파트 개발 범위는 Streamlit, 크로스페이드, 믹스 생성 및 출력입니다.

## 폴더 일괄 분석과 JSON 출력

```powershell
.\.venv\Scripts\python.exe -m melolink.analysis.batch .\data
.\.venv\Scripts\python.exe -m melolink.analysis.batch .\data --output .\data\playlist.json
```

폴더 바로 아래의 MP3·WAV를 파일명 순으로 분석합니다. JSON의 `tracks`에는 분석에 성공한 파일의 이름, ID, 길이, BPM이 들어갑니다. `recommendation.track_indices`와 `recommendation.transitions`의 인덱스는 이 `tracks` 배열을 기준으로 합니다. 팀원 B는 입력 폴더와 `tracks[index].file_name`을 조합해 원본 파일을 열 수 있습니다.

실패한 곡은 `failures`에 기록되며 성공한 곡으로 추천을 계속합니다. 성공한 곡이 하나도 없으면 빈 추천 결과를 출력하고 종료 코드 1을 반환합니다. `--output`을 지정하면 새 UTF-8 파일을 생성하며, 기존 파일이 있으면 오류를 표시합니다.

## 오픈소스 및 라이선스

이 프로젝트가 직접 사용하는 패키지는 다음과 같습니다. 재배포 전에는 설치 환경의 전이 의존성 라이선스도 함께 확인해야 합니다.

| 프로젝트 | 용도 | 라이선스 / 출처 |
|---|---|---|
| [Librosa](https://librosa.org/) | 음악·오디오 특징 분석 | ISC |
| [NumPy](https://numpy.org/) | 수치 배열 연산 | BSD-3-Clause (배포물에 포함된 제3자 구성요소는 추가 라이선스 포함) |
| [SciPy](https://scipy.org/) | 과학 계산 및 Librosa 기반 기능 | BSD-3-Clause |
| [SoundFile](https://python-soundfile.readthedocs.io/) | 오디오 파일 입출력 백엔드 | BSD-3-Clause |
| [pytest](https://pytest.org/) | 자동 테스트 | MIT |
| [FFmpeg](https://ffmpeg.org/legal.html) | 선택적 MP3 디코딩/테스트 변환 | 빌드 옵션에 따라 LGPL/GPL; 현재 설치 빌드 확인 필요 |

버전은 `requirements.txt`에 고정되어 재현 가능한 설치를 제공합니다.
