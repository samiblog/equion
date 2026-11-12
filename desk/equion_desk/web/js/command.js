// 명령 창 (DESK_V2 §7) — 오른쪽 열에서 터미널과 위아래로. Equion 명령 한 줄을 쳐서 Enter 로 실행한다.
//
//   > est demand:CN            식을 추정 — 결과 탭이 가운데에 열린다
//   > an corr                  왼쪽에서 고른 변수가 대상으로 들어간다
//
// - 문법은 명령줄 그대로(앞의 `equion` 은 빼도 된다). 같은 줄을 터미널에서 치면 같은 일이고 같은 기록이 남는다.
// - 터미널과 달리 프로그램을 새로 띄우지 않고 떠 있는 작업 프로세스에 시킨다(0.1초 안팎) — 기록의 '누가'는 Desk.
// - 파일을 바꾸는 명령(채택·회차 바꾸기…)도 바로 실행한다. 바뀐 것은 바뀜 기록에 남고 그 자리에서 차이를 보고 되돌린다.
// - 받지 않는 것: Python 스크립트(run x.py)·새 프로젝트(new)·셸 명령 — 터미널에서.
// - 자동 완성: 명령·옵션·고를 값과 프로젝트의 이름(식·모형·블록·묶음·시리즈·기록·회차…). ↑↓ 로 지난 명령.

import { cmdText, clear, debounce, flash, h, icon, kindPill, seconds } from './util.js';

const MAX_LOG = 40;
const MAX_HISTORY = 60;
const MAX_SUGGEST = 8;
const LONG_OUT = 14;          // 출력이 이 줄 수보다 길면 접어 둔다
const QUOTE = "'";

// 명령 자리의 이름 → 프로젝트 이름 목록(catalog.names 의 열쇠)
const ARG_NAMES = {
  part: 'parts', model: 'models', record: 'records', records: 'records', vintage: 'vintages', a: 'vintages', b: 'vintages',
  scenarios: 'scenarios', script: 'scripts', report: 'reports',
};
const NAME_BY_COMMAND = { 'group define': 'groups', 'group remove': 'groups', 'block define': 'blocks', 'block add': 'blocks', 'model define': 'models', est: 'parts' };
const OPT_NAMES = { '--model': 'models', '--part': 'parts', '--block': 'blocks', '--blocks': 'blocks', '--group': 'groups', '--vs': 'records', '--replay': 'records',
  '--from': 'parts', '--series': 'series', '--swap': 'parts' };
const TARGET_NAMES = { series: 'series', expr: 'series', group: 'groups', part: 'parts', model: 'models', block: 'blocks', records: 'records', est: 'records' };

/** Python 의 shlex.quote 와 같은 규칙 */
export function quote(word) {
  const s = String(word);
  if (s === '') return QUOTE + QUOTE;
  return /[^A-Za-z0-9_@%+=:,./-]/.test(s) ? QUOTE + s.split(QUOTE).join(`${QUOTE}"${QUOTE}"${QUOTE}`) + QUOTE : s;
}

/** 줄을 낱말로(따옴표 안의 빈칸은 낱말 안) — 자동 완성용, 대충이면 된다 */
function words(text) {
  const out = [];
  let cur = '';
  let q = null;
  let started = false;
  for (const ch of text) {
    if (q) { if (ch === q) q = null; else cur += ch; continue; }
    if (ch === '"' || ch === "'") { q = ch; started = true; continue; }
    if (/\s/.test(ch)) { if (started) { out.push(cur); cur = ''; started = false; } continue; }
    cur += ch;
    started = true;
  }
  return { done: out, last: started ? cur : '', open: !!q, trailing: !started };
}

export class CommandPane {
  constructor(project) {
    this.project = project;
    this.catalog = null;
    this.entries = [];
    this.histIndex = -1;
    this.draft = '';
    this.suggest = [];
    this.pick = 0;
    this.running = false;
    this.input = h('input', { class: 'cmd-input', type: 'text', spellcheck: 'false', autocomplete: 'off', 'aria-label': '명령', 'data-act': 'cmd-input',
      placeholder: 'Equion 명령 — 예: est demand:CN · an unitroot Y · hs main' });
    this.hint = h('div', { class: 'cmd-hint' });
    this.list = h('div', { class: 'cmd-suggest', role: 'listbox', hidden: true });
    this.log = h('div', { class: 'cmd-log', 'aria-live': 'polite' });
    this.runBtn = h('button', { class: 'icon-btn', type: 'button', title: '실행 (Enter)', 'aria-label': '실행', onclick: () => this.submit() }, icon('play'));
    this.swapBtn = h('button', { class: 'icon-btn', type: 'button', 'data-act': 'cmd-swap', title: '터미널과 자리 바꾸기(위·아래)', 'aria-label': '자리 바꾸기',
      onclick: () => project.app.setSetting('cmd_top', !project.app.settings.cmd_top) }, icon('swap'));
    this.clearBtn = h('button', { class: 'icon-btn', type: 'button', title: '창의 글을 지운다(기록은 그대로)', 'aria-label': '글 지우기', onclick: () => { this.entries = []; this.drawLog(); } }, icon('trash'));
    this.el = h('section', { class: 'cmd-pane', 'aria-label': '명령 창' },
      h('div', { class: 'cmd-head' }, h('b', {}, '명령'), h('span', { class: 'muted' }, '터미널보다 빠르게 — 결과는 가운데 탭으로'), h('span', { class: 'grow' }), this.clearBtn, this.swapBtn),
      this.log,
      h('div', { class: 'cmd-form' }, this.list, this.hint, h('div', { class: 'cmd-row' }, h('span', { class: 'prompt' }, '>'), this.input, this.runBtn)));
    this.input.addEventListener('input', () => { this.histIndex = -1; this.update(); });
    this.input.addEventListener('keydown', (e) => this.key(e));
    this.input.addEventListener('focus', () => { this.ensureCatalog(); this.update(); });
    this.input.addEventListener('blur', () => setTimeout(() => this.closeList(), 120));
    this.reloadCatalog = debounce(() => { if (this.catalog) this.loadCatalog(); }, 800);
    this.drawLog();
    this.drawHint();
  }

  get history() { return this.project.cmdHistory; }

  async ensureCatalog() { if (!this.catalog && !this.loading) await this.loadCatalog(); }

  async loadCatalog() {
    this.loading = true;
    try { this.catalog = await this.project.get('catalog'); } catch { /* 작업 프로세스가 아직 — 다음에 */ }
    this.loading = false;
    if (document.activeElement === this.input) this.update();
  }

  // ---- 실행 -----------------------------------------------------------------------------------

  /** 왼쪽에서 고른 대상 — `an 분석` 처럼 대상 없이 친 줄에 넣는다 */
  selection() { return this.project.side?.targetText() || ''; }

  /** `an 분석` 만 쳤으면 고른 변수를 대상으로 붙인다(분석 이름 뒤에 대상이 없을 때만) */
  fill(line) {
    const w = words(line.trim()).done.concat(words(line.trim()).last ? [words(line.trim()).last] : []);
    const at = w[0]?.toLowerCase() === 'equion' ? 1 : 0;
    if (w[at] !== 'an' || w.length !== at + 2 || w[at + 1].startsWith('-') || ['list', 'keep'].includes(w[at + 1])) return line;
    const target = this.selection();
    return target ? `${line.trim()} ${quote(target)}` : line;
  }

  async submit(text = null) {
    let line = (text ?? this.input.value).trim();
    if (!line) return;
    if (this.running) { flash('명령이 도는 중입니다 — 끝난 뒤에'); return; }
    line = this.fill(line);
    this.remember(line);
    this.input.value = '';
    this.closeList();
    this.drawHint();
    const entry = { line, state: 'run', started: performance.now() };
    this.entries.push(entry);
    if (this.entries.length > MAX_LOG) this.entries.shift();
    this.running = true;
    this.drawLog();
    try {
      const res = await this.project.compute('line', { line }, { quiet: true });
      Object.assign(entry, res.result, { state: res.result.denied ? 'denied' : res.result.code === 0 ? 'ok' : 'bad' });
      const first = entry.records?.[0];
      if (first) this.project.openRecord(first);
      if (entry.changes?.length) this.project.loadOverview();
    } catch (err) {
      if (err.kind === 'busy') { this.entries.pop(); this.input.value = line; }
      else Object.assign(entry, { state: 'bad', out: err.message, code: err.kind === 'cancelled' ? 130 : 1 });
    } finally {
      this.running = false;
      this.drawLog();
    }
  }

  remember(line) {
    const list = this.history;
    const at = list.indexOf(line);
    if (at >= 0) list.splice(at, 1);
    list.push(line);
    while (list.length > MAX_HISTORY) list.shift();
    this.histIndex = -1;
    this.project.saveView();
  }

  // ---- 키 -----------------------------------------------------------------------------------

  key(e) {
    const open = !this.list.hidden && this.suggest.length;
    if (e.key === 'Enter') {
      e.preventDefault();
      if (open && this.pickedOnce) { this.accept(this.suggest[this.pick]); return; }
      this.submit();
      return;
    }
    if (e.key === 'Tab') {
      if (open) { e.preventDefault(); this.accept(this.suggest[this.pick]); }
      return;
    }
    if (e.key === 'Escape') { if (open) { e.preventDefault(); e.stopPropagation(); this.closeList(); } return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const d = e.key === 'ArrowDown' ? 1 : -1;
      if (open && (this.pickedOnce || d > 0) && this.histIndex < 0) {
        this.pickedOnce = true;
        this.pick = (this.pick + d + this.suggest.length) % this.suggest.length;
        this.drawList();
        return;
      }
      this.walkHistory(d);
    }
  }

  walkHistory(d) {
    const list = this.history;
    if (!list.length) return;
    if (this.histIndex < 0) { if (d > 0) return; this.draft = this.input.value; this.histIndex = list.length; }
    this.histIndex = Math.max(0, Math.min(list.length, this.histIndex + d));
    this.input.value = this.histIndex === list.length ? this.draft : list[this.histIndex];
    if (this.histIndex === list.length) this.histIndex = -1;
    this.closeList();
    requestAnimationFrame(() => this.input.setSelectionRange(this.input.value.length, this.input.value.length));
  }

  // ---- 자동 완성 --------------------------------------------------------------------------------

  update() {
    this.drawHint();
    if (document.activeElement !== this.input) return;
    this.suggest = this.suggestions(this.input.value);
    this.pick = 0;
    this.pickedOnce = false;
    this.drawList();
  }

  /** 지금 칠 낱말의 후보 — [{text, note, kind}] */
  suggestions(text) {
    const cat = this.catalog;
    if (!cat || !text.trim()) return [];          // 빈 칸에서는 보이지 않는다(치기 시작하면)
    const { done: w0, last, open } = words(text);
    if (open) return [];
    const w = w0[0]?.toLowerCase() === 'equion' ? w0.slice(1) : w0;
    const prefix = last.toLowerCase();
    const cmds = cat.commands.filter((c) => !c.denied && c.command);
    // 명령 이름 자리 — 친 낱말로 시작하는 명령의 다음 낱말
    const typed = w.join(' ');
    const exact = cmds.filter((c) => c.command === typed || c.command.startsWith(`${typed} `) || !typed);
    const deeper = new Map();
    const subs = new Map();          // 'group' → define · list · remove (다음 낱말이 더 있는 명령)
    for (const c of exact) {
      const rest = c.command.split(' ').slice(w.length);
      if (!rest.length) continue;
      const next = rest[0];
      if (!next.toLowerCase().startsWith(prefix)) continue;
      if (rest.length > 1) { if (!subs.has(next)) subs.set(next, []); subs.get(next).push(rest[1]); }
      if (!deeper.has(next) || rest.length === 1) deeper.set(next, { text: next, note: rest.length === 1 ? c.help : '', kind: 'cmd' });
    }
    for (const [k, list] of subs) { const d = deeper.get(k); if (d && !d.note) d.note = `${list.slice(0, 6).join(' · ')}${list.length > 6 ? ' …' : ''}`; }
    if (deeper.size) return [...deeper.values()].slice(0, MAX_SUGGEST);
    // 명령이 정해졌다 — 옵션·값·이름
    let spec = null;
    for (let k = Math.min(w.length, 3); k > 0 && !spec; k--) spec = cmds.find((c) => c.command === w.slice(0, k).join(' ')) || null;
    if (!spec) return [];
    const depth = spec.command.split(' ').length;
    const after = w.slice(depth);
    const prev = after[after.length - 1];
    const prevOpt = prev?.startsWith('-') ? spec.options.find((o) => o.flags.includes(prev)) : null;
    if (prevOpt?.takes) {
      const pool = prevOpt.choices || this.names(OPT_NAMES[prevOpt.flags[prevOpt.flags.length - 1]] || OPT_NAMES[prevOpt.flags[0]]);
      return this.filter(pool, prefix, prevOpt.help);
    }
    if (last.startsWith('-')) {
      const used = new Set(after);
      return spec.options.filter((o) => !o.flags.some((f) => used.has(f))).flatMap((o) => o.flags.filter((f) => f.startsWith('--')).slice(0, 1))
        .filter((f) => f.startsWith(last)).slice(0, MAX_SUGGEST)
        .map((f) => ({ text: f, note: spec.options.find((o) => o.flags.includes(f))?.help || '', kind: 'opt' }));
    }
    // 몇째 자리 인자인가(옵션과 그 값을 빼고 센다)
    let pos = 0;
    for (let i = 0; i < after.length; i++) {
      const o = after[i].startsWith('-') ? spec.options.find((x) => x.flags.includes(after[i])) : null;
      if (o) { if (o.takes) i++; continue; }
      pos++;
    }
    const arg = spec.args[Math.min(pos, spec.args.length - 1)];
    if (!arg || (pos >= spec.args.length && !arg.many)) return [];
    if (arg.choices) return this.filter(arg.choices, prefix, arg.help);
    let pool = [];
    if (spec.command.startsWith('an ') && arg.name === 'target') {
      const a = cat.names.analyses.find((x) => `an ${x.name}` === spec.command);
      const kinds = [...new Set((a?.targets || []).map((t) => TARGET_NAMES[t]).filter(Boolean))];
      pool = kinds.flatMap((k) => this.names(k));
      const sel = this.selection();
      if (sel && !last) pool = [sel, ...pool];
    } else {
      const key = (arg.name === 'name' ? NAME_BY_COMMAND[spec.command] : null) || (spec.command === 'est' ? 'parts' : ARG_NAMES[arg.name]);
      pool = this.names(key);
    }
    return this.filter(pool, prefix, arg.help);
  }

  names(key) { return key ? (this.catalog?.names?.[key] || []) : []; }

  filter(pool, prefix, note = '') {
    const seen = new Set();
    const out = [];
    const low = prefix.toLowerCase();
    for (const item of pool) {
      const s = String(item);
      if (seen.has(s) || !s.toLowerCase().startsWith(low) || s === prefix) continue;
      seen.add(s);
      out.push({ text: s, note, kind: 'name' });
      if (out.length >= MAX_SUGGEST) break;
    }
    return out;
  }

  accept(item) {
    if (!item) return;
    const v = this.input.value;
    const { last } = words(v);
    const base = last ? v.slice(0, v.length - last.length) : v.replace(/\s*$/, v.trim() ? ' ' : '');
    this.input.value = `${base}${/[\s'"]/.test(item.text) ? quote(item.text) : item.text} `;
    this.input.focus();
    this.update();
  }

  closeList() { this.list.hidden = true; this.suggest = []; }

  drawList() {
    const box = clear(this.list);
    if (!this.suggest.length) { box.hidden = true; return; }
    box.hidden = false;
    this.suggest.forEach((s, i) => {
      box.append(h('button', { class: `cmd-sug ${i === this.pick ? 'on' : ''} ${s.kind}`.replace(/\s+/g, ' ').trim(), type: 'button', role: 'option', 'aria-selected': String(i === this.pick),
        onpointerdown: (e) => { e.preventDefault(); this.accept(s); } }, h('span', { class: 'mono' }, s.text), s.note ? h('small', {}, s.note) : null));
    });
    box.append(h('div', { class: 'cmd-sug-foot' }, 'Tab 넣기 · ↑↓ 고르기 · Esc 닫기'));
  }

  drawHint() {
    const sel = this.selection();
    const v = this.input.value.trim();
    clear(this.hint);
    if (sel && (!v || /^(equion\s+)?an(\s+\S*)?$/.test(v))) {
      this.hint.append(icon('info'), h('span', {}, '고른 대상 ', h('b', { class: 'mono' }, sel), ' — ', h('code', {}, 'an 분석'), '만 치면 대상으로 들어갑니다'));
    }
    this.hint.hidden = !this.hint.childNodes.length;
  }

  // ---- 글 ------------------------------------------------------------------------------------

  drawLog() {
    const box = clear(this.log);
    if (!this.entries.length) {
      box.append(h('div', { class: 'cmd-empty' },
        h('p', {}, '화면의 ', h('code', {}, '> equion …'), ' 줄을 그대로 쳐도 됩니다(앞의 equion 은 빼도 된다). 결과와 기록은 단추로 한 것과 같습니다.'),
        h('div', { class: 'cmd-examples' }, ['est demand:CN', 'an unitroot Y --trend ct', 'hs main', 'work list'].map((x) => h('button', {
          class: 'cmd-ex mono', type: 'button', title: '입력칸에 넣는다', onclick: () => { this.input.value = x; this.input.focus(); this.update(); },
        }, x))),
        h('p', { class: 'muted' }, 'Python 스크립트와 셸 명령은 터미널에서 — 명령 창은 Equion 이 아는 명령만 실행합니다.')));
      return;
    }
    for (const e of this.entries) box.append(this.entryEl(e));
    box.scrollTop = box.scrollHeight;
  }

  entryEl(e) {
    const out = String(e.out || '').replace(/\s+$/, '');
    const lines = out ? out.split('\n') : [];
    const long = lines.length > LONG_OUT && !e.expanded;
    const status = e.state === 'run' ? h('span', { class: 'spin' })
      : e.state === 'ok' ? h('span', { class: 'cmd-ok', title: '종료 코드 0' }, icon('check'))
        : h('span', { class: 'cmd-code', title: `종료 코드 ${e.code}` }, e.state === 'denied' ? '터미널에서' : `코드 ${e.code}`);
    const pre = out ? h('pre', { class: 'cmd-out' }, long ? lines.slice(0, LONG_OUT).join('\n') : out) : null;
    return h('div', { class: `cmd-entry ${e.state}` },
      h('div', { class: 'cmd-line' }, h('span', { class: 'prompt' }, '>'),
        h('button', { class: 'cmd-text mono', type: 'button', title: '입력칸에 다시 넣는다', onclick: () => { this.input.value = e.line; this.input.focus(); this.update(); } }, e.line),
        h('span', { class: 'grow' }), e.seconds != null ? h('span', { class: 'time' }, seconds(e.seconds)) : null, status),
      pre,
      long ? h('button', { class: 'link small', type: 'button', onclick: () => { e.expanded = true; this.drawLog(); } }, `${lines.length - LONG_OUT}줄 더 보기`) : null,
      e.records?.length || e.changes?.length ? h('div', { class: 'cmd-links' },
        (e.records || []).map((id) => h('button', { class: 'cmd-chip', type: 'button', title: `${id} — 카드 열기`, onclick: () => this.project.openRecord(id) },
          kindPill(id.split(':')[0]), h('span', { class: 'mono' }, id.split(':').slice(1).join(':')))),
        (e.changes || []).map((id) => h('button', { class: 'cmd-chip change', type: 'button', 'data-change': id, title: `${id} — 이 명령이 정의 파일을 바꿨습니다. 차이를 보고 되돌릴 수 있습니다`,
          onclick: () => this.project.openTab({ type: 'changes', id }) }, icon('history'), h('span', { class: 'mono' }, id), h('span', {}, '바뀜 · 되돌리기')))) : null);
  }

  /** 기록 하나에서 만든 명령을 입력칸에 — 다시 돌리기 */
  put(text) {
    this.input.value = cmdText(text).replace(/^equion\s+/, '');
    this.input.focus();
    this.update();
  }

  event(e) {
    if (e.type === 'defs' || e.type === 'record' || e.type === 'data') this.reloadCatalog();
    if (e.type === 'selection') this.drawHint();
  }

  focus() { this.input.focus(); }
}
