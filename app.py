import hashlib
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from audio_io import save_uploaded_audio
from mixer import create_mix


st.set_page_config(page_title="MeloLink", page_icon="🎵")
st.title("🎵 MeloLink")
st.write("MP3 또는 WAV 파일을 올려 여러 곡을 크로스페이드로 연결하세요.")

if "work_dir" not in st.session_state:
    st.session_state.work_dir = TemporaryDirectory(prefix="melolink-")
    st.session_state.upload_cache = {}
    st.session_state.mix_settings = None

work_dir = Path(st.session_state.work_dir.name)
upload_cache = st.session_state.upload_cache
uploaded_files = st.file_uploader(
    "음악 파일",
    type=["mp3", "wav"],
    accept_multiple_files=True,
    help="곡은 업로드 목록에 표시된 순서대로 연결됩니다.",
)

songs = []
for uploaded_file in uploaded_files:
    name = Path(uploaded_file.name).name
    key = (Path(name).suffix.lower(), hashlib.sha256(uploaded_file.getbuffer()).digest())

    if key in upload_cache and not Path(upload_cache[key]["path"]).is_file():
        del upload_cache[key]

    try:
        if key not in upload_cache:
            upload_cache[key] = save_uploaded_audio(uploaded_file, str(work_dir / "uploads"))
        songs.append({**upload_cache[key], "name": name})
    except FileNotFoundError as error:
        if error.filename == "ffprobe":
            st.error("ffprobe를 찾을 수 없습니다. FFmpeg가 설치되어 있고 실행 경로에 있는지 확인하세요.")
            break
        st.error(f"{name} 파일을 검사하는 중 필요한 파일을 찾지 못했습니다.")
    except ValueError:
        st.error(f"{name} 파일을 읽을 수 없습니다. 재생 가능한 MP3 또는 WAV 파일을 올려 주세요.")
    except OSError as error:
        st.error(f"{name} 파일을 저장하거나 검사하지 못했습니다. {error.strerror or error}")

if songs:
    st.table([
        {"순서": index, "파일": song["name"], "재생 시간(초)": round(song["duration"], 2)}
        for index, song in enumerate(songs, start=1)
    ])

fade = st.slider("크로스페이드 길이(초)", 0.1, 30.0, 5.0, 0.1)
short_tracks = [song["name"] for song in songs if song["duration"] <= fade]
if len(songs) < 2:
    st.info("믹스를 만들려면 유효한 음악 파일을 2개 이상 올려 주세요.")
elif short_tracks:
    st.warning("크로스페이드 길이를 다음 곡의 재생 시간보다 짧게 설정하세요. "
               + ", ".join(short_tracks))

settings = (tuple(song["path"] for song in songs), fade)
output = work_dir / "melolink_mix.wav"
if st.button(
    "믹스 만들기",
    type="primary",
    disabled=len(songs) < 2 or len(songs) != len(uploaded_files) or bool(short_tracks),
):
    pending = work_dir / "pending.wav"
    try:
        with st.spinner("곡을 연결하는 중입니다…"):
            create_mix(list(settings[0]), fade, str(pending))
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
