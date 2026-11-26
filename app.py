import hashlib
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from web_preview import render_preview
from audio_io import save_uploaded_audio
from mix_engine import FFmpegMixEngine
from recommendation import recommendation_provider
from song_analysis import AnalysisCache, AnalysisSettings, SongAnalysis
from transition_planner import MixSettings, plan_transitions
from song_order import (
    UploadedSong,
    mock_song_order,
    optimizer_provider,
    validate_song_order,
)


def set_song_order(order: list[str]) -> None:
    if order != st.session_state.get("song_order", []):
        st.session_state.song_order = order
        st.session_state.mix_settings = None


def move_song(song_id: str, offset: int) -> None:
    order = list(st.session_state.song_order)
    if song_id not in order:
        return
    index = order.index(song_id)
    target = index + offset
    if 0 <= target < len(order):
        order[index], order[target] = order[target], order[index]
        set_song_order(order)


def apply_recommendation(
    propose_order: Callable[[], Sequence[str]],
    songs_by_id: dict[str, UploadedSong],
) -> bool:
    try:
        proposed_order = propose_order()
    except Exception as error:
        st.error(f"곡 순서를 가져오지 못했습니다. {error}")
        return False
    try:
        set_song_order(validate_song_order(proposed_order, songs_by_id))
    except ValueError as error:
        st.error(f"곡 순서를 반영하지 못했습니다. {error}")
        return False
    return True


st.set_page_config(page_title="MeloLink", page_icon="🎵")
st.title("🎵 MeloLink")
st.write("MP3 또는 WAV 파일을 올려 여러 곡을 크로스페이드로 연결하세요.")

if "work_dir" not in st.session_state:
    st.session_state.work_dir = TemporaryDirectory(prefix="melolink-")
    st.session_state.upload_cache = {}
    st.session_state.mix_settings = None

if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = AnalysisCache()

work_dir = Path(st.session_state.work_dir.name)
upload_cache = st.session_state.upload_cache
uploaded_files = st.file_uploader(
    "음악 파일",
    type=["mp3", "wav"],
    accept_multiple_files=True,
    help="업로드 후 아래의 위로·아래로 버튼으로 연결 순서를 바꿀 수 있습니다.",
)

songs_by_id: dict[str, UploadedSong] = {}
content_keys: dict[str, tuple[str, bytes]] = {}
for uploaded_file in uploaded_files:
    name = Path(uploaded_file.name).name
    key = (Path(name).suffix.lower(), hashlib.sha256(uploaded_file.getbuffer()).digest())

    if key in upload_cache and not Path(upload_cache[key]["path"]).is_file():
        del upload_cache[key]

    try:
        if key not in upload_cache:
            upload_cache[key] = save_uploaded_audio(uploaded_file, str(work_dir / "uploads"))
        songs_by_id[uploaded_file.file_id] = {**upload_cache[key], "name": name}
        content_keys[uploaded_file.file_id] = key
    except FileNotFoundError as error:
        if error.filename == "ffprobe":
            st.error("ffprobe를 찾을 수 없습니다. FFmpeg가 설치되어 있고 실행 경로에 있는지 확인하세요.")
            break
        st.error(f"{name} 파일을 검사하는 중 필요한 파일을 찾지 못했습니다.")
    except ValueError:
        st.error(f"{name} 파일을 읽을 수 없습니다. 재생 가능한 MP3 또는 WAV 파일을 올려 주세요.")
    except OSError as error:
        st.error(f"{name} 파일을 저장하거나 검사하지 못했습니다. {error.strerror or error}")

previous_order = st.session_state.get("song_order", [])
upload_ids = {uploaded_file.file_id for uploaded_file in uploaded_files}
order = [file_id for file_id in previous_order if file_id in songs_by_id]
order.extend(file_id for file_id in songs_by_id if file_id not in previous_order)
if upload_ids != st.session_state.get("upload_ids", set()):
    st.session_state.mix_settings = None
set_song_order(order)
st.session_state.upload_ids = upload_ids

can_mix_uploads = len(songs_by_id) >= 2 and len(songs_by_id) == len(uploaded_files)
with st.expander("음악 분석 설정"):
    use_rms = st.checkbox("믹스 생성 시 구간별 RMS 분석")
    window_seconds = st.selectbox("RMS 분석 구간(초)", (1, 5, 10), index=1)
analysis_settings = AnalysisSettings(window_seconds)


def playlist_analysis(order: list[str], *, include_rms: bool) -> dict[str, SongAnalysis]:
    return {
        song_id: st.session_state.analysis_cache.get(
            song_id, songs_by_id[song_id], content_keys[song_id], analysis_settings,
            analyze=include_rms,
        )
        for song_id in order
    }


def catalog_in_playback_order() -> dict[str, UploadedSong]:
    return {song_id: songs_by_id[song_id].copy() for song_id in order}


if songs_by_id:
    st.subheader("곡 순서")
    if recommendation_provider is not None:
        if st.button("자동 추천 순서 적용", disabled=not can_mix_uploads):
            if apply_recommendation(
                lambda: recommendation_provider(playlist_analysis(order, include_rms=True)),
                songs_by_id,
            ):
                st.success("자동 추천 순서를 적용했습니다.")
    elif optimizer_provider is None:
        st.caption("자동 추천 기능은 연결 대기 중입니다. 테스트용 순서는 현재 순서를 역순으로 바꿉니다.")
        if st.button("테스트용 순서 적용", disabled=not can_mix_uploads):
            if apply_recommendation(lambda: mock_song_order(catalog_in_playback_order()), songs_by_id):
                st.success("테스트용 순서를 적용했습니다.")
    elif st.button("자동 추천 순서 적용", disabled=not can_mix_uploads):
        if apply_recommendation(lambda: optimizer_provider(catalog_in_playback_order()), songs_by_id):
            st.success("자동 추천 순서를 적용했습니다.")
    order = st.session_state.get("song_order", [])

songs = [songs_by_id[file_id] for file_id in order]
if songs:
    for index, (file_id, song) in enumerate(zip(order, songs)):
        details, up, down = st.columns([5, 1, 1])
        details.text(f'{index + 1}. {song["name"]} ({song["duration"]:.2f}초)')
        up.button(
            "위로", key=f"up_{file_id}", disabled=index == 0,
            on_click=move_song, args=(file_id, -1),
        )
        down.button(
            "아래로", key=f"down_{file_id}", disabled=index == len(order) - 1,
            on_click=move_song, args=(file_id, 1),
        )

fade = st.slider("크로스페이드 길이(초)", 0.1, 30.0, 5.0, 0.1)
short_tracks = [song["name"] for song in songs if song["duration"] <= fade]
if len(songs) < 2:
    st.info("믹스를 만들려면 유효한 음악 파일을 2개 이상 올려 주세요.")
elif short_tracks:
    st.warning("크로스페이드 길이를 각 곡의 재생 시간보다 짧게 설정하세요. "
               + ", ".join(short_tracks))

if can_mix_uploads and not short_tracks:
    preview_plan = plan_transitions(order, playlist_analysis(order, include_rms=False), MixSettings(fade))
    st.subheader("전체 곡 실시간 미리 듣기")
    render_preview(preview_plan, songs_by_id)

settings = (tuple(song["path"] for song in songs), fade)
output = work_dir / "melolink_mix.wav"
if st.button(
    "믹스 만들기",
    type="primary",
    disabled=not can_mix_uploads or bool(short_tracks),
):
    pending = work_dir / "pending.wav"
    try:
        with st.spinner("곡을 연결하는 중입니다…"):
            try:
                analysis = playlist_analysis(order, include_rms=use_rms)
            except (ValueError, OSError) as error:
                st.warning(f"RMS 분석에 실패하여 재생 시간으로 전환을 계획합니다. {error}")
                analysis = playlist_analysis(order, include_rms=False)
            plan = plan_transitions(order, analysis, MixSettings(fade))
            FFmpegMixEngine().render(plan, songs_by_id, pending)
            pending.replace(output)
        st.session_state.mix_settings = settings
    except FileNotFoundError as error:
        if error.filename in {"ffmpeg", "ffprobe"}:
            st.error("FFmpeg와 ffprobe가 설치되어 있고 실행 경로에 있는지 확인하세요.")
        else:
            st.error("믹스에 필요한 파일을 찾을 수 없습니다.")
    except subprocess.CalledProcessError:
        st.error("FFmpeg가 믹스를 만들지 못했습니다. 원본 파일이 재생되는지 확인해 주세요.")
    except (ValueError, OSError) as error:
        st.error(f"믹스를 만들지 못했습니다. {error}")
    finally:
        try:
            pending.unlink(missing_ok=True)
        except OSError:
            st.warning("임시 믹스 파일을 정리하지 못했습니다.")

if st.session_state.mix_settings is not None and output.is_file():
    st.subheader("최근 생성한 믹스")
    if settings != st.session_state.mix_settings or len(songs) != len(uploaded_files):
        st.info("아래 WAV는 이전 설정으로 생성했습니다. 현재 설정으로 만들려면 믹스 만들기를 누르세요.")
    try:
        wav = output.read_bytes()
    except OSError:
        st.error("생성된 WAV 파일을 읽지 못했습니다.")
    else:
        st.audio(wav, format="audio/wav")
        st.download_button("WAV 다운로드", wav, file_name=output.name, mime="audio/wav")
