// 오른쪽 터미널 — xterm.js와 서버의 셸(ConPTY)을 긴 폴링으로 잇는다. 규약은 Lectern 0.69.1의 terminal.js와 같다
// (키 입력 POST /api/term/input, 출력 POST /api/term/read). 프로젝트 탭마다 터미널 하나 — 셸은 그 프로젝트 폴더에서 뜬다.
// 셸로 가는 길은 사용자의 키 입력과, 사용자가 누른 '터미널로 보내기'(Enter 없이 붙이기만 — 기획안 K5)뿐이다.

import { postJSON, TERM_SECRET } from './api.js';

const X = { 'X-Term': TERM_SECRET };
const FONT = '"Cascadia Mono", "D2Coding", Consolas, "Malgun Gothic", monospace';

function theme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const bg = v('--term-bg', '#15191c');
  return {
    background: bg, foreground: v('--term-fg', '#d5dade'), cursor: '#e8ebee', cursorAccent: bg, selectionBackground: '#2d5f5b',
    black: '#1c2126', red: '#f0796d', green: '#5fcb8c', yellow: '#e3c05a', blue: '#72aae8', magenta: '#c08ee6', cyan: '#4bc0b4', white: '#d5dade',
    brightBlack: '#6b7580', brightRed: '#ff9488', brightGreen: '#7fe0a6', brightYellow: '#f2d47c', brightBlue: '#93c1f4',
    brightMagenta: '#d5aef2', brightCyan: '#7fd9cf', brightWhite: '#ffffff',
  };
}

export class Term {
  /** box: 터미널이 들어갈 요소, pid: 프로젝트 탭 id, onState({shell, alive}) */
  constructor(box, pid, onState = () => {}) {
    this.box = box;
    this.pid = pid;
    this.onState = onState;
    this.sid = null;
    this.next = 0;
    this.reading = null;
    this.xterm = null;
    this.fit = null;
    this.started = false;
  }

  /** 처음 보일 때 한 번 — 숨은 요소에서는 크기를 잴 수 없다 */
  async start() {
    if (this.started) { this.refit(); return; }
    this.started = true;
    this.xterm = new window.Terminal({
      fontFamily: FONT, fontSize: 13, lineHeight: 1.12, cursorBlink: true, scrollback: 8000, allowProposedApi: true, theme: theme(),
    });
    this.fit = new window.FitAddon.FitAddon();
    this.xterm.loadAddon(this.fit);
    this.xterm.loadAddon(new window.Unicode11Addon.Unicode11Addon());
    this.xterm.unicode.activeVersion = '11';     // 한글 폭
    this.xterm.open(this.box);
    this.xterm.onData((data) => { if (this.sid) postJSON('/api/term/input', { t: this.sid, data }, X).catch(() => {}); });
    this.xterm.onResize(({ cols, rows }) => { if (this.sid) postJSON('/api/term/resize', { t: this.sid, cols, rows }, X).catch(() => {}); });
    let timer = 0;
    new ResizeObserver(() => { clearTimeout(timer); timer = setTimeout(() => this.refit(), 60); }).observe(this.box);
    await this.open();
  }

  refit() {
    if (!this.fit || !this.box.offsetWidth) return;
    try { this.fit.fit(); } catch { /* 숨겨짐 */ }
  }

  retheme() { if (this.xterm) this.xterm.options.theme = theme(); }

  async open() {
    this.refit();
    let res;
    try {
      res = await postJSON('/api/term/open', { p: this.pid, cols: this.xterm.cols, rows: this.xterm.rows }, X);
    } catch (err) {
      this.xterm.write(`\r\n[터미널을 열지 못했습니다: ${err.message}]\r\n`);
      this.onState({ shell: '', alive: false });
      return;
    }
    this.sid = res.id;
    this.next = 0;
    this.onState({ shell: res.shell, alive: true });
    this.readLoop(this.sid);
  }

  async readLoop(mine) {
    while (this.sid === mine) {
      const ctl = new AbortController();
      this.reading = ctl;
      let res;
      try {
        res = await postJSON('/api/term/read', { want: { [mine]: this.next } }, X, { signal: ctl.signal });
      } catch {
        if (ctl.signal.aborted || this.sid !== mine) return;
        await new Promise((r) => setTimeout(r, 500));
        continue;
      }
      const out = res.terms?.[mine];
      if (this.sid !== mine) return;
      if (!out) { this.ended('[끝난 터미널입니다 — "다시 시작"을 누르세요]'); return; }
      if (out.reset) this.xterm.reset();
      if (out.data) this.xterm.write(out.data);
      this.next = out.next;
      if (!out.alive) { this.ended(`[셸이 끝났습니다 (종료 코드 ${out.exit ?? '?'}) — "다시 시작"을 누르세요]`); return; }
    }
  }

  ended(text) {
    this.xterm.write(`\r\n${text}\r\n`);
    this.onState({ shell: '', alive: false });
  }

  async restart() {
    if (!this.started) return this.start();
    const old = this.sid;
    this.sid = null;
    this.reading?.abort();
    if (old) { try { await postJSON('/api/term/close', { t: old }, X); } catch { /* 이미 끝남 */ } }
    this.xterm.reset();
    return this.open();
  }

  /** 글을 터미널에 붙인다 — Enter 는 누르지 않는다(실행은 사람이 한다) */
  async paste(text) {
    if (!this.started) await this.start();
    if (!this.sid) return false;
    const clean = String(text).replace(/[\r\n]+/g, ' ');
    try { await postJSON('/api/term/input', { t: this.sid, data: clean }, X); } catch { return false; }
    this.xterm.focus();
    return true;
  }

  focus() { this.xterm?.focus(); }

  /** 화면에서만 뗀다 — 셸은 서버가 탭을 닫을 때 끝낸다 */
  dispose() {
    this.sid = null;
    this.reading?.abort();
    this.xterm?.dispose();
  }
}
