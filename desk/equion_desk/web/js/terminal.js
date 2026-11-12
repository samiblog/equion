// 오른쪽 터미널 — xterm.js와 서버의 셸(ConPTY)을 긴 폴링으로 잇는다. 규약은 Lectern 0.69.1의 terminal.js와 같다
// (키 입력 POST /api/term/input, 출력 POST /api/term/read). 셸은 그 프로젝트 폴더에서 뜬다.
//
// 터미널 여러 개(DESK_V2 §1.4 — Lectern D69 와 같다): 머리줄의 탭 [1 PowerShell ×][2 PowerShell ×][+] 로 고르고 더하고 끝낸다.
// 프로젝트마다 MAX_TERMS 개까지. 화면이 터미널로 보내는 것(Claude ▾ · 'Claude Code 에 Equion 알려 주기' · 이름 보내기)은
// 늘 1번에 붙이고 1번을 골라 보인다 — Claude 는 1번에서 돈다고 본다. 2번부터는 사람이 다른 일에 쓴다.
// 셸로 가는 길은 사용자의 키 입력과, 사용자가 누른 '터미널로 보내기'(Enter 없이 붙이기만 — 기획안 K5)뿐이다.
//
// 출력은 모든 터미널(모든 프로젝트)이 긴 폴링 하나를 함께 쓴다 — 셸마다 따로 기다리면 브라우저의 연결 수(호스트마다 6)가 모자란다.

import { getJSON, postJSON, TERM_SECRET } from './api.js';
import { clear, h, icon } from './util.js';

const X = { 'X-Term': TERM_SECRET };
const FONT = '"Cascadia Mono", "D2Coding", Consolas, "Malgun Gothic", monospace';
export const MAX_TERMS = 5;      // 프로젝트마다 터미널 수 (서버 terminal.MAX_SLOTS)

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

// ---- 출력 받기: 긴 폴링 하나를 모든 셸이 함께 쓴다 ----------------------------------------------------------------

const reading = new Map();     // 셸 id → Term
let readOn = false;
let readAbort = null;

function pump(term) {
  reading.set(term.sid, term);
  if (readOn) readAbort?.abort();          // 지금 기다리는 요청에 새 셸을 더해 다시 묻는다
  else readAll();
}

async function readAll() {
  readOn = true;
  try {
    for (;;) {
      for (const [sid, term] of reading) if (term.sid !== sid || term.disposed) reading.delete(sid);
      if (!reading.size) return;
      const want = Object.fromEntries([...reading].slice(0, 16).map(([sid, term]) => [sid, term.next]));
      readAbort = new AbortController();
      let res;
      try {
        res = await postJSON('/api/term/read', { want }, X, { signal: readAbort.signal });
      } catch (err) {
        if (err.name !== 'AbortError') await new Promise((r) => setTimeout(r, 800));   // 서버가 잠시 답하지 않음(AbortError: 새 셸이 붙었다)
        continue;
      }
      for (const [sid, out] of Object.entries(res.terms || {})) {
        const term = reading.get(sid);
        if (!term || term.sid !== sid) continue;
        if (!out) { reading.delete(sid); term.ended('[끝난 터미널입니다 — ‘다시 시작’을 누르세요]'); continue; }
        if (out.reset) term.xterm.reset();
        if (out.data) term.xterm.write(out.data);
        term.next = out.next;
        if (!out.alive) { reading.delete(sid); term.ended(`[셸이 끝났습니다 (종료 코드 ${out.exit ?? '?'}) — ‘다시 시작’을 누르세요]`); }
      }
    }
  } finally {
    readOn = false;
  }
}

// ---- 터미널 하나(번호 하나) ------------------------------------------------------------------------------------

class Term {
  constructor(deck, n) {
    this.deck = deck;
    this.n = n;                  // 서버의 터미널 번호(0 부터) — 화면의 '1'·'2'…
    this.box = h('div', { class: 'term-slot', hidden: true, 'data-n': String(n) });
    this.sid = null;
    this.next = 0;
    this.alive = false;
    this.shell = '';
    this.xterm = null;
    this.fit = null;
    this.disposed = false;
  }

  /** 처음 보일 때 xterm 을 만든다 — 숨은 요소에서는 크기를 잴 수 없다. sid: 이미 돌고 있는 셸(화면을 다시 불러온 뒤) */
  async start(existing = null) {
    if (this.xterm) { this.refit(); return; }
    this.xterm = new window.Terminal({
      fontFamily: FONT, fontSize: 13, lineHeight: 1.12, cursorBlink: true, scrollback: 8000, allowProposedApi: true, theme: theme(),
      minimumContrastRatio: MIN_CONTRAST,
    });
    this.fit = new window.FitAddon.FitAddon();
    this.xterm.loadAddon(this.fit);
    this.xterm.loadAddon(new window.Unicode11Addon.Unicode11Addon());
    this.xterm.unicode.activeVersion = '11';     // 한글 폭
    this.xterm.open(this.box);
    this.xterm.onData((data) => {
      if (this.sid && this.alive) postJSON('/api/term/input', { t: this.sid, data }, X).catch(() => {});
      else if (!this.alive && data === '\r') this.restart();          // 끝난 셸에서 Enter — 다시 띄운다(Lectern 과 같다)
    });
    this.xterm.onResize(({ cols, rows }) => { if (this.sid && this.alive) postJSON('/api/term/resize', { t: this.sid, cols, rows }, X).catch(() => {}); });
    let timer = 0;
    new ResizeObserver(() => { clearTimeout(timer); timer = setTimeout(() => this.refit(), 60); }).observe(this.box);
    await this.open(existing);
  }

  refit() {
    if (!this.fit || this.box.hidden || !this.box.offsetWidth) return;
    try { this.fit.fit(); } catch { /* 숨겨짐 */ }
  }

  retheme() { if (this.xterm) this.xterm.options.theme = theme(); }

  async open(existing = null) {
    this.refit();
    let res = existing;
    if (!res) {
      try {
        res = await postJSON('/api/term/open', { p: this.deck.pid, n: this.n, cols: this.xterm.cols, rows: this.xterm.rows }, X);
      } catch (err) {
        this.xterm.write(`\r\n[터미널을 열지 못했습니다: ${err.message}]\r\n`);
        this.alive = false;
        this.deck.render();
        return;
      }
    }
    this.sid = res.id;
    this.shell = res.shell || '';
    this.next = 0;
    this.alive = true;
    if (existing) postJSON('/api/term/resize', { t: this.sid, cols: this.xterm.cols, rows: this.xterm.rows }, X).catch(() => {});
    this.deck.render();
    pump(this);
  }

  ended(text) {
    this.alive = false;
    this.xterm?.write(`\r\n\x1b[90m${text}\x1b[0m\r\n`);
    this.deck.render();
  }

  async restart() {
    if (!this.xterm) return this.start();
    const old = this.sid;
    this.sid = null;
    if (old && this.alive) { try { await postJSON('/api/term/close', { t: old }, X); } catch { /* 이미 끝남 */ } }
    this.alive = false;
    this.xterm.reset();
    return this.open();
  }

  /** 이 셸을 끝내고 화면에서 뗀다 */
  async close() {
    const old = this.sid;
    this.dispose();
    if (old) { try { await postJSON('/api/term/close', { t: old }, X); } catch { /* 이미 끝남 */ } }
  }

  /** 화면에서만 뗀다 — 셸은 서버가 탭을 닫을 때 끝낸다 */
  dispose() {
    this.disposed = true;
    this.sid = null;
    this.xterm?.dispose();
    this.box.remove();
  }
}

// ---- 터미널 모음(프로젝트 하나) ------------------------------------------------------------------------------------

export class TermDeck {
  /** pid: 프로젝트 탭 id. 머리줄(.term-head)과 몸통(.term-body)을 el 에 담는다 */
  constructor(pid) {
    this.pid = pid;
    this.terms = [];             // 번호 차례
    this.current = null;
    this.started = false;
    this.tabsBox = h('div', { class: 'term-tabs', role: 'tablist', 'aria-label': '터미널' });
    this.addBtn = h('button', { class: 'icon-btn term-add', type: 'button', 'data-act': 'term-add', title: `새 터미널 — 이 프로젝트 폴더에서 (프로젝트마다 ${MAX_TERMS}개까지)`, 'aria-label': '새 터미널',
      onclick: () => this.add() }, icon('plus'));
    this.restartBtn = h('button', { class: 'icon-btn', type: 'button', 'data-act': 'term-restart', title: '고른 터미널의 셸을 끝내고 다시 띄운다', 'aria-label': '다시 시작',
      onclick: () => this.current?.restart() }, icon('refresh'));
    this.body = h('div', { class: 'term-body' });
    this.head = h('div', { class: 'term-head' }, h('b', { class: 'term-title' }, '터미널'), this.tabsBox, this.addBtn, h('span', { class: 'grow' }), this.restartBtn);
    this.tabsBox.addEventListener('wheel', (e) => { if (e.deltaY) { this.tabsBox.scrollLeft += e.deltaY; e.preventDefault(); } }, { passive: false });
  }

  /** 처음 보일 때 — 서버에 이미 돌고 있는 셸(화면을 다시 불러온 뒤)이 있으면 그것을, 없으면 1번을 띄운다 */
  async start() {
    if (this.started) { this.current?.refit(); return; }
    this.started = true;
    let alive = [];
    try { alive = (await getJSON(`/api/term/list?p=${encodeURIComponent(this.pid)}`, X)).terms || []; } catch { /* 처음 */ }
    if (!alive.length) { await this.ensure(0); return; }
    for (const t of alive) this.make(t.n);
    this.select(this.terms[0]);
    for (const t of alive) { const term = this.terms.find((x) => x.n === t.n); this.showSlot(term); await term.start({ id: t.id, shell: t.shell }); }
    this.select(this.terms[0]);
  }

  make(n) {
    const term = new Term(this, n);
    this.terms.push(term);
    this.terms.sort((a, b) => a.n - b.n);
    this.body.append(term.box);
    return term;
  }

  showSlot(term) { for (const t of this.terms) t.box.hidden = t !== term; }

  /** 그 번호의 터미널(없으면 만든다)을 골라 띄운다 */
  async ensure(n) {
    let term = this.terms.find((t) => t.n === n);
    if (!term) term = this.make(n);
    this.select(term);
    await term.start();
    return term;
  }

  select(term) {
    if (!term) return;
    this.current = term;
    this.showSlot(term);
    this.render();
    requestAnimationFrame(() => term.refit());
  }

  async add() {
    if (this.terms.length >= MAX_TERMS) return;
    const used = new Set(this.terms.map((t) => t.n));
    let n = 0;
    while (used.has(n)) n++;
    const term = await this.ensure(n);
    term.xterm?.focus();
  }

  async close(term) {
    const i = this.terms.indexOf(term);
    if (i < 0) return;
    this.terms.splice(i, 1);
    await term.close();
    if (this.current === term) this.current = this.terms[Math.min(i, this.terms.length - 1)] || null;
    if (!this.terms.length) { await this.ensure(0); return; }       // 하나는 늘 둔다 — 마지막을 닫으면 새 1번
    this.select(this.current);
  }

  render() {
    const tabs = clear(this.tabsBox);
    for (const term of this.terms) {
      const on = term === this.current;
      tabs.append(h('button', {
        class: `term-tab ${on ? 'on' : ''} ${term.alive ? '' : 'ended'}`.replace(/\s+/g, ' ').trim(), type: 'button', role: 'tab', 'aria-selected': String(on), 'data-n': String(term.n),
        title: `${term.n + 1} · ${term.shell || 'PowerShell'}${term.n === 0 ? ' — Claude 맡기기·제안 받기는 이 터미널에 붙입니다' : ''}${term.alive ? '' : ' (끝남)'}`,
        onclick: () => { this.select(term); term.xterm?.focus(); },
        onauxclick: (e) => { if (e.button === 1) { e.preventDefault(); this.close(term); } },
      }, h('span', { class: 'n' }, String(term.n + 1)), h('span', { class: 'name' }, term.shell || 'PowerShell'),
      h('span', { class: 'x', role: 'button', title: '이 터미널 끝내기 — 셸과 거기서 띄운 프로그램을 끝낸다', 'aria-label': '끝내기',
        onclick: (e) => { e.stopPropagation(); this.close(term); } }, icon('x'))));
    }
    this.addBtn.disabled = this.terms.length >= MAX_TERMS;
    this.addBtn.title = this.terms.length >= MAX_TERMS ? `터미널은 프로젝트마다 ${MAX_TERMS}개까지입니다` : `새 터미널 — 이 프로젝트 폴더에서 (프로젝트마다 ${MAX_TERMS}개까지)`;
    this.restartBtn.disabled = !this.current;
    this.tabsBox.querySelector('.term-tab.on')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  refit() { this.current?.refit(); }

  retheme() { for (const t of this.terms) t.retheme(); }

  /** 글을 1번 터미널에 붙이고 1번을 골라 보인다 — Enter 는 누르지 않는다(실행은 사람이 한다) */
  async paste(text) {
    if (!this.started) await this.start();
    const term = await this.ensure(0);
    if (!term.sid || !term.alive) return false;
    const clean = String(text).replace(/[\r\n]+/g, ' ');
    try { await postJSON('/api/term/input', { t: term.sid, data: clean }, X); } catch { return false; }
    term.xterm.focus();
    return true;
  }

  focus() { this.current?.xterm?.focus(); }

  contains(node) { return this.body.contains(node); }

  dispose() { for (const t of this.terms) t.dispose(); this.terms = []; }
}
