// 서버 API 호출. 창 모드에서는 pywebview가 준 토큰을 X-Token으로 싣는다(Lectern의 api.js와 같은 방식).

const root = document.documentElement;
export const MODE = root.dataset.mode;
export const TERM_SECRET = root.dataset.term;

/** 창 모드: pywebview가 토큰을 넣을 때까지 기다린다(브라우저 모드는 바로). */
export async function ready() {
  if (MODE !== 'app' || window.pywebview?.token) return;
  await new Promise((resolve) => {
    const done = () => { clearInterval(timer); resolve(undefined); };
    window.addEventListener('pywebviewready', done, { once: true });
    const began = Date.now();
    const timer = setInterval(() => { if (window.pywebview?.token || Date.now() - began > 5000) done(); }, 30);
  });
}

function headers(extra = {}) {
  const h = { ...extra };
  const token = window.pywebview?.token;
  if (token) h['X-Token'] = token;
  return h;
}

async function parse(res) {
  let data = null;
  try { data = await res.json(); } catch { /* 본문이 JSON이 아님 */ }
  if (res.ok) return data;
  const err = /** @type {any} */ (new Error(data?.error || `HTTP ${res.status}`));
  err.status = res.status;
  err.kind = data?.kind;
  err.detail = data?.detail;
  throw err;
}

export async function getJSON(path, extra = {}) {
  return parse(await fetch(path, { headers: headers(extra), cache: 'no-store' }));
}

export async function postJSON(path, body = {}, extra = {}, { signal, keepalive } = {}) {
  return parse(await fetch(path, {
    method: 'POST', headers: headers({ 'Content-Type': 'application/json', ...extra }), body: JSON.stringify(body), signal, keepalive,
  }));
}

/** 프로젝트(탭)의 API 주소 */
export const papi = (pid, path) => `/api/p/${encodeURIComponent(pid)}/${path}`;

/** 주소의 물음표 뒤 — 값이 없는 것은 뺀다 */
export function query(params) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null && v !== '') q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : '';
}

/** 그림 파일을 받아 blob 주소로(창 모드의 토큰은 <img src>로 실어 보낼 수 없다) */
export async function blobURL(path) {
  const res = await fetch(path, { headers: headers(), cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

/**
 * 알림 긴 폴링 — 서버의 알림 줄(새 기록·바뀜·정의 바뀜·작업 줄·탭)을 받아 handler(event)에 넘긴다.
 * 서버를 다시 띄웠거나 너무 오래 끊겼으면 onReset() — 화면이 목록을 통째로 다시 읽는다.
 */
export function listen(since, handler, onReset) {
  let seq = since;
  let stopped = false;
  (async () => {
    while (!stopped) {
      let res;
      try {
        res = await getJSON(`/api/events${query({ since: seq })}`);
      } catch {
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
      if (stopped) return;
      if (res.reset) { seq = res.seq; try { onReset?.(); } catch (err) { console.error(err); } continue; }
      seq = res.seq;
      for (const event of res.events) { try { handler(event); } catch (err) { console.error(err); } }
    }
  })();
  return () => { stopped = true; };
}
