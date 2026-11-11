// 프로젝트 탭 하나의 화면 — 사이드바(부품·파일) · 가운데 탭들 · 오른쪽 터미널. 프로젝트마다 한 벌씩 만들어 두고 고른 것만 보인다
// (터미널의 글과 스크롤 자리가 탭을 오가도 그대로다).
//
// 화면 상태(연 탭·고른 탭·쓰던 식·펼친 폴더)는 바뀔 때마다 서버의 설정 파일에 적는다 — 닫았다 열면 이어진다.

import { getJSON, papi, postJSON, query } from './api.js';
import { Term } from './terminal.js';
import { clear, debounce, flash, h, icon, kindClass, WHO } from './util.js';
import { analysisView } from './views/analysis.js';
import { benchView } from './views/bench.js';
import { cardView } from './views/card.js';
import { dataView } from './views/data.js';
import { fileView } from './views/file.js';
import { flowView } from './views/flow.js';
import { forecastView } from './views/forecast.js';
import { helpView } from './views/help.js';
import { homeView } from './views/home.js';
import { importView } from './views/importer.js';
import { changesView, recordsView } from './views/lists.js';
import { modelView } from './views/model.js';
import { proposalsView } from './views/proposals.js';
import { reportsView } from './views/reports.js';

const FACTORY = { home: homeView, bench: benchView, record: cardView, file: fileView, records: recordsView, changes: changesView, data: dataView, analysis: analysisView, import: importView, model: modelView, flow: flowView, forecast: forecastView, reports: reportsView, proposals: proposalsView, help: helpView };
const MAX_TABS = 24;       // 가운데 탭 — 넘으면 가장 오래된 것부터 닫는다(작업대가 늘어 14에서 올렸다)
const FILE_ICON = { md: 'doc', csv: 'table', toml: 'code', txt: 'equation', eqs: 'play', json: 'code', xlsx: 'table' };

export class Project {
  constructor(app, tab) {
    this.app = app;
    this.id = tab.id;
    this.root = tab.root;
    this.name = tab.name;
    this.overview = null;
    this.error = null;
    this.worker = null;
    this.records = [];
    this.unseen = new Set();
    this.tabs = new Map();       // key → {view, pane, button}
    this.active = null;
    this.side = 'parts';
    this.expanded = new Set();   // 펼친 폴더(파일 나무)
    this.collapsed = new Set();  // 접은 블록(부품 나무)
    this.dirs = new Map();       // 폴더 → 항목
    this.job = null;
    this.pending = 0;
    this.finished = new Set();   // 응답을 받은 일(job) — 알림 줄의 '끝남'이 오기 전에도 다음 일을 시킬 수 있게
    this.free = 0;
    this.ready = false;
    this.dataInfo = null;        // 자료의 세 층(원자료·시리즈·회차) — 자료 작업대를 처음 열 때 읽는다
    this.dataError = null;
    this.dataWanted = false;
    this.dataChecked = null;     // {vintage, fingerprint} — 만들어 보았더니 값이 같았던 정의·원자료(다시 권하지 않는다)
    this.proposals = [];         // 제안(work/proposals/) — 열림·적용·버림
    this.unseenProps = new Set();
    this.reloadProposals = debounce(() => this.loadProposals(), 200);
    this.saveView = debounce(() => this.persist(), 500);
    this.reloadOverview = debounce(() => this.loadOverview(), 150);
    this.reloadData = debounce(() => { if (this.dataWanted) this.loadData(); }, 500);
    this.build();
  }

  /** 계산이 도는 중인가 — 이 화면이 시킨 일은 응답이 오면 끝난 것이다(알림 줄의 '끝남'은 조금 늦게 온다) */
  get busy() { return this.pending > 0 || ((this.job?.state === 'start' || this.job?.state === 'progress') && !this.finished.has(this.job.job)); }

  get(path) { return getJSON(papi(this.id, path)); }

  post(path, body = {}, options = {}) { return postJSON(papi(this.id, path), body, {}, options); }

  part(id) {
    for (const b of this.overview?.blocks || []) for (const p of b.parts) if (p.id === id) return p;
    return null;
  }

  // ---- 뼈대 ------------------------------------------------------------------------------------

  build() {
    this.partsBox = h('div', { class: 'side-body' });
    this.filesBox = h('div', { class: 'side-body', hidden: true });
    this.sideTabs = h('div', { class: 'side-tabs', role: 'tablist' },
      h('button', { type: 'button', role: 'tab', 'data-side': 'parts', onclick: () => this.showSide('parts') }, '부품'),
      h('button', { type: 'button', role: 'tab', 'data-side': 'files', onclick: () => this.showSide('files') }, '파일'));
    this.tabbar = h('div', { class: 'tabbar', role: 'tablist' });
    this.panes = h('div', { class: 'panes' });
    this.notices = h('div', { class: 'notices', 'aria-live': 'polite' });
    this.termBox = h('div', { class: 'term-body' });
    this.termLamp = h('span', { class: 'lamp off' });
    this.termShell = h('span', {});
    this.term = new Term(this.termBox, this.id, ({ shell, alive }) => {
      this.termLamp.classList.toggle('off', !alive);
      this.termShell.textContent = shell ? `· ${shell}` : alive ? '' : '· 끝남';
    });
    const gSide = h('div', { class: 'gutter g-side', role: 'separator', 'aria-orientation': 'vertical' });
    const gTerm = h('div', { class: 'gutter g-term', role: 'separator', 'aria-orientation': 'vertical' });
    this.el = h('section', { class: 'project', hidden: true, 'data-p': this.id },
      h('aside', { class: 'side', 'aria-label': '사이드바' }, this.sideTabs, this.partsBox, this.filesBox),
      gSide,
      h('section', { class: 'center' }, this.tabbar, this.panes, this.notices),
      gTerm,
      h('aside', { class: 'term', 'aria-label': '터미널' },
        h('div', { class: 'term-head' }, this.termLamp, h('b', {}, '터미널'), this.termShell, h('span', { class: 'grow' }),
          h('button', { class: 'icon-btn', type: 'button', title: '셸을 끝내고 다시 띄운다', onclick: () => this.term.restart() }, icon('refresh'))),
        this.termBox));
    this.app.dragGutter(gSide, 'side');
    this.app.dragGutter(gTerm, 'term');
    this.tabbar.addEventListener('wheel', (e) => { if (e.deltaY) { this.tabbar.scrollLeft += e.deltaY; e.preventDefault(); } }, { passive: false });
    this.partsBox.append(h('div', { class: 'side-note' }, '작업 프로세스를 띄우는 중…'));
  }

  /** 이 탭을 골랐다 — 처음이면 지난 화면을 되살리고 프로젝트를 읽는다 */
  async activate() {
    this.el.hidden = false;
    this.applyLayout();
    if (!this.ready) {
      this.ready = true;
      await this.restore();
      this.loadRecords();
      this.loadOverview();
      this.loadProposals();
    }
    if (this.app.settings.term_visible) this.term.start();
    this.tabs.get(this.active)?.view.show();
  }

  deactivate() { this.el.hidden = true; }

  applyLayout() {
    this.el.classList.toggle('no-side', !this.app.settings.side_visible);
    this.el.classList.toggle('no-term', !this.app.settings.term_visible);
    if (this.app.settings.term_visible && !this.el.hidden) requestAnimationFrame(() => this.term.start());
  }

  async restore() {
    let view = {};
    try { view = (await this.get('view')).view || {}; } catch { /* 처음 */ }
    this.side = view.side === 'files' ? 'files' : 'parts';
    this.expanded = new Set(Array.isArray(view.expanded) ? view.expanded.filter((x) => typeof x === 'string').slice(0, 200) : []);
    this.collapsed = new Set(Array.isArray(view.collapsed) ? view.collapsed.filter((x) => typeof x === 'string').slice(0, 200) : []);
    this.free = Number.isInteger(view.free) ? view.free : 0;
    this.dataChecked = view.dataChecked && typeof view.dataChecked === 'object' ? { vintage: String(view.dataChecked.vintage), fingerprint: String(view.dataChecked.fingerprint) } : null;
    this.openTab({ type: 'home' }, { activate: false, save: false });
    for (const desc of Array.isArray(view.tabs) ? view.tabs.slice(0, MAX_TABS) : []) {
      if (desc && FACTORY[desc.type] && desc.type !== 'home') this.openTab(desc, { activate: false, save: false });
    }
    this.selectTab(this.tabs.has(view.active) ? view.active : 'home', { save: false });
    this.showSide(this.side, { save: false });
  }

  /** 화면 상태를 서버의 설정 파일에 적는다. closing: 창이 닫히는 중 — 요청이 끊기지 않게 */
  persist(closing = false) {
    if (!this.ready) return;
    const tabs = [...this.tabs.values()].map((t) => t.view.desc()).filter((d) => d.type !== 'home');
    this.post('view', { view: { tabs, active: this.active, side: this.side, expanded: [...this.expanded], collapsed: [...this.collapsed], free: this.free, dataChecked: this.dataChecked } },
      { keepalive: closing }).catch(() => {});
  }

  // ---- 읽기 ------------------------------------------------------------------------------------

  async loadOverview() {
    try {
      const res = await this.get('overview');
      this.overview = res.overview;
      this.worker = res.worker;
      this.error = null;
      if (this.overview.project && this.overview.project !== this.name) { this.name = this.overview.project; this.app.renderTabs(); }
    } catch (err) {
      this.error = err.message;
    }
    this.renderParts();
    this.emit({ type: 'overview' });
    this.app.renderStatus();
  }

  /** 자료의 세 층을 읽는다(원자료를 틀대로 읽어 보므로 개요보다 무겁다 — 자료 작업대를 연 뒤부터, 바뀔 때마다) */
  async loadData() {
    this.dataWanted = true;
    const turn = (this.dataTurn = (this.dataTurn || 0) + 1);
    try {
      const info = await this.get('data');
      if (turn !== this.dataTurn) return;
      this.dataInfo = info;
      this.dataError = null;
    } catch (err) {
      if (turn !== this.dataTurn) return;
      this.dataError = err.message;
    }
    this.renderParts();
    this.emit({ type: 'data' });
  }

  /** 지금 회차를 만든 뒤 정의·원자료가 바뀌었는가 — 만들어 보았더니 값이 같았던 것은 뺀다. 돌려주는 것: {definitions, sources} 또는 null */
  dataStale() {
    const d = this.dataInfo;
    if (!d?.stale) return null;
    const c = this.dataChecked;
    return c && c.vintage === d.current && c.fingerprint === d.fingerprint ? null : d.stale;
  }

  /** '자료 만들기'를 누르면 새 회차가 생길 것 같은가(만들어 보았더니 값이 같았던 것은 뺀다) */
  dataPending() {
    const d = this.dataInfo;
    if (!d?.pending) return false;
    const c = this.dataChecked;
    return !(c && c.fingerprint === d.fingerprint && d.vintages.some((v) => v.id === c.vintage));
  }

  /** 자료에 손볼 것이 있는가 — 사이드바의 점과 개요의 한 줄이 쓴다. 아직 읽지 않았으면 null */
  dataNote() {
    const d = this.dataInfo;
    if (!d || d.mode !== 'defs') return null;
    if (d.problems.length) return { level: 'bad', text: '정의 파일을 읽지 못했습니다' };
    if (!d.current) return { level: 'warn', text: '아직 만든 자료가 없습니다' };
    if (this.dataStale()) return { level: 'warn', text: '지금 회차를 만든 뒤 정의·원자료가 바뀌었습니다' };
    const newest = d.vintages[d.vintages.length - 1]?.id;
    if (newest && newest !== d.current) return { level: 'warn', text: `더 새 회차 ${newest} 가 있습니다` };
    if (d.inbox.length) return { level: 'warn', text: `받은 상자에 새 파일 ${d.inbox.length}개` };
    return { level: 'ok', text: '원자료·정의와 같습니다' };
  }

  async loadRecords() {
    try { this.records = (await this.get('records')).records; } catch { this.records = []; }
    this.emit({ type: 'records' });
    this.renderParts();
    this.app.renderActivity();
  }

  // ---- 계산 ------------------------------------------------------------------------------------

  /** 작업 프로세스에 계산을 시킨다. quiet 면 결과 탭을 열지 않고 오류도 부른 쪽이 다룬다(식 작업대) */
  async compute(op, body, { quiet = false } = {}) {
    if (this.busy) { flash('계산이 도는 중입니다 — 끝난 뒤에 다시 누르세요'); throw Object.assign(new Error('busy'), { kind: 'busy' }); }
    this.pending++;
    this.app.renderActivity();
    this.emit({ type: 'job' });
    try {
      const res = await this.post(op, body);
      if (res.job) { if (this.finished.size > 40) this.finished.clear(); this.finished.add(res.job); }
      const id = res.result?.id;
      if (id) this.seen(id);
      if (!quiet && id) this.openTab({ type: 'record', id });
      return res;
    } catch (err) {
      if (quiet) throw err;
      if (err.kind !== 'cancelled') this.notify({ level: 'error', text: err.message, detail: err.detail });
      return null;
    } finally {
      this.pending--;
      this.app.renderActivity();
      this.emit({ type: 'job' });
    }
  }

  cancel() { return this.post('cancel').catch(() => {}); }

  async sendToTerminal(text) {
    if (!this.app.settings.term_visible) await this.app.setSetting('term_visible', true);
    const ok = await this.term.paste(`${text} `);
    flash(ok ? '터미널에 붙였습니다 — Enter 를 누르면 실행됩니다' : '터미널이 꺼져 있습니다 — ‘다시 시작’을 누르세요');
  }

  // ---- 가운데 탭 --------------------------------------------------------------------------------

  keyOf(desc) {
    if (desc.type === 'bench') return desc.part ? `bench:${desc.part}` : `bench:~${desc.free}`;
    if (desc.type === 'record') return `record:${desc.id}`;
    if (desc.type === 'file') return `file:${desc.path}`;
    if (desc.type === 'model') return `model:${desc.model}`;
    if (desc.type === 'flow') return `flow:${desc.path}`;
    return desc.type;
  }

  openTab(desc, { activate = true, save = true, replace = false } = {}) {
    if (desc.type === 'bench' && !desc.part && desc.free == null) desc = { ...desc, free: ++this.free };
    const key = this.keyOf(desc);
    let tab = this.tabs.get(key);
    if (tab && replace) { this.closeTab(key, { save: false, select: false }); tab = null; }
    if (!tab) {
      if (this.tabs.size >= MAX_TABS) {
        // 가장 오래된(맨 왼쪽) 닫을 수 있는 탭을 닫는다
        const old = [...this.tabs.values()].find((t) => !t.view.pinned && t.view.key !== this.active);
        if (old) this.closeTab(old.view.key, { save: false, select: false });
      }
      const view = FACTORY[desc.type](this, desc);
      const pane = h('div', { class: 'pane', hidden: true, role: 'tabpanel' }, view.el);
      const button = this.tabButton(view);
      this.panes.append(pane);
      this.tabbar.append(button);
      tab = { view, pane, button };
      this.tabs.set(key, tab);
    } else if (typeof tab.view.open === 'function') tab.view.open(desc);      // 이미 연 탭 — 무엇을 보일지만 넘긴다(쓰던 것은 그대로)
    if (activate) this.selectTab(key, { save: false });
    if (save) this.saveView();
    return tab.view;
  }

  tabButton(view) {
    const mark = view.kind ? h('span', { class: `kdot ${kindClass(view.kind)}` }) : icon(view.icon || 'file');
    const button = h('div', {
      class: `tab ${view.pinned ? 'pinned' : ''}`.trim(), role: 'tab', tabindex: '0', title: view.title,
      onclick: () => this.selectTab(view.key),
      onauxclick: (e) => { if (e.button === 1 && !view.pinned) { e.preventDefault(); this.closeTab(view.key); } },
      onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.selectTab(view.key); } },
    }, mark, h('span', { class: `title ${view.mono ? 'mono' : ''}`.trim() }, view.title));
    if (!view.pinned) {
      button.append(h('button', { class: 'x', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: (e) => { e.stopPropagation(); this.closeTab(view.key); } }, icon('x')));
    }
    return button;
  }

  selectTab(key, { save = true } = {}) {
    if (!this.tabs.has(key)) return;
    this.active = key;
    for (const [k, t] of this.tabs) {
      const on = k === key;
      t.pane.hidden = !on;
      t.button.setAttribute('aria-selected', String(on));
      if (on) { t.button.scrollIntoView({ block: 'nearest', inline: 'nearest' }); if (!this.el.hidden) t.view.show(); }
    }
    const view = this.tabs.get(key).view;
    if (view.type === 'record') this.seen(view.key.slice(7));
    if (view.type === 'changes') {
      this.app.clearChanges(this);
      for (const card of this.notices.querySelectorAll('.notice[data-change]')) card.remove();      // 목록에서 보면 된다
    }
    this.markSide();
    if (save) this.saveView();
  }

  closeTab(key, { save = true, select = true } = {}) {
    const tab = this.tabs.get(key);
    if (!tab || tab.view.pinned) return;
    const keys = [...this.tabs.keys()];
    const next = keys[keys.indexOf(key) + 1] || keys[keys.indexOf(key) - 1] || 'home';
    tab.view.dispose();
    tab.pane.remove();
    tab.button.remove();
    this.tabs.delete(key);
    if (select && this.active === key) this.selectTab(next, { save: false });
    if (save) this.saveView();
  }

  openRecord(id) {
    this.seen(id);
    return this.openTab({ type: 'record', id });
  }

  async loadProposals() {
    try { this.proposals = (await this.get('proposals')).proposals; } catch { this.proposals = []; }
    for (const id of [...this.unseenProps]) if (!this.proposals.some((p) => p.id === id && p.status === 'open')) this.unseenProps.delete(id);
    this.renderParts();
  }

  seenProposal(id) {
    if (this.unseenProps.delete(id)) this.renderParts();
    this.notices.querySelector(`[data-key="${CSS.escape(id)}"]`)?.remove();
  }

  /** 이름으로 화면을 연다 — `equion desk show <이름>` 이 시킨 것(화면 이동만) */
  showByName(name, kind) {
    const PLACE = { home: 'home', data: 'data', analysis: 'analysis', forecast: 'forecast', reports: 'reports', records: 'records', changes: 'changes', proposals: 'proposals' };
    if (kind === 'record') return this.openRecord(name);
    if (kind === 'proposal') return this.openTab({ type: 'proposals', id: name });
    if (kind === 'data') return this.openTab({ type: 'data' });
    if (kind === 'part') return this.openTab({ type: 'bench', part: name });
    if (kind === 'model') return this.openTab({ type: 'model', model: name.replace(/^model:/, '') });
    if (kind === 'file') return this.openTab(/^FLOWS\/[^/]+\.eqs$/.test(name) ? { type: 'flow', path: name } : { type: 'file', path: name });
    if (kind === 'place' && PLACE[name]) return this.openTab({ type: PLACE[name] });
    return null;
  }

  seen(id) {
    if (this.unseen.delete(id)) this.app.renderActivity();
  }

  emit(event) {
    for (const { view } of this.tabs.values()) { try { view.event(event); } catch (err) { console.error(err); } }
  }

  // ---- 사이드바 ---------------------------------------------------------------------------------

  showSide(name, { save = true } = {}) {
    this.side = name;
    for (const b of this.sideTabs.children) b.setAttribute('aria-selected', String(b.dataset.side === name));
    this.partsBox.hidden = name !== 'parts';
    this.filesBox.hidden = name !== 'files';
    if (name === 'files' && !this.dirs.has('')) this.loadDir('').then(() => Promise.all([...this.expanded].map((d) => this.loadDir(d)))).then(() => this.renderFiles());
    if (save) this.saveView();
  }

  /** 부품마다 가장 최근 추정 기록의 판단 기준(통과·걸러짐) */
  lastEst() {
    const out = new Map();
    for (const r of this.records) if (r.kind === 'est' && r.part) out.set(r.part, r);
    return out;
  }

  renderParts() {
    const box = clear(this.partsBox);
    const o = this.overview;
    if (!o) {
      box.append(h('div', { class: `side-note ${this.error ? 'error' : ''}`.trim() }, this.error ? `프로젝트를 읽지 못했습니다.\n\n${this.error}` : '작업 프로세스를 띄우는 중…'));
      return;
    }
    if (this.error) box.append(h('div', { class: 'side-note error' }, `정의 파일에 문제가 있습니다 — 지난 내용을 보이고 있습니다.\n\n${this.error}`));
    const last = this.lastEst();
    const sec = (title, count, rows) => h('div', { class: 'sec' }, h('div', { class: 'sec-head' }, title, h('span', { class: 'count' }, count)), rows);

    // 작업대 — 식은 아래 블록에서, 모형(조립·과거 재현)은 아래 모형에서 고르고, 자료·분석·전망·보고서는 여기서 연다
    const note = this.dataNote();
    const nAn = this.records.filter((r) => r.kind === 'an').length;
    const nSim = this.records.filter((r) => r.kind === 'sim').length;
    const nOpen = this.proposals.filter((p) => p.status === 'open').length;
    box.append(sec('작업대', '', [
      h('button', { class: 'row-item', type: 'button', 'data-key': 'data', title: note ? `자료 — ${note.text}` : '자료 — 원자료 · 시리즈 · 회차', onclick: () => this.openTab({ type: 'data' }) },
        icon('data'), h('span', { class: 'label' }, '자료'), h('span', { class: 'desc mono' }, o.vintage?.id || (o.data_file || '').split('/').pop() || ''),
        h('span', { class: 'tail' }, note && note.level !== 'ok' ? h('span', { class: `dot ${note.level}` }) : null)),
      h('button', { class: 'row-item', type: 'button', 'data-key': 'analysis', title: '분석 — 요약·단위근·공적분·계절조정·ECM·VAR…', onclick: () => this.openTab({ type: 'analysis' }) },
        icon('flask'), h('span', { class: 'label' }, '분석'), h('span', { class: 'desc' }, ''), h('span', { class: 'tail' }, nAn || null)),
      h('button', { class: 'row-item', type: 'button', 'data-key': 'forecast', title: '전망 — 가정을 적고 기준선과 시나리오를 푼다', onclick: () => this.openTab({ type: 'forecast' }) },
        icon('forward'), h('span', { class: 'label' }, '전망'), h('span', { class: 'desc mono' }, o.forecast?.model || ''), h('span', { class: 'tail' }, nSim || null)),
      h('button', { class: 'row-item', type: 'button', 'data-key': 'reports', title: '보고서 — 글 사이에 기록에서 보낸 표·차트. 새 기록으로 바꾼다', onclick: () => this.openTab({ type: 'reports' }) },
        icon('doc'), h('span', { class: 'label' }, '보고서'), h('span', { class: 'desc' }, ''), h('span', { class: 'tail' }, o.reports || null)),
      h('button', { class: 'row-item', type: 'button', 'data-key': 'proposals', title: nOpen ? `제안 — 열린 제안 ${nOpen}개(적용하기 전에 바뀔 내용을 본다)` : '제안 — Claude 가 남긴 “이렇게 바꾸면”을 적용하기 전에 본다', onclick: () => this.openTab({ type: 'proposals' }) },
        icon('spark'), h('span', { class: 'label' }, '제안'), h('span', { class: 'desc' }, nOpen ? `열림 ${nOpen}` : ''), h('span', { class: 'tail' }, this.unseenProps.size ? h('span', { class: 'dot prop', title: '아직 보지 않은 제안' }) : (this.proposals.length || null))),
    ]));

    box.append(sec('모형', o.models.length, o.models.map((m) => h('button', {
      class: 'row-item', type: 'button', 'data-key': `model:${m.name}`, title: `${m.desc || m.name} — 조립과 과거 재현`, onclick: () => this.openTab({ type: 'model', model: m.name }),
    }, h('span', { class: 'glyph model' }, 'M'), h('span', { class: 'label mono' }, m.name), h('span', { class: 'desc' }, m.desc || '')))));

    const blocks = o.blocks.map((b) => {
      const open = !this.collapsed.has(b.name);
      const head = h('button', {
        class: 'row-item', type: 'button', 'aria-expanded': String(open), title: b.file,
        onclick: () => { if (open) this.collapsed.add(b.name); else this.collapsed.delete(b.name); this.renderParts(); this.saveView(); },
      }, icon('chevron', 'caret'), h('span', { class: 'label mono' }, b.name), h('span', { class: 'desc' }, b.desc || ''), h('span', { class: 'tail' }, b.parts.length));
      const rows = open ? b.parts.map((p) => {
        const rec = last.get(p.id);
        const tail = [];
        if (p.adopted) tail.push(h('span', { class: 'star', title: `채택: ${p.adopted}` }, '★'));
        if (rec && rec.pass != null) tail.push(h('span', { class: `dot ${rec.pass ? 'ok' : 'warn'}`, title: `${rec.id} — ${rec.pass ? '기준 통과' : '걸러짐'} · ${rec.metric || ''}` }));
        return h('button', {
          class: 'row-item', type: 'button', 'data-key': `bench:${p.id}`, style: { '--indent': '33px' }, title: `${p.text}\n${p.where}`,
          onclick: () => this.openTab({ type: 'bench', part: p.id }),
        }, h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'),
        h('span', { class: 'label mono' }, p.target), h('span', { class: 'desc' }, p.desc || ''), h('span', { class: 'tail' }, tail));
      }) : [];
      return [head, ...rows];
    });
    box.append(sec('블록', o.blocks.length, blocks));

    const fileRow = (label, path, kind) => h('button', {
      class: 'row-item', type: 'button', 'data-key': `file:${path}`, title: path, onclick: () => this.openTab({ type: 'file', path }),
    }, icon(kind), h('span', { class: 'label' }, label), h('span', { class: 'desc' }, path));
    const more = [
      ...o.assumptions.map((n) => fileRow(n, `ASSUMPTIONS/${n}.csv`, 'table')),
      ...o.scenarios.map((n) => fileRow(n, `SCENARIOS/${n}.toml`, 'layers')),
      ...o.scripts.map((n) => h('button', { class: 'row-item', type: 'button', 'data-key': `flow:FLOWS/${n}.eqs`, title: `FLOWS/${n}.eqs — 단계를 보고 실행한다`,
        onclick: () => this.openTab({ type: 'flow', path: `FLOWS/${n}.eqs` }) }, icon('play'), h('span', { class: 'label' }, n), h('span', { class: 'desc' }, `FLOWS/${n}.eqs`))),
    ];
    if (more.length) box.append(sec('가정 · 시나리오 · 스크립트', more.length, more));
    this.markSide();
  }

  markSide() {
    for (const row of this.el.querySelectorAll('.side .row-item[data-key]')) row.classList.toggle('on', row.dataset.key === this.active);
  }

  async loadDir(path) {
    try {
      this.dirs.set(path, (await this.get(`tree${query({ path })}`)).entries);
    } catch {
      this.dirs.delete(path);
      this.expanded.delete(path);
    }
  }

  renderFiles() {
    const box = clear(this.filesBox);
    const rows = [];
    const walk = (dir, depth) => {
      for (const e of this.dirs.get(dir) || []) {
        const path = dir ? `${dir}/${e.name}` : e.name;
        const indent = `${14 + depth * 14}px`;
        if (e.dir) {
          const open = this.expanded.has(path);
          rows.push(h('button', {
            class: 'row-item', type: 'button', 'aria-expanded': String(open), style: { '--indent': indent }, title: path,
            onclick: async () => {
              if (open) this.expanded.delete(path); else { this.expanded.add(path); await this.loadDir(path); }
              this.renderFiles();
              this.saveView();
            },
          }, icon('chevron', 'caret'), h('span', { class: 'label' }, e.name)));
          if (open) walk(path, depth + 1);
        } else {
          const ext = (/\.([^.]+)$/.exec(e.name)?.[1] || '').toLowerCase();
          rows.push(h('button', {
            class: 'row-item', type: 'button', 'data-key': `file:${path}`, style: { '--indent': `${14 + depth * 14 + 19}px` }, title: path,
            onclick: () => this.openTab({ type: 'file', path }),
          }, icon(FILE_ICON[ext] || 'file'), h('span', { class: 'label' }, e.name)));
        }
      }
    };
    walk('', 0);
    if (rows.length) box.append(...rows); else box.append(h('div', { class: 'side-note' }, '파일을 읽는 중…'));
    this.markSide();
  }

  async refreshFiles() {
    if (!this.dirs.has('')) return;
    await this.loadDir('');
    await Promise.all([...this.expanded].map((d) => this.loadDir(d)));
    this.renderFiles();
  }

  // ---- 알림 ------------------------------------------------------------------------------------

  /** 가운데 오른쪽 위의 알림 카드. actions: [[이름, 함수]] */
  notify({ level = 'warn', text, sub = null, detail = null, actions = [], key = null, timeout = 0 }) {
    if (key) this.notices.querySelector(`[data-key="${CSS.escape(key)}"]`)?.remove();
    const card = h('div', { class: `notice ${level}`, role: 'status', 'data-key': key, 'data-change': /^h\d+$/.test(key || '') ? '' : null },
      icon(level === 'info' ? 'info' : level === 'error' ? 'alert' : 'history'),
      h('div', { class: 'text' }, text, detail ? h('pre', { style: { margin: '6px 0 0', 'white-space': 'pre-wrap', font: 'var(--fs-xs)/1.5 var(--font-mono)', color: 'var(--ink-3)', 'max-height': '120px', overflow: 'auto' } }, detail) : null),
      h('button', { class: 'icon-btn', type: 'button', title: '닫기', style: { width: '22px', height: '22px' }, onclick: () => card.remove() }, icon('x')),
      sub ? h('div', { class: 'sub' }, sub) : null,
      actions.length ? h('div', { class: 'actions' }, actions.map(([label, fn, primary]) => h('button', {
        class: `btn small ${primary ? 'primary' : ''}`.trim(), type: 'button', onclick: () => { card.remove(); fn(); },
      }, label))) : null);
    this.notices.prepend(card);
    while (this.notices.children.length > 4) this.notices.lastChild.remove();
    if (timeout) setTimeout(() => card.remove(), timeout);
    return card;
  }

  changed(change, offline = false) {
    const files = change.files.map((f) => f.path);
    const who = change.who === '바깥' ? '명령 밖에서(편집기·직접 편집)' : `${WHO[change.who] || change.who}${change.how ? ` — ${change.how}` : ''}`;
    const text = h('span', {}, offline ? 'Desk 가 꺼져 있는 동안 ' : '', files.length === 1 ? [h('b', {}, files[0]), ' 파일이 바뀌었습니다.'] : [h('b', {}, `정의 파일 ${files.length}개`), '가 바뀌었습니다.']);
    this.notify({
      level: 'warn', key: change.id, text,
      sub: [h('span', {}, who), h('span', {}, h('span', { class: 'plus' }, `+${change.plus}`), ' ', h('span', { class: 'minus' }, `−${change.minus}`)), h('span', { class: 'mono' }, change.id)],
      actions: [['차이 보기', () => this.openTab({ type: 'changes', id: change.id }), true]],
      timeout: 30000,
    });
  }

  // ---- 서버가 알려 온 것 -------------------------------------------------------------------------

  onEvent(e) {
    if (e.type === 'record') {
      const r = e.record;
      if (!this.records.some((x) => x.id === r.id)) this.records.push(r);
      if (!this.tabs.has(`record:${r.id}`) && !(r.who === 'desk' && this.app.current === this)) this.unseen.add(r.id);
      r.fresh = true;
      if (r.kind === 'data') this.reloadData();        // 터미널·Claude 가 만든 회차도 곧 보이게
      this.renderParts();
      this.emit({ type: 'record', record: r });
      this.app.renderActivity();
    } else if (e.type === 'change') {
      this.offlineIds ||= new Set();
      // 방금 이 화면에서 한 일(채택 등)은 알림 카드를 띄우지 않는다 — 한 사람이 이미 안다. 바뀜 기록에는 똑같이 남는다.
      // 이 화면에서 실행한 스크립트가 고친 것도 같다(단계마다 카드가 쌓여 화면을 가린다 — 흐름 화면의 단계 줄과 실행 기록이 말한다)
      const mine = e.change.who === 'desk' || (e.change.who === 'script' && performance.now() < (this.scriptUntil || 0));
      if (!mine) {
        this.changed(e.change, this.offlineIds.has(e.change.id));
        this.app.countChange(this);
      }
      this.emit(e);
    } else if (e.type === 'offline') {
      (this.offlineIds ||= new Set()).add(e.change);
      const card = this.notices.querySelector(`[data-key="${CSS.escape(e.change)}"] .text`);
      if (card && !card.textContent.startsWith('Desk')) card.prepend('Desk 가 꺼져 있는 동안 ');
    } else if (e.type === 'proposal') {
      const p = e.proposal;
      if (p && e.new && p.status === 'open' && this.active !== 'proposals') { this.unseenProps.add(p.id); this.renderParts(); }
      if (p && e.new && p.status === 'open') {
        this.notify({ level: 'info', key: p.id, timeout: 45000,
          text: h('span', {}, h('b', {}, `${WHO[p.who] || p.who || ''} 제안 ${p.name}`.trim()), p.title ? ` — ${p.title}` : ''),
          sub: [h('span', {}, `바꿀 파일 ${p.files.length}`), h('span', {}, '아직 아무것도 바뀌지 않았습니다')],
          actions: [['제안 보기', () => this.openTab({ type: 'proposals', id: p.id }), true]] });
      }
      this.reloadProposals();
      this.emit(e);
    } else if (e.type === 'show') {
      if (this.app.current !== this) this.app.select(this.id);
      const view = this.showByName(e.show, e.kind);
      if (view) flash(`${WHO[e.who] || e.who || '터미널'} — ${e.show} 화면을 열었습니다`);
    } else if (e.type === 'defs') {
      this.reloadOverview();
      this.reloadData();
      this.emit(e);
    } else if (e.type === 'tree') {
      this.refreshFiles();
      this.reloadData();           // 원자료·받은 상자·회차 폴더가 바뀌었을 수 있다
      this.emit(e);
    } else if (e.type === 'job') {
      if (e.op === 'script_run') this.scriptUntil = e.state === 'start' || e.state === 'progress' ? Infinity : performance.now() + 4000;
      if (e.state === 'start') this.job = { ...e, began: performance.now() };
      else if (e.state === 'progress') this.job = { ...(this.job || { began: performance.now() }), ...e };       // 하는 동안의 알림(스크립트의 단계)
      else {
        this.job = { ...e, ended: performance.now() };
        const mine = this.job;
        setTimeout(() => { if (this.job === mine) { this.job = null; this.app.renderActivity(); } }, e.state === 'done' ? 7000 : 12000);
      }
      this.app.renderActivity();
      this.app.renderTabs();
      this.emit({ type: 'job' });
    }
  }

  /** 알림 줄이 끊겼다 이어졌다(서버를 다시 띄움 등) — 목록을 통째로 다시 읽는다 */
  resync() {
    if (!this.ready) return;
    this.loadRecords();
    this.loadOverview();
    this.loadProposals();
    this.refreshFiles();
    this.reloadData();
  }

  dispose() {
    for (const { view } of this.tabs.values()) view.dispose();
    this.term.dispose();
    this.el.remove();
  }
}
