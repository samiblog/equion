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

export async function postJSON(path, body = {}, extra = {}, { signal } = {}) {
  return parse(await fetch(path, {
    method: 'POST', headers: headers({ 'Content-Type': 'application/json', ...extra }), body: JSON.stringify(body), signal,
  }));
}
