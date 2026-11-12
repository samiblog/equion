// 왼쪽 열 (DESK_V2 §1.2) — 작업대 줄(늘 보인다 · 지금 표본) · 탭 다섯(변수 · 분석 · 모형 · 파일 · 기록).
//
//   [개요] [자료] [분석 실행] [전망] [보고서]   표본 전체 ▾
//    변수 │ 분석 │ 모형 │ 파일 │ 기록
//    찾기 …
//    목록
//    고른 변수 3  Y → CN → P   [할 수 있는 일 ▾] [창으로] [묶음으로 저장]
//
// 탭 하나는 출발하는 대상 한 종류다. 변수 탭에서는 여러 개를 골라(Ctrl·Shift) 우클릭하거나 '할 수 있는 일 ▾'로 시작한다 — 고른 순서를 지킨다
// (ECM 은 첫 변수가 목표, VAR 은 순서가 결과에 닿는다). 모형 탭과 파일 탭의 목록은 project.js 가 그린다(1차판의 부품·파일 나무).

import { confirmDialog } from './dialog.js';
import { clear, cmdText, debounce, flash, h, icon, KINDS, kindPill, natural, short, when, WHO, whoLabel } from './util.js';
import { openVarMenu, targetText } from './varmenu.js';
import { diffBlock } from './views/lists.js';

const TABS = [['vars', '변수'], ['analysis', '분석'], ['models', '모형'], ['files', '파일'], ['records', '기록']];
const REL = {
  endo: ['식', '이 변수의 식이 모형에 있다 — 누르면 식 작업대'],
  single: ['개별', '이 변수의 식이 있지만 모형에는 들지 않았다(개별 식) — 누르면 식 작업대'],
  exo: ['외생', '모형의 식이 쓰는 외생 변수'],
  used: ['쓰임', '모형 밖의 식(개별 식)이 쓴다'],
};
const KIND_ORDER = ['원자료', '계절조정', '파생', '자료'];
const MAX_ROWS = 400;          // 한 묶음에 그리는 줄 — 넘으면 '더 보기'

export class Side {
  constructor(project) {
    this.p = project;
    this.tab = 'vars';
    this.vars = null;
    this.varsError = null;
    this.alist = null;
    this.alistError = null;
    this.registry = null;
    this.changes = null;
    this.sel = [];               // 고른 변수 — 고른 차례
    this.group = null;           // 고른 묶음 이름(변수와 함께 고르지 않는다)
    this.anchor = null;          // Shift 로 이어 고르기의 시작
    this.q = { vars: '', analysis: '', records: '' };
    this.transform = '';
    this.smpl = '';
    this.stars = new Set();
    this.folded = new Set();
    this.recFilter = 'all';
    this.recSub = 'results';
    this.more = new Set();       // '더 보기'를 누른 묶음
    this.reloadVars = debounce(() => this.loadVars(), 400);
    this.reloadList = debounce(() => this.loadAnalysisList(), 400);
    this.reloadRegistry = debounce(() => this.loadRegistry(), 600);
    this.reloadChanges = debounce(() => { if (this.changes) this.loadChanges(); }, 300);
    this.notes = null;           // 노트(notes/**/*.md)와 블록 상태의 수 — 분석 탭
    this.reloadNotes = debounce(() => { if (this.notes) this.loadNotes(); }, 500);
    this.build();
  }

  // ---- 뼈대 ------------------------------------------------------------------------------------

  build() {
    const p = this.p;
    const wb = (key, ic, label, title, open) => h('button', { class: 'wb', type: 'button', 'data-key': key, title, onclick: open }, icon(ic), h('span', { class: 'lbl' }, label), h('span', { class: 'wb-dot' }));
    this.smplBtn = h('button', { class: 'smpl-chip', type: 'button', 'data-act': 'smpl', title: '지금 표본 — 메뉴에서 바로 돌린 분석은 이 구간을 쓴다(비우면 자료 전체)', onclick: (e) => this.editSample(e.currentTarget) });
    this.bench = h('div', { class: 'wb-row', role: 'toolbar', 'aria-label': '작업대' },
      wb('home', 'home', '개요', '개요 — 프로젝트 한눈에', () => p.openTab({ type: 'home' })),
      wb('data', 'data', '자료', '자료 — 원자료 · 시리즈 · 회차', () => p.openTab({ type: 'data' })),
      wb('analysis', 'flask', '분석 실행', '분석 실행 — 분석을 골라 옵션을 주고 돌린다', () => p.openTab({ type: 'analysis' })),
      wb('forecast', 'forward', '전망', '전망 — 가정을 적고 기준선과 시나리오를 푼다', () => p.openTab({ type: 'forecast' })),
      wb('reports', 'doc', '보고서', '보고서 — 글 사이에 기록에서 보낸 표·차트', () => p.openTab({ type: 'reports' })),
      h('span', { class: 'grow' }), this.smplBtn);
    this.tabsEl = h('div', { class: 'side-tabs', role: 'tablist' }, TABS.map(([key, label]) => h('button', {
      type: 'button', role: 'tab', 'data-side': key, onclick: () => this.showSide(key),
    }, h('span', {}, label), h('span', { class: 'tc' }))));
    this.panes = {
      vars: h('div', { class: 'side-pane vars', hidden: true }),
      analysis: h('div', { class: 'side-body side-pane', hidden: true }),
      models: p.partsBox,
      files: p.filesBox,
      records: h('div', { class: 'side-pane recs', hidden: true }),
    };
    this.p.partsBox.classList.add('side-pane');
    this.p.filesBox.classList.add('side-pane');
    // 변수 탭: 찾기 · 목록 · 고른 변수 줄
    this.varSearch = h('input', { class: 'side-search', type: 'search', placeholder: '변수 찾기 — 이름 · 설명', spellcheck: 'false', 'data-act': 'var-search', 'aria-label': '변수 찾기' });
    this.varSearch.addEventListener('input', () => { this.q.vars = this.varSearch.value; this.drawVarList(); });
    this.varList = h('div', { class: 'side-body var-list', role: 'listbox', 'aria-multiselectable': 'true', 'aria-label': '변수' });
    this.selBar = h('div', { class: 'sel-bar', hidden: true });
    this.panes.vars.append(h('div', { class: 'side-tools' }, icon('search'), this.varSearch), this.varList, this.selBar);
    this.varList.addEventListener('keydown', (e) => this.listKey(e));
    this.el = h('aside', { class: 'side', 'aria-label': '사이드바' }, this.bench, this.tabsEl, ...Object.values(this.panes));
    this.drawSample();
  }

  state() {
    return { sel: this.sel, group: this.group, transform: this.transform, smpl: this.smpl, stars: [...this.stars], folded: [...this.folded], recFilter: this.recFilter, recSub: this.recSub };
  }

  restore(s = {}) {
    const strs = (v, n) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, n) : []);
    this.sel = strs(s.sel, 60);
    this.group = typeof s.group === 'string' ? s.group : null;
    this.transform = typeof s.transform === 'string' ? s.transform : '';
    this.smpl = typeof s.smpl === 'string' ? s.smpl.slice(0, 40) : '';
    this.stars = new Set(strs(s.stars, 200));
    this.folded = new Set(strs(s.folded, 100));
    this.recFilter = typeof s.recFilter === 'string' ? s.recFilter : 'all';
    this.recSub = s.recSub === 'changes' ? 'changes' : 'results';
    this.drawSample();
  }

  save() { this.p.saveView(); }

  showSide(name, { save = true } = {}) {
    if (name === 'parts') name = 'models';
    if (!this.panes[name]) name = 'vars';
    this.tab = name;
    for (const b of this.tabsEl.children) b.setAttribute('aria-selected', String(b.dataset.side === name));
    for (const [k, pane] of Object.entries(this.panes)) pane.hidden = k !== name;
    this.p.el.classList.toggle('side-records', name === 'records');
    if (name === 'vars') { if (!this.vars) this.loadVars(); else this.drawVars(); }
    if (name === 'analysis') { if (!this.alist) this.loadAnalysisList(); else this.drawAnalysis(); if (!this.notes) this.loadNotes(); }
    if (name === 'records') { this.drawRecords(); if (this.recSub === 'changes' && !this.changes) this.loadChanges(); }
    if (name === 'files') this.p.openFiles();
    if (save) this.save();
  }

  /** 처음 열 때 — 고른 탭을 그리고, 변수 메뉴가 쓸 분석 목록을 읽어 둔다 */
  start() {
    this.loadRegistry();
    if (this.tab !== 'vars') this.loadVars();       // 탭 머리의 수 · 명령 창의 고른 대상 · 표의 변수 우클릭이 쓴다
    this.showSide(this.tab, { save: false });
  }

  // ---- 읽기 ------------------------------------------------------------------------------------

  async loadVars() {
    try { this.vars = await this.p.get('variables'); this.varsError = null; } catch (err) { this.varsError = err.message; }
    const have = new Set((this.vars?.variables || []).map((v) => v.name));
    this.sel = this.sel.filter((n) => have.has(n));
    if (this.group && !this.vars?.groups?.some((g) => g.name === this.group)) this.group = null;
    this.drawTabs();
    if (this.tab === 'vars') this.drawVars();
    this.p.command?.drawHint();
  }

  async loadAnalysisList() {
    try { this.alist = await this.p.get('analysis-list'); this.alistError = null; } catch (err) { this.alistError = err.message; }
    this.drawTabs();
    if (this.tab === 'analysis') this.drawAnalysis();
  }

  async loadNotes() {
    try { this.notes = (await this.p.get('notes')).notes; } catch { this.notes = this.notes || []; }
    if (this.tab === 'analysis') this.drawAnalysis();
  }

  async loadRegistry() {
    try { this.registry = await this.p.get('analyses'); } catch { /* 다음 알림 때 */ }
  }

  async loadChanges() {
    try { this.changes = (await this.p.get('changes')).changes; } catch { this.changes = this.changes || []; }
    if (this.tab === 'records') this.drawRecords();
  }

  variable(name) {
    const u = String(name).toUpperCase();
    return this.vars?.variables.find((v) => v.name.toUpperCase() === u) || null;
  }

  groupOf(name) { return this.vars?.groups.find((g) => g.name === name) || null; }

  // ---- 표본 ------------------------------------------------------------------------------------

  drawSample() {
    clear(this.smplBtn).append(h('span', { class: 'k' }, '표본'), h('b', { class: 'mono' }, this.smpl || '전체'), icon('chevron', 'down'));
  }

  editSample(anchor) {
    document.querySelector('.popover')?.remove();
    const span = this.p.overview?.vintage?.span || [];
    const input = h('input', { class: 'mini-input wide', type: 'text', value: this.smpl, spellcheck: 'false', placeholder: span.length ? `${span[0]}:${span[1]}` : '처음:끝', 'aria-label': '표본' });
    const done = (value) => { this.smpl = value.trim(); this.drawSample(); this.save(); pop.remove(); document.removeEventListener('pointerdown', away, true); };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); done(input.value); } if (e.key === 'Escape') { e.stopPropagation(); pop.remove(); } });
    const pop = h('div', { class: 'popover smpl-pop', role: 'dialog', 'aria-label': '표본' },
      h('h4', {}, '지금 표본'), input,
      h('div', { class: 'pop-note' }, '처음:끝 — 예 1990Q1:2019Q4 · 상대 기간 1990Q1:last · last-39:last. 비우면 자료 전체', span.length ? h('span', {}, ` (지금 자료 ${span[0]}–${span[1]})`) : null),
      h('div', { class: 'pop-actions row' }, h('button', { class: 'btn small', type: 'button', onclick: () => done('') }, '전체'),
        h('button', { class: 'btn small primary', type: 'button', onclick: () => done(input.value) }, '적용')));
    document.body.append(pop);
    const r = anchor.getBoundingClientRect();
    pop.style.top = `${r.bottom + 6}px`;
    pop.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - pop.offsetWidth - 8))}px`;
    const away = (e) => { if (!pop.contains(e.target) && !anchor.contains(e.target)) { pop.remove(); document.removeEventListener('pointerdown', away, true); } };
    document.addEventListener('pointerdown', away, true);
    input.focus();
    input.select();
  }

  setTransform(key) { this.transform = key; this.save(); this.p.command?.drawHint(); }

  // ---- 탭 머리의 수 ------------------------------------------------------------------------------

  drawTabs() {
    const p = this.p;
    const count = {
      vars: this.vars ? this.vars.variables.length : '',
      analysis: this.alist ? (this.alist.singles.length + this.alist.results.length) || '' : '',
      models: p.overview ? p.overview.models.length || '' : '',
      files: '',
      records: '',
    };
    const nOpen = p.proposals.filter((x) => x.status === 'open').length;
    for (const b of this.tabsEl.children) {
      const tc = clear(b.querySelector('.tc'));
      const key = b.dataset.side;
      if (key === 'records') {
        const unseen = p.unseen.size;
        if (p.unseenProps.size) tc.append(h('span', { class: 'dot prop', title: '아직 보지 않은 제안이 있습니다' }));
        else if (nOpen) tc.append(h('span', { class: 'n', title: `열린 제안 ${nOpen}` }, nOpen));
        else if (unseen) tc.append(h('span', { class: 'n new', title: `아직 보지 않은 기록 ${unseen}` }, unseen));
      } else if (count[key] !== '') tc.append(h('span', { class: 'n' }, count[key]));
    }
    // 작업대 줄의 점 — 자료에 손볼 것
    const note = p.dataNote();
    const dot = this.bench.querySelector('[data-key="data"] .wb-dot');
    if (dot) { dot.className = `wb-dot ${note && note.level !== 'ok' ? `on ${note.level}` : ''}`.trim(); dot.title = note && note.level !== 'ok' ? note.text : ''; }
  }

  // ---- 변수 탭 ---------------------------------------------------------------------------------

  drawVars() {
    this.drawVarList();
    this.drawSelBar();
  }

  /** 지금 보이는 차례대로의 변수 이름 — Shift 로 이어 고를 때 */
  visibleNames() { return [...this.varList.querySelectorAll('.var-row[data-var]')].map((n) => n.dataset.var); }

  drawVarList() {
    const box = clear(this.varList);
    if (this.varsError && !this.vars) { box.append(h('div', { class: 'side-note error' }, `변수를 읽지 못했습니다.\n\n${this.varsError}`)); return; }
    if (!this.vars) { box.append(h('div', { class: 'side-note' }, '변수를 읽는 중…')); return; }
    const q = this.q.vars.trim().toLowerCase();
    const hit = (v) => !q || v.name.toLowerCase().includes(q) || (v.desc || '').toLowerCase().includes(q);
    const sec = (key, title, rows, total, tools = null) => {
      const folded = this.folded.has(key) && !q;
      const head = h('button', { class: 'sec-head fold', type: 'button', 'aria-expanded': String(!folded), onclick: () => { if (folded) this.folded.delete(key); else this.folded.add(key); this.save(); this.drawVarList(); } },
        icon('chevron', 'caret'), h('span', {}, title), h('span', { class: 'count' }, total), tools);
      const limit = this.more.has(key) ? Infinity : MAX_ROWS;
      box.append(h('div', { class: 'sec' }, head, folded ? null : rows.slice(0, limit), !folded && rows.length > limit
        ? h('button', { class: 'link more', type: 'button', onclick: () => { this.more.add(key); this.drawVarList(); } }, `${rows.length - limit}개 더 보기`) : null));
    };
    const groups = this.vars.groups.filter((g) => !q || g.name.toLowerCase().includes(q) || g.series.some((s) => s.toLowerCase().includes(q)));
    if (groups.length || !q) {
      sec('g', '묶음', groups.length ? groups.map((g) => this.groupRow(g)) : [h('div', { class: 'side-hint' }, '변수를 여럿 고르고 ‘묶음으로 저장’하면 여기에 남습니다.')], groups.length || '');
    }
    const all = this.vars.variables.filter(hit);
    const starred = all.filter((v) => this.stars.has(v.name));
    if (starred.length) sec('s', '즐겨찾기', starred.map((v) => this.varRow(v, 's')), starred.length);
    const kinds = [...new Set(all.map((v) => v.kind))].sort((a, b) => KIND_ORDER.indexOf(a) - KIND_ORDER.indexOf(b));
    for (const k of kinds) {
      const rows = all.filter((v) => v.kind === k).sort((a, b) => natural(a.name, b.name));
      sec(`k:${k}`, kinds.length === 1 && k === '자료' ? '시리즈' : k, rows.map((v) => this.varRow(v, 'k')), rows.length);
    }
    if (!all.length && q) box.append(h('div', { class: 'side-note' }, `‘${this.q.vars}’ 에 맞는 변수가 없습니다.`));
  }

  groupRow(g) {
    const on = this.group === g.name;
    return h('div', {
      class: `var-row group ${on ? 'on' : ''}`.trim(), role: 'option', tabindex: '0', 'aria-selected': String(on), 'data-group': g.name,
      title: `${g.name}${g.desc ? ` — ${g.desc}` : ''}\n${g.series.join(' · ')}${g.transform ? `\n변환 ${g.transform}` : ''}\n두 번 누르면 그룹 창`,
      onclick: () => this.pickGroup(g.name), ondblclick: () => this.openWindow(),
      oncontextmenu: (e) => { e.preventDefault(); this.pickGroup(g.name); openVarMenu(this.p, { x: e.clientX, y: e.clientY }, this.selection()); },
    }, icon('layers'), h('span', { class: 'vname mono' }, g.name), h('span', { class: 'vdesc' }, g.desc || g.series.join(' · ')), h('span', { class: 'vtail' }, h('span', { class: 'n' }, g.series.length)));
  }

  varRow(v, where) {
    const on = this.sel.includes(v.name);
    const order = on && this.sel.length > 1 ? this.sel.indexOf(v.name) + 1 : null;
    const starred = this.stars.has(v.name);
    const rel = REL[v.rel];
    const relEl = rel ? h(v.parts.length ? 'button' : 'span', {
      class: `rel ${v.rel}`, type: v.parts.length ? 'button' : null,
      title: `${rel[1]}${v.parts.length ? `\n${v.parts.join(' · ')}` : ''}${v.models.length ? `\n모형 ${v.models.join(' · ')}` : ''}${v.users.length ? `\n쓰는 식 ${v.users.join(' · ')}` : ''}`,
      onclick: v.parts.length ? (e) => { e.stopPropagation(); this.p.openTab({ type: 'bench', part: v.parts[0] }); } : null,
    }, rel[0]) : null;
    return h('div', {
      class: `var-row ${on ? 'on' : ''}`.trim(), role: 'option', tabindex: '0', 'aria-selected': String(on), 'data-var': v.name, 'data-where': where,
      title: `${v.name}${v.desc ? ` — ${v.desc}` : ''}${v.unit ? ` (${v.unit})` : ''}\n${v.first ? `${v.first}–${v.last} · ${v.n}개` : '값 없음'}\nCtrl·Shift 로 여럿 · 두 번 누르면 변수 창 · 우클릭 메뉴`,
      onclick: (e) => this.clickVar(v.name, e), ondblclick: (e) => { e.preventDefault(); this.p.openTab({ type: 'var', names: [v.name] }); },
      oncontextmenu: (e) => {
        e.preventDefault();
        if (!this.sel.includes(v.name)) this.select([v.name]);
        openVarMenu(this.p, { x: e.clientX, y: e.clientY }, this.selection());
      },
    },
    h('button', { class: `vstar ${starred ? 'on' : ''}`.trim(), type: 'button', title: starred ? '즐겨찾기에서 빼기' : '즐겨찾기', 'aria-label': '즐겨찾기', tabindex: '-1',
      onclick: (e) => { e.stopPropagation(); if (starred) this.stars.delete(v.name); else this.stars.add(v.name); this.save(); this.drawVarList(); } }, icon('star')),
    order ? h('span', { class: 'vorder' }, order) : null,
    h('span', { class: 'vname mono' }, v.name),
    h('span', { class: 'vdesc' }, v.desc || ''),
    h('span', { class: 'vrange' }, v.first ? `${v.first}–${v.last}` : ''),
    h('span', { class: 'vval' }, v.value != null ? short(v.value) : ''),
    h('span', { class: 'vtail' }, relEl));
  }

  clickVar(name, e) {
    const additive = e.ctrlKey || e.metaKey;
    if (e.shiftKey && this.anchor) {
      const names = this.visibleNames();
      const a = names.indexOf(this.anchor);
      const b = names.indexOf(name);
      if (a >= 0 && b >= 0) {
        const range = names.slice(Math.min(a, b), Math.max(a, b) + 1);
        const base = additive ? this.sel.filter((n) => !range.includes(n)) : [];
        this.sel = [...new Set([...base, ...(a <= b ? range : range.reverse())])];
        this.group = null;
        this.changedSelection();
        return;
      }
    }
    if (additive) {
      this.group = null;
      this.sel = this.sel.includes(name) ? this.sel.filter((n) => n !== name) : [...this.sel, name];
    } else {
      this.group = null;
      this.sel = [name];
    }
    this.anchor = name;
    this.changedSelection();
  }

  select(names) {
    this.group = null;
    this.sel = [...new Set(names)].filter((n) => this.variable(n)).map((n) => this.variable(n).name);
    this.anchor = this.sel[this.sel.length - 1] || null;
    if (this.tab !== 'vars') this.showSide('vars', { save: false });
    this.changedSelection();
  }

  pickGroup(name) {
    this.group = this.group === name ? null : name;
    this.sel = [];
    this.changedSelection();
  }

  clearSelection() { this.sel = []; this.group = null; this.changedSelection(); }

  changedSelection() {
    this.save();
    if (this.tab === 'vars') { this.drawVarList(); this.drawSelBar(); }
    this.p.command?.event({ type: 'selection' });
  }

  /** 고른 것 — {series, group} (메뉴·창이 받는 모양) */
  selection() {
    const g = this.group ? this.groupOf(this.group) : null;
    return { series: g ? [...g.series] : [...this.sel], group: g ? { name: g.name, series: [...g.series], transform: g.transform } : null };
  }

  /** 명령 창이 `an 분석` 뒤에 붙일 대상 글 */
  targetText() {
    const s = this.selection();
    return s.series.length ? targetText(s, this.transform) : '';
  }

  openWindow() {
    const s = this.selection();
    if (!s.series.length) return;
    this.p.openTab({ type: 'var', names: s.series, group: s.group?.name || null });
  }

  drawSelBar() {
    const bar = clear(this.selBar);
    const s = this.selection();
    bar.hidden = !s.series.length;
    if (!s.series.length) return;
    let drag = null;
    const chips = h('div', { class: 'sel-chips' }, s.group
      ? [h('span', { class: 'sel-chip group' }, icon('layers'), h('b', { class: 'mono' }, s.group.name)), h('span', { class: 'muted mono' }, s.series.join(' · '))]
      : this.sel.flatMap((n, i) => [i ? h('span', { class: 'sel-arrow' }, '→') : null, h('span', {
        class: 'sel-chip', draggable: 'true', title: '끌어서 순서를 바꾼다 — ECM 은 첫 변수가 목표, VAR 은 이 차례로',
        ondragstart: (e) => { drag = i; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', n); },
        ondragover: (e) => { e.preventDefault(); e.currentTarget.classList.add('over'); },
        ondragleave: (e) => e.currentTarget.classList.remove('over'),
        ondrop: (e) => {
          e.preventDefault();
          if (drag == null || drag === i) return;
          const next = [...this.sel];
          const [moved] = next.splice(drag, 1);
          next.splice(i, 0, moved);
          this.sel = next;
          this.changedSelection();
        },
      }, h('span', { class: 'mono' }, n), h('button', { class: 'x', type: 'button', title: '빼기', 'aria-label': `${n} 빼기`, onclick: () => { this.sel = this.sel.filter((x) => x !== n); this.changedSelection(); } }, icon('x')))]));
    const n = s.series.length;
    bar.append(
      h('div', { class: 'sel-top' }, h('span', { class: 'k' }, s.group ? '고른 묶음' : `고른 변수 ${n}`), chips),
      h('div', { class: 'sel-acts' },
        h('button', { class: 'btn small primary', type: 'button', 'data-act': 'var-menu', title: '고른 것에 맞는 분석과 일 — 우클릭과 같은 메뉴', onclick: (e) => openVarMenu(this.p, e.currentTarget, this.selection()) }, '할 수 있는 일', icon('chevron', 'down')),
        h('button', { class: 'btn small', type: 'button', 'data-act': 'var-open', title: n > 1 ? '그룹 창 — 값 나란히 · 차트 · 상관' : '변수 창 — 차트 · 값 · 내력 · 분석', onclick: () => this.openWindow() }, icon('window'), n > 1 ? '그룹 창' : '변수 창'),
        !s.group && n > 1 ? h('button', { class: 'btn small', type: 'button', 'data-act': 'save-group', title: 'equion.toml 의 [group] 에 이름을 붙여 둔다', onclick: () => this.saveGroup(this.sel) }, '묶음으로 저장') : null,
        h('span', { class: 'grow' }),
        h('button', { class: 'link', type: 'button', onclick: () => this.clearSelection() }, '지우기')));
  }

  listKey(e) {
    const row = e.target instanceof Element ? e.target.closest('.var-row') : null;
    if (!row) return;
    const rows = [...this.varList.querySelectorAll('.var-row')];
    const i = rows.indexOf(row);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const next = rows[i + (e.key === 'ArrowDown' ? 1 : -1)];
      if (!next) return;
      next.focus();
      if (e.shiftKey && next.dataset.var) { this.anchor ||= row.dataset.var; this.clickVar(next.dataset.var, { shiftKey: true }); this.focusRow(next.dataset.var); }
      return;
    }
    if (e.key === ' ') { e.preventDefault(); if (row.dataset.var) this.clickVar(row.dataset.var, { ctrlKey: true }); else this.pickGroup(row.dataset.group); this.focusRow(row.dataset.var, row.dataset.group); return; }
    if (e.key === 'Enter') { e.preventDefault(); if (row.dataset.var && !this.sel.includes(row.dataset.var)) this.select([row.dataset.var]); else if (row.dataset.group && this.group !== row.dataset.group) this.pickGroup(row.dataset.group); this.openWindow(); return; }
    if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) {
      e.preventDefault();
      if (row.dataset.var && !this.sel.includes(row.dataset.var)) this.select([row.dataset.var]);
      if (row.dataset.group && this.group !== row.dataset.group) this.pickGroup(row.dataset.group);
      const r = row.getBoundingClientRect();
      openVarMenu(this.p, { x: r.left + 40, y: r.bottom }, this.selection());
    }
  }

  focusRow(name, group = null) {
    const sel = name ? `.var-row[data-var="${CSS.escape(name)}"]` : `.var-row[data-group="${CSS.escape(group)}"]`;
    requestAnimationFrame(() => this.varList.querySelector(sel)?.focus());
  }

  // ---- 묶음 ------------------------------------------------------------------------------------

  async saveGroup(names) {
    const name = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: core', spellcheck: 'false', 'aria-label': '묶음 이름' });
    const desc = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '설명(선택)', 'aria-label': '설명' });
    const diffWrap = h('div', {});
    const note = (text, cls = '') => clear(diffWrap).append(h('div', { class: 'diff' }, h('span', { class: `dl ${cls}`.trim() }, text)));
    note('이름을 적으면 바뀔 줄이 보입니다');
    const draw = debounce(async () => {
      const n = name.value.trim();
      if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(n)) { note(n ? '이름은 영문으로 시작 — 영문·숫자·_' : '이름을 적으면 바뀔 줄이 보입니다'); return; }
      try {
        const res = await this.p.post('group/define', { name: n, series: names, desc: desc.value.trim(), dry: true });
        clear(diffWrap).append(diffBlock(res.diff));
      } catch (err) { note(err.message, 'del'); }
    }, 250);
    name.addEventListener('input', draw);
    desc.addEventListener('input', draw);
    const body = h('div', { class: 'adopt define-form' },
      h('p', {}, '고른 변수를 이 차례대로 ', h('b', {}, '묶음'), '으로 남깁니다(', h('code', {}, 'equion.toml'), ' 의 [group]). 분석의 대상으로 이름 하나만 적으면 됩니다.'),
      h('div', { class: 'diff' }, h('span', { class: 'dl' }, names.join(' · '))),
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '설명'), desc),
      h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, 'equion.toml')), diffWrap,
      h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    setTimeout(() => name.focus(), 30);
    if (!(await confirmDialog({ title: '묶음으로 저장', body, confirm: '저장', wide: true }))) return;
    const n = name.value.trim();
    if (!n) return;
    try {
      await this.p.compute('group/define', { name: n, series: names, desc: desc.value.trim() }, { quiet: true });
      await this.loadVars();
      this.pickGroup(n);
      flash(`묶음 ${n} 를 저장했습니다`);
    } catch (err) {
      if (err.kind !== 'busy') this.p.notify({ level: 'error', text: err.message });
    }
  }

  async removeGroup(name) {
    const g = this.groupOf(name);
    const body = h('div', { class: 'adopt' }, h('p', {}, '묶음 ', h('b', { class: 'mono' }, name), ' 를 equion.toml 에서 뺍니다. 변수와 기록은 그대로입니다.'),
      g ? h('div', { class: 'diff' }, h('span', { class: 'dl del' }, `- [group.${name}]  ${g.series.join(', ')}`)) : null,
      h('div', { class: 'cmd-note mono' }, `equion group remove ${name}`));
    if (!(await confirmDialog({ title: '묶음 지우기', body, confirm: '지우기', tone: 'danger', wide: true }))) return;
    try {
      await this.p.compute('group/remove', { name }, { quiet: true });
      if (this.group === name) this.group = null;
      await this.loadVars();
    } catch (err) {
      if (err.kind !== 'busy') this.p.notify({ level: 'error', text: err.message });
    }
  }

  /** '이 변수를 쓰는 식' — 그 이름으로 찾은 모형 탭을 보인다 */
  showUsers(name) {
    const v = this.variable(name);
    const users = v?.users || [];
    if (users.length === 1) { this.p.openTab({ type: 'bench', part: users[0] }); return; }
    import('./dialog.js').then(({ popMenu }) => {
      const anchor = this.varList.querySelector(`.var-row[data-var="${CSS.escape(v.name)}"]`) || this.selBar;
      popMenu(anchor, [h('div', { class: 'menu-title' }, `${v.name} 를 쓰는 식`), ...users.map((p) => ({ label: p, onPick: () => this.p.openTab({ type: 'bench', part: p }) }))], { cls: 'plain' });
    });
  }

  // ---- 분석 탭 ---------------------------------------------------------------------------------

  drawAnalysis() {
    const box = clear(this.panes.analysis);
    const p = this.p;
    const tools = h('div', { class: 'side-actions' },
      h('button', { class: 'btn small', type: 'button', 'data-act': 'new-single', title: '식 작업대에서 식을 써서 추정하고, 마음에 들면 ‘개별 식으로 남기기’', onclick: () => p.openTab({ type: 'bench' }) }, icon('plus'), '새 개별 식'),
      h('button', { class: 'btn small quiet', type: 'button', title: '분석을 골라 옵션을 주고 돌린다', onclick: () => p.openTab({ type: 'analysis' }) }, icon('flask'), '분석 실행'));
    box.append(tools);
    if (this.alistError && !this.alist) { box.append(h('div', { class: 'side-note error' }, this.alistError)); return; }
    if (!this.alist) { box.append(h('div', { class: 'side-note' }, '읽는 중…')); return; }
    const a = this.alist;
    const sec = (key, title, rows, empty) => {
      const folded = this.folded.has(`a:${key}`);
      box.append(h('div', { class: 'sec' },
        h('button', { class: 'sec-head fold', type: 'button', 'aria-expanded': String(!folded), onclick: () => { if (folded) this.folded.delete(`a:${key}`); else this.folded.add(`a:${key}`); this.save(); this.drawAnalysis(); } },
          icon('chevron', 'caret'), h('span', {}, title), h('span', { class: 'count' }, rows.length || '')),
        folded ? null : rows.length ? rows : h('div', { class: 'side-hint' }, empty)));
    };
    const last = p.lastEst();
    sec('singles', '개별 식', a.singles.map((s) => {
      const rec = last.get(s.id);
      const pass = rec?.pass ?? s.last?.pass;
      return h('div', { class: 'row-line' },
        h('button', { class: 'row-item', type: 'button', 'data-key': `bench:${s.id}`, title: `${s.text}\n${s.id}${s.adopted ? `\n채택 ${s.adopted}` : ''}`, onclick: () => p.openTab({ type: 'bench', part: s.id }) },
          h('span', { class: `glyph ${s.kind === 'identity' ? 'identity' : ''}` }, s.kind === 'identity' ? '≡' : 'ƒ'), h('span', { class: 'label mono' }, s.target),
          h('span', { class: 'desc' }, s.desc || s.text), h('span', { class: 'tail' },
            s.adopted ? h('span', { class: 'star', title: `채택: ${s.adopted}` }, '★') : null,
            pass != null ? h('span', { class: `dot ${pass ? 'ok' : 'warn'}`, title: pass ? '기준 통과' : '걸러짐' }) : null,
            h('span', { class: 'mono blk' }, s.block))),
        h('button', { class: 'icon-btn row-more', type: 'button', title: '모형에 넣기 · 빼기', 'aria-label': '더 보기', onclick: (e) => this.singleMenu(e.currentTarget, s) }, icon('more')));
    }), '모형에 넣지 않은 식이 여기에 놓입니다 — ‘새 개별 식’으로 시작하거나, 변수를 골라 ‘이 변수들로 새 식’.');
    const now = Date.now();
    const resRow = (r) => h('div', { class: 'row-line' },
      h('button', { class: 'row-item res', type: 'button', 'data-record': r.id, title: `${r.id}\n${r.line || ''}\n${r.runs > 1 ? `같은 대상에 ${r.runs}번 돌렸다 — 가장 새 것` : ''}`,
        onclick: () => p.openTab({ type: 'analysis', shown: r.id }) },
      h('span', { class: 'albl' }, r.label || r.analysis), h('span', { class: 'label mono' }, r.target_label || r.target),
      h('span', { class: 'desc' }, r.line || ''),
      h('span', { class: 'tail' }, r.stale ? h('span', { class: 'tag warn', title: `자료 회차 ${r.vintage} 로 계산했습니다 — 지금은 ${a.vintage}` }, '낡음') : null,
        r.runs > 1 ? h('span', { class: 'n', title: `${r.runs}번` }, `×${r.runs}`) : null, h('span', { class: 'when' }, when(r.created, now)))),
      h('button', { class: `icon-btn row-more ${r.stale ? 'hot' : ''}`.trim(), type: 'button', 'data-act': 'rerun', title: '같은 설정으로 다시 돌린다(지금 자료로)', 'aria-label': '다시 돌리기',
        onclick: () => p.openTab({ type: 'analysis', analysis: r.analysis, target: r.target, options: r.options || {}, smpl: r.smpl || '', run: true }) }, icon('refresh')));
    const by = (scope) => a.results.filter((r) => r.scope === scope);
    sec('many', '여러 변수의 분석', by('many').map(resRow), '변수 탭에서 여럿을 골라 우클릭 — 상관 · 그랜저 · 공적분 · VAR …');
    sec('one', '한 변수의 분석', by('one').map(resRow), '변수 탭에서 하나를 골라 우클릭 — 기술 통계 · 자기상관 · 단위근 …');
    const other = a.results.filter((r) => !['many', 'one'].includes(r.scope));
    if (other.length) sec('other', '식·모형의 분석', other.map(resRow), '');
    // 노트 — 블록을 매달 다시 실행하는 분석 묶음
    const notes = this.notes || [];
    sec('notes', '노트', notes.map((n) => {
      const c = n.counts || {};
      const old = (c.stale || 0) + (c.missing || 0);
      const never = c.never || 0;
      return h('button', { class: 'row-item', type: 'button', 'data-key': `note:${n.path}`, title: `${n.path}\n실행 블록 ${n.blocks}${n.error ? `\n${n.error}` : ''}`,
        onclick: () => p.openTab({ type: 'note', path: n.path }) },
      icon('doc'), h('span', { class: 'label' }, n.path.replace(/^notes\//, '')), h('span', { class: 'desc' }, n.error ? '읽지 못함' : `블록 ${n.blocks}`),
      h('span', { class: 'tail' }, old ? h('span', { class: 'tag warn', title: '자료 회차나 정의가 바뀌어 다시 실행할 블록' }, `낡음 ${old}`) : null,
        never ? h('span', { class: 'n', title: '아직 실행하지 않은 블록' }, `새 ${never}`) : null));
    }), this.notes ? '분석 결과의 ‘노트에’나 후보 묶음의 ‘노트로 저장’으로 만듭니다 — 다음 회차에 노트 전체를 다시 실행합니다.' : '읽는 중…');
    p.markSide();
  }

  async singleMenu(anchor, s) {
    const { popMenu } = await import('./dialog.js');
    const { toModel, removePart } = await import('./partops.js');
    popMenu(anchor, [
      { label: '식 작업대', hint: '추정 · 후보 · 진단', onPick: () => this.p.openTab({ type: 'bench', part: s.id }) },
      { label: '모형에 넣기…', hint: '모형이 쓰는 블록으로 옮긴다', onPick: async () => { if (await toModel(this.p, { text: s.text, from: s.id, desc: s.desc })) this.loadAnalysisList(); } },
      { label: '빼기…', hint: '블록 파일에서 이 줄을 뺀다', onPick: async () => { if (await removePart(this.p, s.id)) this.loadAnalysisList(); } },
    ], { align: 'right', cls: 'plain' });
  }

  // ---- 기록 탭 ---------------------------------------------------------------------------------

  drawRecords() {
    const box = clear(this.panes.records);
    const p = this.p;
    const nOpen = p.proposals.filter((x) => x.status === 'open').length;
    const sub = h('div', { class: 'segmented small rec-sub', role: 'tablist' },
      h('button', { type: 'button', 'aria-pressed': String(this.recSub === 'results'), 'data-sub': 'results', onclick: () => { this.recSub = 'results'; this.save(); this.drawRecords(); } }, '결과', h('span', { class: 'c' }, p.records.length || '')),
      h('button', { type: 'button', 'aria-pressed': String(this.recSub === 'changes'), 'data-sub': 'changes', onclick: () => { this.recSub = 'changes'; this.save(); if (!this.changes) this.loadChanges(); this.drawRecords(); } },
        '바뀜 · 제안', p.unseenProps.size ? h('span', { class: 'dot prop' }) : nOpen ? h('span', { class: 'c' }, nOpen) : null));
    box.append(h('div', { class: 'side-tools' }, sub, h('span', { class: 'grow' }),
      h('button', { class: 'icon-btn', type: 'button', title: this.recSub === 'results' ? '작업 기록 모두 보기(가운데 — 스크립트로 만들기)' : '바뀜 기록(가운데)', 'aria-label': '가운데에 열기',
        onclick: () => p.openTab({ type: this.recSub === 'results' ? 'records' : 'changes' }) }, icon('external'))));
    const body = h('div', { class: 'side-body' });
    box.append(body);
    if (this.recSub === 'results') this.drawResults(body);
    else this.drawChanges(body);
  }

  drawResults(body) {
    const p = this.p;
    const all = p.records;
    const counts = {};
    for (const r of all) counts[r.kind] = (counts[r.kind] || 0) + 1;
    const filters = h('div', { class: 'filters compact' },
      h('button', { type: 'button', 'aria-pressed': String(this.recFilter === 'all'), onclick: () => { this.recFilter = 'all'; this.save(); this.drawRecords(); } }, '모두'),
      Object.keys(KINDS).filter((k) => counts[k]).map((k) => h('button', { type: 'button', 'aria-pressed': String(this.recFilter === k), 'data-filter': k, onclick: () => { this.recFilter = k; this.save(); this.drawRecords(); } }, KINDS[k], h('span', { class: 'c' }, counts[k]))),
      all.some((r) => r.pinned) ? h('button', { type: 'button', 'aria-pressed': String(this.recFilter === 'pinned'), 'data-filter': 'pinned', onclick: () => { this.recFilter = 'pinned'; this.save(); this.drawRecords(); } }, icon('pin'), '고정') : null);
    body.append(filters);
    const rows = all.filter((r) => this.recFilter === 'all' || (this.recFilter === 'pinned' ? r.pinned : r.kind === this.recFilter)).slice(-300).reverse();
    if (!rows.length) { body.append(h('div', { class: 'side-note' }, '계산하면 기록이 여기에 쌓입니다 — Desk 에서 하든 터미널·Claude 가 하든.')); return; }
    const now = Date.now();
    for (const r of rows) {
      body.append(h('button', { class: `row-item rec ${p.unseen.has(r.id) ? 'unseen' : ''}`.trim(), type: 'button', 'data-key': `record:${r.id}`, 'data-record': r.id,
        title: `${r.id}\n${cmdText(r.command)}\n${WHO[r.who] || r.who || ''} · ${r.created || ''}${r.memo ? `\n“${r.memo}”` : ''}`, onclick: () => p.openRecord(r.id) },
      kindPill(r.kind), h('span', { class: 'label mono' }, String(r.id).split(':').slice(1).join(':')),
      h('span', { class: 'desc' }, r.pinned ? icon('pin') : null, r.metric || ''), h('span', { class: 'tail' }, whoLabel(r.who), h('span', { class: 'when' }, when(r.created, now)))));
    }
    p.markSide();
  }

  drawChanges(body) {
    const p = this.p;
    const now = Date.now();
    const props = p.proposals.filter((x) => x.status === 'open');
    body.append(h('div', { class: 'sec' }, h('div', { class: 'sec-head' }, '열린 제안', h('span', { class: 'count' }, props.length || '')),
      props.length ? props.map((x) => h('button', { class: `row-item ${p.unseenProps.has(x.id) ? 'unseen' : ''}`.trim(), type: 'button', 'data-key': 'proposals', 'data-proposal': x.id,
        title: `${x.title || x.name}\n바꿀 파일 ${x.files.length}`, onclick: () => p.openTab({ type: 'proposals', id: x.id }) },
      icon('spark'), h('span', { class: 'label mono' }, x.name), h('span', { class: 'desc' }, x.title || ''), h('span', { class: 'tail' }, WHO[x.who] || x.who || '', p.unseenProps.has(x.id) ? h('span', { class: 'dot prop' }) : null)))
        : h('div', { class: 'side-hint' }, 'Claude 가 남긴 ‘이렇게 바꾸면’이 여기에 — 적용하기 전에 바뀔 내용을 봅니다.'),
      p.proposals.length > props.length ? h('button', { class: 'link more', type: 'button', onclick: () => p.openTab({ type: 'proposals' }) }, `적용·버린 제안 ${p.proposals.length - props.length}개`) : null));
    const list = this.changes;
    body.append(h('div', { class: 'sec' }, h('div', { class: 'sec-head' }, '바뀜', h('span', { class: 'count' }, list ? list.length || '' : '')),
      !list ? h('div', { class: 'side-note' }, '읽는 중…') : list.length ? [...list].reverse().slice(0, 200).map((c) => h('button', { class: 'row-item chg', type: 'button', 'data-change': c.id,
        title: `${c.id} — ${c.how || ''}\n${c.files.map((f) => f.path).join('\n')}`, onclick: () => p.openTab({ type: 'changes', id: c.id }) },
      icon('history'), h('span', { class: 'label mono' }, c.id), h('span', { class: 'desc' }, c.files.map((f) => f.path.split('/').pop()).join(' · ')),
      h('span', { class: 'tail' }, h('span', { class: `who ${c.who === 'claude' ? 'claude' : ''}`.trim() }, WHO[c.who] || c.who || ''), h('span', { class: 'when' }, when(c.created, now)))))
        : h('div', { class: 'side-hint' }, '정의 파일(equion.toml·블록 파일·자료 정의·가정…)이 바뀌면 전후 차이가 여기에 남습니다.')));
  }

  // ---- 알림 ------------------------------------------------------------------------------------

  event(e) {
    if (e.type === 'defs' || e.type === 'data' || (e.type === 'record' && e.record?.kind === 'data')) { this.reloadVars(); this.reloadList(); }
    if (e.type === 'defs') this.reloadRegistry();
    if (e.type === 'record' && ['an', 'est'].includes(e.record?.kind)) this.reloadList();
    if (e.type === 'change') this.reloadChanges();
    if (['change', 'tree', 'defs', 'data'].includes(e.type) || (e.type === 'record' && e.record?.kind === 'data')) this.reloadNotes();
    if (['record', 'records', 'proposal', 'change'].includes(e.type) && this.tab === 'records') this.drawRecords();
    if (['overview', 'record', 'records', 'proposal', 'change', 'data'].includes(e.type)) this.drawTabs();
    if (e.type === 'overview' && this.tab === 'analysis') this.drawAnalysis();
  }
}
