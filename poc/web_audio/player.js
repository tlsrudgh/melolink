const byId = id => document.getElementById(id);
const statusText = byId("status");
let active;
let timer;

const embedded = document.getElementById("preview-data");
if (!embedded) byId("plan").onchange = () => {
  byId("fade").disabled = Boolean(byId("plan").files.length);
};

async function playbackSettings() {
  if (embedded) {
    const { plan, tracks } = JSON.parse(embedded.textContent);
    return { slots: plan.order, fades: plan.transitions.map(edge => edge.seconds), tracks };
  }
  const slots = ["first", "second"];
  const file = byId("plan").files[0];
  if (!file) return { slots, fades: [Number(byId("fade").value)] };

  const plan = JSON.parse(await file.text());
  const ids = slots.map(slot => byId(slot + "Id").value);
  const transition = plan?.transitions?.[0];
  if (plan?.version !== 1 || !Array.isArray(plan.order) || plan.order.length !== 2 ||
      new Set(plan.order).size !== 2 || !plan.order.every(id => id && ids.includes(id)) ||
      !Array.isArray(plan.transitions) || plan.transitions.length !== 1 ||
      transition?.effect !== "crossfade" || transition.outgoing !== plan.order[0] ||
      transition.incoming !== plan.order[1] || !Number.isFinite(transition.seconds) ||
      transition.seconds <= 0) {
    throw new Error("버전 1의 두 곡 계획과 일치하는 곡 ID를 확인하세요.");
  }
  return { slots: plan.order.map(id => slots[ids.indexOf(id)]), fades: [transition.seconds] };
}

function finish(message) {
  clearInterval(timer);
  const context = active;
  active = null;
  if (context) context.close();
  byId("settings").disabled = byId("play").disabled = false;
  byId("stop").disabled = true;
  statusText.textContent = message;
}
byId("stop").onclick = () => finish("재생을 정지했습니다.");
byId("controls").onsubmit = async event => {
  event.preventDefault();
  if (active) return;
  let context;
  try {
    context = new AudioContext();
    active = context;
    byId("settings").disabled = byId("play").disabled = true;
    byId("stop").disabled = false;
    statusText.textContent = "음원을 읽는 중…";
    await context.resume();
    const { slots, fades, tracks } = await playbackSettings();
    if (active !== context) return;
    const names = slots.map(id => tracks ? tracks[id].name : byId(id).files[0].name);
    const buffers = await Promise.all(slots.map(async id => {
      let audio = tracks ? await fetch(tracks[id].url) : byId(id).files[0];
      if (tracks && !audio.ok) throw new Error("음원을 불러올 수 없습니다.");
      return context.decodeAudioData(await audio.arrayBuffer());
    }));
    if (active !== context) return;
    if (fades.some((seconds, i) => seconds >= Math.min(buffers[i].duration, buffers[i + 1].duration))) {
      finish("페이드 길이를 각 음원의 재생 시간보다 짧게 설정하세요.");
      return;
    }

    const sources = buffers.map(buffer => {
      const source = context.createBufferSource();
      source.buffer = buffer;
      return source;
    });
    // Fade the accumulated mix into each new track, like the sequential WAV mixer.
    let mix = sources[0];
    const offsets = [0];
    const edges = [];
    for (const [i, seconds] of fades.entries()) {
      const end = offsets[i] + buffers[i].duration;
      const start = end - seconds;
      offsets.push(start);
      const outgoing = context.createGain();
      const incoming = context.createGain();
      const sum = context.createGain();
      mix.connect(outgoing).connect(sum);
      sources[i + 1].connect(incoming).connect(sum);
      mix = sum;
      edges.push({ start, end, outgoing, incoming });
    }
    mix.connect(context.destination);
    const origin = context.currentTime + 0.05;
    for (const { start, end, outgoing, incoming } of edges) {
      outgoing.gain.setValueAtTime(1, origin + start);
      outgoing.gain.linearRampToValueAtTime(0, origin + end);
      incoming.gain.setValueAtTime(0, origin + start);
      incoming.gain.linearRampToValueAtTime(1, origin + end);
    }
    sources.at(-1).onended = () => {
      if (active === context) finish("재생 완료");
    };
    sources.forEach((source, i) => source.start(origin + offsets[i]));
    statusText.textContent = names[0] + " 재생 중";
    timer = setInterval(() => {
      const elapsed = context.currentTime - origin;
      const i = Math.max(0, offsets.findLastIndex(offset => offset <= elapsed));
      statusText.textContent = i > 0 && elapsed < edges[i - 1].end
        ? names[i - 1] + " → " + names[i] + " 크로스페이드 중"
        : names[i] + " 재생 중";
    }, 50);
  } catch (error) {
    if (active === context) finish("재생 실패 · " + error.message);
  }
};
