import json
from dataclasses import asdict
from pathlib import Path

import streamlit as st
from streamlit import runtime

from song_order import UploadedSong
from transition_planner import TransitionPlan


def render_preview(plan: TransitionPlan, catalog: dict[str, UploadedSong]) -> None:
    media = runtime.get_instance().media_file_mgr
    tracks = {}
    for song_id in plan.order:
        song = catalog[song_id]
        mime = "audio/mpeg" if Path(song["path"]).suffix.lower() == ".mp3" else "audio/wav"
        url = media.add(str(song["path"]), mime, f"web-preview-{song_id}")
        prefix = st.get_option("server.baseUrlPath").strip("/")
        tracks[song_id] = {"name": song["name"], "url": f"/{prefix}{url}" if prefix else url}
    payload = json.dumps({"plan": asdict(plan), "tracks": tracks}).replace("<", r"\u003c")
    script = (Path(__file__).parent / "poc/web_audio/player.js").read_text()
    st.iframe(f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<style>body{{font:16px system-ui;margin:0}}button{{font:inherit;padding:5px 12px}}</style>
<form id="controls"><fieldset id="settings" hidden></fieldset>
<button id="play">미리 듣기</button> <button type="button" id="stop" disabled>정지</button>
<output id="status" aria-live="polite"></output></form>
<script type="application/json" id="preview-data">{payload}</script><script>{script}</script></html>""",
              height=60, alt="전체 곡 실시간 플레이어")
