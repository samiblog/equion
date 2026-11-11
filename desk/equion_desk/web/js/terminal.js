// 오른쪽 터미널 — xterm.js와 서버의 셸(ConPTY)을 긴 폴링으로 잇는다. 규약은 Lectern 0.69.1의 terminal.js와 같다
// (키 입력 POST /api/term/input, 출력 POST /api/term/read). 시험판(D0)은 터미널 하나만 — 여러 개·모음 줄은 D1에서 옮긴다.

import { getJSON, postJSON, TERM_SECRET } from './api.js';

const X = { 'X-Term': TERM_SECRET };
const FONT = '"Cascadia Mono", "D2Coding", Consolas, "Malgun Gothic", monospace';
const THEME = {
  background: '#1e1f22', foreground: '#cccccc', cursor: '#e6e6e6', cursorAccent: '#1e1f22', selectionBackground: '#3a5f8f',
  black: '#1e1f22', red: '#f14c4c', green: '#23d18b', yellow: '#f5f543', blue: '#3b8eea', magenta: '#d670d6', cyan: '#29b8db', white: '#e5e5e5',
  brightBlack: '#666666', brightRed: '#f14c4c', brightGreen: '#23d18b', brightYellow: '#f5f543', brightBlue: '#3b8eea',
  brightMagenta: '#d670d6', brightCyan: '#29b8db', brightWhite: '#ffffff',
};

let xterm = null;
let fit = null;
let sid = null;
let next = 0;
let reading = null;

function note(text) {
  const box = document.getElementById('term');
  box.textContent = '';
  const p = document.createElement('div');
  p.className = 'note';
  p.textContent = text;
  box.append(p);
}

async function readLoop(mine) {
  while (sid === mine) {
    const ctl = new AbortController();
    reading = ctl;
    let res;
    try {
      res = await postJSON('/api/term/read', { want: { [mine]: next } }, X, { signal: ctl.signal });
    } catch (err) {
      if (ctl.signal.aborted || sid !== mine) return;
      await new Promise((r) => setTimeout(r, 500));
      continue;
    }
    const out = res.terms?.[mine];
    if (sid !== mine) return;
    if (!out) { xterm.write('\r\n[끝난 터미널입니다 — "다시 시작"을 누르세요]\r\n'); return; }
    if (out.reset) xterm.reset();
    if (out.data) xterm.write(out.data);
    next = out.next;
    if (!out.alive) { xterm.write(`\r\n[셸이 끝났습니다 (종료 코드 ${out.exit ?? '?'}) — "다시 시작"을 누르세요]\r\n`); return; }
  }
}

async function open() {
  fit.fit();
  let res;
  try {
    res = await postJSON('/api/term/open', { cols: xterm.cols, rows: xterm.rows }, X);
  } catch (err) {
    xterm.write(`\r\n[터미널을 열지 못했습니다: ${err.message}]\r\n`);
    return;
  }
  sid = res.id;
  next = 0;
  document.getElementById('term-title').textContent = `터미널 — ${res.shell}`;
  readLoop(sid);
}

async function restart() {
  const old = sid;
  sid = null;
  reading?.abort();
  if (old) { try { await postJSON('/api/term/close', { t: old }, X); } catch { /* 이미 끝남 */ } }
  xterm.reset();
  await open();
}

export async function startTerminal() {
  const state = await getJSON('/api/state');
  if (!state.terminal) { note('터미널은 Windows 10(1809) 이상에서만 쓸 수 있습니다.'); return; }
  if (!state.root) { note('프로젝트 폴더를 열면 터미널이 그 폴더에서 뜹니다.'); return; }
  xterm = new window.Terminal({
    fontFamily: FONT, fontSize: 13, lineHeight: 1.1, cursorBlink: true, scrollback: 5000, allowProposedApi: true, theme: THEME,
  });
  fit = new window.FitAddon.FitAddon();
  xterm.loadAddon(fit);
  xterm.loadAddon(new window.Unicode11Addon.Unicode11Addon());
  xterm.unicode.activeVersion = '11';     // 한글 폭
  xterm.open(document.getElementById('term'));
  xterm.onData((data) => { if (sid) postJSON('/api/term/input', { t: sid, data }, X).catch(() => {}); });
  xterm.onResize(({ cols, rows }) => { if (sid) postJSON('/api/term/resize', { t: sid, cols, rows }, X).catch(() => {}); });
  let timer = 0;
  new ResizeObserver(() => { clearTimeout(timer); timer = setTimeout(() => { try { fit.fit(); } catch { /* 숨겨짐 */ } }, 60); })
    .observe(document.getElementById('term'));
  document.getElementById('term-restart').addEventListener('click', restart);
  await open();
}
