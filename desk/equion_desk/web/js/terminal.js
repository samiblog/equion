// 오른쪽 터미널 — xterm.js와 서버의 셸(ConPTY)을 긴 폴링으로 잇는다. 규약은 Lectern 0.69.1의 terminal.js와 같다
// (키 입력 POST /api/term/input, 출력 POST /api/term/read). 프로젝트 탭마다 터미널 하나 — 셸은 그 프로젝트 폴더에서 뜬다.
// 셸로 가는 길은 사용자의 키 입력과, 사용자가 누른 '터미널로 보내기'(Enter 없이 붙이기만 — 기획안 K5)뿐이다.

import { postJSON, TERM_SECRET } from './api.js';

const X = { 'X-Term': TERM_SECRET };
const FONT = '"Cascadia Mono", "D2Coding", Consolas, "Malgun Gothic", monospace';

// ---- 색: 창의 바탕을 따른다(Lectern 의 terminal.js 와 같은 방식 — 설정 term_follow, 끄면 늘 어둡게) -----------------------
// 바탕·글자·커서·선택 색은 tokens.css 의 --term-* 에서(밝은 바탕·어두운 바탕·'늘 어둡게'가 거기서 갈린다), ANSI 16색은 밝기에 맞는 색표를 쓴다.
// 셸과 프로그램은 어두운 바탕을 가정하고 흰 글자를 쓰기도 하므로(PSReadLine 의 숫자, Claude Code 의 강조 등), 글자와 그 칸 바탕의 대비가
// MIN_CONTRAST 보다 낮으면 xterm 이 글자 색을 진하게·옅게 고친다(minimumContrastRatio — 밝은 터미널에서도 다 읽히게).
const MIN_CONTRAST = 4.5;
const ANSI = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
  'brightBlack', 'brightRed', 'brightGreen', 'brightYellow', 'brightBlue', 'brightMagenta', 'brightCyan', 'brightWhite'];
const ansi = (...colors) => Object.fromEntries(ANSI.map((name, i) => [name, colors[i]]));
const PALETTES = {
  dark: ansi('#1c2126', '#f0796d', '#5fcb8c', '#e3c05a', '#72aae8', '#c08ee6', '#4bc0b4', '#d5dade',
    '#6b7580', '#ff9488', '#7fe0a6', '#f2d47c', '#93c1f4', '#d5aef2', '#7fd9cf', '#ffffff'),
  // 밝은 바탕용(Lectern 의 밝은 색표): 흰색(white·brightWhite)은 프로그램이 '또렷한 글자'로 쓰므로 어두운 회색·검정으로
  light: ansi('#24292f', '#c4262e', '#116329', '#8a5a00', '#0b62c4', '#8250df', '#1b7c83', '#57606a',
    '#6e7781', '#a40e26', '#1a7f37', '#9a6700', '#0550ae', '#6639ba', '#136061', '#1f2328'),
};

/** 터미널이 지금 어두운가 — 창이 어둡거나, 설정이 '늘 어둡게'(html 의 term-dark) */
export function termDark() {
  const root = document.documentElement;
  return root.dataset.theme === 'dark' || root.classList.contains('term-dark');
}

function theme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const dark = termDark();
  const bg = v('--term-bg', dark ? '#15191c' : '#f7f6f2');
  return {
    background: bg, foreground: v('--term-fg', dark ? '#d5dade' : '#1b1f24'), cursor: v('--term-cursor', dark ? '#e8ebee' : '#0b7a75'), cursorAccent: bg,
    selectionBackground: v('--term-select', dark ? '#2d5f5b' : '#cfe6e3'), selectionInactiveBackground: v('--term-select-off', dark ? '#24403e' : '#e3efed'),
    ...PALETTES[dark ? 'dark' : 'light'],
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
      minimumContrastRatio: MIN_CONTRAST,
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

  /** 창의 바탕이나 '터미널 색' 설정이 바뀌었다 — 열린 터미널에 지금 색을 입힌다(이미 찍힌 글도 새 색으로 다시 그려진다) */
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
