// Equion Desk — 앱의 틀: 제목줄(프로젝트 탭·도구) · 무대(프로젝트마다 한 벌) · 작업 줄과 작업 기록 띠 · 상태줄.
// 서버의 알림 줄(/api/events)을 받아 프로젝트 화면에 넘긴다 — 터미널에서 친 명령의 기록이 생기는 순간 띠에 뜬다.

import { getJSON, listen, postJSON, ready } from './api.js';
import { LOGO } from './icons.js';
import { recolorCharts } from './md.js';
import { Project } from './project.js';
import { clear, cmdText, debounce, h, icon, kindPill, seconds, when, whoLabel } from './util.js';

const $ = (id) => /** @type {HTMLElement} */ (document.getElementById(id));
const root = document.documentElement;
const dark = window.matchMedia('(prefers-color-scheme: dark)');

const app = {
  state: null,
  settings: { theme: 'auto', font_scale: 100, side_width: null, term_width: null, side_visible: true, term_visible: true, term_follow: true },
  projects: new Map(),
  current: null,
  changes: new Map(),      // 프로젝트 → 아직 보지 않은 바뀜 수
  notice: null,

  // ---- 설정 ------------------------------------------------------------------------------------

  applySettings() {
    const s = this.settings;
    const theme = s.theme === 'auto' ? (dark.matches ? 'dark' : 'light') : s.theme;
    const termDark = s.term_follow === false;          // 터미널 색: 창의 바탕을 따른다(기본) · 늘 어둡게
    const changed = root.dataset.theme !== theme;
    const termChanged = changed || root.classList.contains('term-dark') !== termDark;
    root.dataset.theme = theme;
    root.classList.toggle('term-dark', termDark);
    root.style.setProperty('--scale', String(s.font_scale / 100));
    if (s.side_width) root.style.setProperty('--side-w', `${s.side_width}px`); else root.style.removeProperty('--side-w');
    if (s.term_width) root.style.setProperty('--term-w', `${s.term_width}px`); else root.style.removeProperty('--term-w');
    $('btn-side').setAttribute('aria-pressed', String(s.side_visible));
    $('btn-term').setAttribute('aria-pressed', String(s.term_visible));
    for (const p of this.projects.values()) { p.applyLayout(); if (termChanged) p.term.retheme(); }
    if (changed) recolorCharts();
  },

  saveSettings: debounce((patch) => postJSON('/api/settings', patch).catch(() => {}), 300),

  async setSetting(key, value) {
    this.settings[key] = value;
    this.applySettings();
    this.saveSettings({ ...this.settings });
  },

  /** 사이드바·터미널의 경계를 끌어 폭을 바꾼다 */
  dragGutter(bar, which) {
    bar.addEventListener('pointerdown', (down) => {
      bar.setPointerCapture(down.pointerId);
      bar.classList.add('dragging');
      const move = (e) => {
        const total = window.innerWidth;
        if (which === 'side') this.settings.side_width = Math.round(Math.min(Math.max(e.clientX, 190), Math.min(560, total - 700)));
        else this.settings.term_width = Math.round(Math.min(Math.max(total - e.clientX, 260), total - 420 - (this.settings.side_visible ? 200 : 0)));
        this.applySettings();
      };
      const up = () => {
        bar.classList.remove('dragging');
        bar.removeEventListener('pointermove', move);
        this.saveSettings({ ...this.settings });
      };
      bar.addEventListener('pointermove', move);
      bar.addEventListener('pointerup', up, { once: true });
      bar.addEventListener('pointercancel', up, { once: true });
    });
    bar.addEventListener('dblclick', () => this.setSetting(which === 'side' ? 'side_width' : 'term_width', null));
  },

  // ---- 프로젝트 탭 ------------------------------------------------------------------------------

  /** 서버의 탭 목록에 화면을 맞춘다 */
  syncTabs(state) {
    this.state = state;
    const ids = new Set(state.tabs.map((t) => t.id));
    for (const [id, p] of this.projects) if (!ids.has(id)) { p.dispose(); this.projects.delete(id); this.changes.delete(p); }
    const ordered = new Map();
    for (const tab of state.tabs) {
      let p = this.projects.get(tab.id);
      if (!p) { p = new Project(this, tab); $('stage').append(p.el); }
      ordered.set(tab.id, p);
    }
    this.projects = ordered;
    this.select(state.active && ordered.has(state.active) ? state.active : (ordered.keys().next().value ?? null), { tell: false });
  },

  select(id, { tell = true } = {}) {
    const next = id ? this.projects.get(id) : null;
    if (this.current !== next) {
      this.current?.deactivate();
      this.current = next;
    }
    $('welcome').hidden = !!next;
    next?.activate();
    if (!next) this.renderWelcome();
    if (tell && next) postJSON('/api/tabs/active', { id }).catch(() => {});
    document.title = next ? `Equion Desk — ${next.name}` : 'Equion Desk';
    this.renderTabs();
    this.renderActivity();
    this.renderStatus();
    this.renderChangesBadge();
  },

  renderTabs() {
    const bar = clear($('ptabs'));
    for (const p of this.projects.values()) {
      bar.append(h('div', {
        class: 'ptab', role: 'tab', tabindex: '0', 'aria-selected': String(p === this.current), title: p.root,
        onclick: () => this.select(p.id),
        onauxclick: (e) => { if (e.button === 1) { e.preventDefault(); this.closeProject(p.id); } },
        onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.select(p.id); } },
      }, p.job?.state === 'start' || p.job?.state === 'progress' ? h('span', { class: 'busy-dot', title: '계산 중' }) : null, h('span', { class: 'name' }, p.name),
      h('button', { class: 'x', type: 'button', title: '프로젝트 탭 닫기', 'aria-label': '닫기', onclick: (e) => { e.stopPropagation(); this.closeProject(p.id); } }, icon('x'))));
    }
  },

  async closeProject(id) {
    this.projects.get(id)?.persist();
    try { this.syncTabs(await postJSON('/api/tabs/close', { id })); } catch (err) { this.say(err.message, 'error'); }
  },

  async openProject(path, body = {}) {
    this.notice = null;
    try {
      const res = await postJSON(path, body);
      if (res.id) this.syncTabs(res);
    } catch (err) {
      this.say(err.message, 'error');
    }
  },

  /** 앱이 알릴 말 — 연 프로젝트가 있으면 그 화면의 알림 카드로, 없으면 첫 화면에 */
  say(text, level = 'info') {
    if (this.current) this.current.notify({ level, text, timeout: level === 'error' ? 0 : 8000 });
    else { this.notice = { text, level }; this.renderWelcome(); }
  },

  // ---- 첫 화면 ---------------------------------------------------------------------------------

  renderWelcome() {
    const box = clear($('welcome'));
    const logo = h('div', { class: 'logo' });
    logo.innerHTML = LOGO;
    const recent = (this.state?.recent || []).slice(0, 6);
    box.append(h('div', { class: 'welcome-card' }, logo,
      h('h1', {}, 'Equion Desk'),
      h('p', { class: 'lede' }, '방정식 모형을 만들고, 과거를 재현해 검증하고, 전망합니다. 프로젝트 폴더를 열면 식·모형·기록이 화면에 놓이고, 터미널에서 친 명령의 결과도 같은 자리에 뜹니다.'),
      h('div', { class: 'actions' },
        h('button', { class: 'btn primary', type: 'button', disabled: !this.state?.can_pick, title: this.state?.can_pick ? '' : '폴더 고르기는 앱 창에서만 됩니다', onclick: () => this.openProject('/api/open') }, icon('folder'), '폴더 열기…'),
        h('button', { class: 'btn', type: 'button', onclick: () => this.openProject('/api/example') }, icon('spark'), '예제 프로젝트 만들기'),
        h('button', { class: 'btn quiet', type: 'button', 'data-act': 'help', title: '도움말 (F1)', onclick: () => this.openHelp() }, icon('info'), '도움말')),
      h('p', { class: 'hint' }, 'Equion 프로젝트 폴더는 ', h('code', {}, 'equion.toml'), ' 이 있는 폴더입니다. 예제는 문서 폴더의 ', h('code', {}, 'Equion/example1'),
        ' 에 만듭니다(가상 분기 모형 — 실제 자료가 아닙니다).'),
      this.notice ? h('div', { class: 'error' }, this.notice.text) : null,
      recent.length ? h('div', { class: 'recent' }, h('h2', {}, '최근 프로젝트'), recent.map((path) => h('button', {
        type: 'button', title: path, onclick: () => this.openProject('/api/open', { root: path }),
      }, h('span', { class: 'n' }, path.split(/[\\/]/).filter(Boolean).pop()), h('span', { class: 'p' }, path)))) : null));
  },

  // ---- 작업 줄 · 작업 기록 띠 --------------------------------------------------------------------

  renderActivity() {
    const p = this.current;
    $('activity').hidden = !p;
    if (!p) return;
    const jobBox = clear($('job'));
    clearInterval(this.jobTimer);
    const job = p.job || (p.pending ? { state: 'start', label: '계산', began: performance.now(), who: 'desk' } : null);
    if (job?.state === 'start' || job?.state === 'progress') {
      const time = h('span', { class: 'time' }, '0.0초');
      const step = /^\[(\d+\/\d+)\]/.exec(job.line || '')?.[1];       // 스크립트: 끝난 단계 / 모두
      jobBox.append(h('div', { class: 'job', role: 'status', title: job.line || '' }, h('span', { class: 'spin' }), h('span', {}, job.label || job.op), step ? h('b', { class: 'step' }, step) : null, h('span', { class: 'who' }, 'Desk'), time,
        h('button', { class: 'btn', type: 'button', onclick: () => p.cancel() }, '취소')));
      const tick = () => { time.textContent = seconds((performance.now() - job.began) / 1000); };
      this.jobTimer = setInterval(tick, 100);
    } else if (job?.state === 'done') {
      jobBox.append(h('div', { class: 'job done', role: 'status' }, icon('check'), h('span', {}, job.label), h('span', { class: 'time' }, seconds(job.seconds)),
        job.record ? h('button', { class: 'link', type: 'button', onclick: () => p.openRecord(job.record) }, job.record) : null));
    } else if (job?.state === 'error') {
      jobBox.append(h('div', { class: 'job failed', role: 'status', title: job.error || '' }, icon('alert'), h('span', {}, `${job.label} — 실패`)));
    } else if (job?.state === 'cancelled') {
      jobBox.append(h('div', { class: 'job failed', role: 'status' }, icon('stop'), h('span', {}, `${job.label} — 취소함`)));
    }
    const strip = clear($('strip'));
    const now = Date.now();
    const recent = p.records.slice(-40).reverse();
    if (!recent.length) strip.append(h('span', { class: 'empty' }, '계산하면 기록이 여기에 뜹니다 — Desk 에서 하든 터미널에서 하든.'));
    for (const r of recent) {
      const chip = h('button', {
        class: `chip ${p.unseen.has(r.id) ? 'unseen' : ''} ${r.fresh ? 'fresh' : ''}`.trim().replace(/\s+/g, ' '), type: 'button',
        title: `${r.id}\n${cmdText(r.command)}\n${r.created || ''}`, onclick: () => p.openRecord(r.id),
      }, kindPill(r.kind), h('span', { class: 'name' }, String(r.id).split(':').slice(1).join(':')), r.metric ? h('span', { class: 'metric' }, r.metric) : null,
      h('span', { class: 'meta' }, whoLabel(r.who), ' · ', when(r.created, now)));
      delete r.fresh;
      strip.append(chip);
    }
    strip.scrollLeft = 0;
  },

  // ---- 바뀜 ------------------------------------------------------------------------------------

  countChange(p) {
    if (p.active === 'changes' && p === this.current) return;
    this.changes.set(p, (this.changes.get(p) || 0) + 1);
    this.renderChangesBadge();
  },

  clearChanges(p) {
    if (this.changes.delete(p)) this.renderChangesBadge();
  },

  renderChangesBadge() {
    const n = this.current ? this.changes.get(this.current) || 0 : 0;
    const btn = $('btn-changes');
    btn.querySelector('.badge')?.remove();
    if (n) btn.append(h('span', { class: 'badge' }, n > 9 ? '9+' : n));
    btn.disabled = !this.current;
  },

  // ---- 상태줄 ----------------------------------------------------------------------------------

  renderStatus() {
    const bar = clear($('status'));
    const p = this.current;
    const version = root.dataset.version;
    if (!p) { bar.append(h('span', { class: 'grow' }), h('span', { class: 'item' }, `Equion Desk ${version}`)); return; }
    const o = p.overview;
    bar.append(h('span', { class: 'item path', title: p.root }, icon('folder'), p.root));
    if (o?.vintage?.id) bar.append(h('button', { class: 'item', type: 'button', title: '지금 자료 회차 — 누르면 자료 작업대(원자료 · 시리즈 · 회차)', onclick: () => p.openTab({ type: 'data' }) }, '자료 ', h('b', {}, o.vintage.id)));
    if (o?.freq) bar.append(h('span', { class: 'item' }, { Q: '분기', M: '월', A: '연' }[o.freq] || o.freq));
    bar.append(h('span', { class: 'grow' }));
    if (p.error && !o) bar.append(h('span', { class: 'item bad' }, h('span', { class: 'dot bad' }), '작업 프로세스 없음'));
    else if (!o) bar.append(h('span', { class: 'item busy' }, h('span', { class: 'dot warn' }), '작업 프로세스를 띄우는 중…'));
    else {
      bar.append(h('span', { class: 'item', title: `${o.executable}\n작업 프로세스가 뜨는 데 ${p.worker?.started_seconds?.toFixed(1) ?? '?'}초` + (p.worker?.watch ? '' : '\n폴더 변경 알림을 쓰지 못해 2초마다 견줍니다') },
        h('span', { class: `dot ${p.error ? 'warn' : 'ok'}` }), p.error ? '정의 파일에 문제' : '작업 프로세스 준비됨'));
      bar.append(h('span', { class: 'item' }, `Desk ${version} · equion ${o.equion} · Python ${o.python}`));
    }
  },

  // ---- 도움말 ----------------------------------------------------------------------------------

  /** 도움말 — 프로젝트가 열려 있으면 가운데 탭으로, 아니면 상자로 */
  async openHelp() {
    if (this.current) { this.current.openTab({ type: 'help' }); return; }
    if (document.querySelector('.dialog.help')) return;
    const { helpText } = await import('./views/help.js');
    const { renderDoc } = await import('./md.js');
    const body = h('div', { class: 'dialog-body' });
    const close = () => { back.remove(); document.removeEventListener('keydown', onKey, true); };
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    const back = h('div', { class: 'backdrop' }, h('div', { class: 'dialog wide help', role: 'dialog', 'aria-modal': 'true', 'aria-label': '도움말' },
      h('div', { class: 'dialog-head' }, h('h2', {}, '도움말'), h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: close }, icon('x'))), body));
    back.addEventListener('pointerdown', (e) => { if (e.target === back) close(); });
    document.addEventListener('keydown', onKey, true);
    document.body.append(back);
    try { await renderDoc(body, await helpText(), { pid: '', dir: '', openFile: () => {} }); } catch (err) { body.textContent = err.message; }
  },

  // ---- 설정 상자 --------------------------------------------------------------------------------

  toggleSettings(anchor) {
    const old = document.querySelector('.popover');
    if (old) { old.remove(); return; }
    const s = this.settings;
    const seg = (key, options) => h('div', { class: 'segmented' }, options.map(([value, label, ic]) => h('button', {
      type: 'button', 'aria-pressed': String(s[key] === value), onclick: () => { this.setSetting(key, value); pop.remove(); this.toggleSettings(anchor); },
    }, ic ? icon(ic) : null, label)));
    const size = h('output', {}, `${s.font_scale}%`);
    const step = (d) => { const v = Math.min(140, Math.max(80, s.font_scale + d)); this.setSetting('font_scale', v); size.textContent = `${v}%`; };
    const pop = h('div', { class: 'popover', role: 'dialog', 'aria-label': '설정' },
      h('h4', {}, '바탕'), seg('theme', [['auto', '자동', 'auto'], ['light', '밝게', 'sun'], ['dark', '어둡게', 'moon']]),
      h('h4', {}, '터미널 색'), seg('term_follow', [[true, '바탕에 맞춤'], [false, '늘 어둡게']]),
      h('h4', {}, '글자 크기'), h('div', { class: 'stepper' },
        h('button', { class: 'btn small', type: 'button', 'aria-label': '작게', onclick: () => step(-5) }, icon('minus')), size,
        h('button', { class: 'btn small', type: 'button', 'aria-label': '크게', onclick: () => step(5) }, icon('plus')),
        h('button', { class: 'btn small quiet', type: 'button', onclick: () => step(100 - this.settings.font_scale) }, '기본')),
      h('h4', {}, 'Claude Code'), h('div', { class: 'pop-actions' },
        h('button', { class: 'btn small', type: 'button', 'data-act': 'teach-claude', disabled: !this.current, title: '이 프로젝트에 Equion 스킬을 넣는 명령을 터미널에 붙인다(Enter 는 직접) — 한 번만 하면 된다',
          onclick: () => { pop.remove(); this.current?.sendToTerminal('equion guide skill --install project'); } }, icon('spark'), 'Claude Code 에 Equion 알려 주기')),
      h('div', { class: 'pop-note' }, this.state?.claude ? '이 PC 에서 claude 명령을 찾았습니다 — 터미널에서 claude 로 띄웁니다.' : '이 PC 에서 claude 명령을 찾지 못했습니다. 없어도 화면의 모든 기능은 그대로입니다.'),
      h('div', { class: 'about' }, `Equion Desk ${root.dataset.version}`, h('br'), '설정과 지난 화면은 사용자 폴더에 적습니다 — 프로젝트 폴더는 건드리지 않습니다.', h('br'),
        h('button', { class: 'link', type: 'button', onclick: () => { pop.remove(); this.openHelp(); } }, '도움말 (F1)')));
    document.body.append(pop);
    const r = anchor.getBoundingClientRect();
    pop.style.top = `${r.bottom + 6}px`;
    pop.style.left = `${Math.max(8, r.right - pop.offsetWidth)}px`;
    const away = (e) => { if (!pop.contains(e.target) && !anchor.contains(e.target)) { pop.remove(); document.removeEventListener('pointerdown', away, true); } };
    document.addEventListener('pointerdown', away, true);
  },
};

function onEvent(e) {
  if (e.type === 'tabs') { getJSON('/api/state').then((state) => app.syncTabs(state)).catch(() => {}); return; }
  if (e.type === 'notice') { app.say(e.text, e.level || 'info'); return; }
  app.projects.get(e.p)?.onEvent(e);
}

async function main() {
  await ready();
  const logo = document.querySelector('.brand .mark');
  if (logo) logo.innerHTML = LOGO;
  for (const [id, name] of [['btn-new', 'plus'], ['btn-changes', 'history'], ['btn-side', 'sidebar'], ['btn-term', 'terminal'], ['btn-help', 'info'], ['btn-settings', 'gear']]) $(id).prepend(icon(name));

  const state = await getJSON('/api/state');
  app.settings = { ...app.settings, ...state.client };
  app.applySettings();
  dark.addEventListener('change', () => app.applySettings());

  $('btn-new').addEventListener('click', () => (state.can_pick ? app.openProject('/api/open') : app.select(null)));
  $('btn-side').addEventListener('click', () => app.setSetting('side_visible', !app.settings.side_visible));
  $('btn-term').addEventListener('click', () => app.setSetting('term_visible', !app.settings.term_visible));
  $('btn-settings').addEventListener('click', (e) => app.toggleSettings(e.currentTarget));
  $('btn-help').addEventListener('click', () => app.openHelp());
  $('btn-changes').addEventListener('click', () => app.current?.openTab({ type: 'changes' }));
  $('btn-records').addEventListener('click', () => app.current?.openTab({ type: 'records' }));
  $('strip').addEventListener('wheel', (e) => { if (e.deltaY) { $('strip').scrollLeft += e.deltaY; e.preventDefault(); } }, { passive: false });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.querySelector('.popover')?.remove();
    if (e.key === 'F1') { e.preventDefault(); app.openHelp(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'w' && app.current && !app.current.termBox.contains(document.activeElement)) {
      e.preventDefault();
      app.current.closeTab(app.current.active);
    }
    if ((e.ctrlKey || e.metaKey) && e.key === '`') { e.preventDefault(); app.setSetting('term_visible', !app.settings.term_visible); }
  });
  window.addEventListener('pagehide', () => { for (const p of app.projects.values()) p.persist(true); });

  app.syncTabs(state);
  listen(state.seq, onEvent, () => { for (const p of app.projects.values()) p.resync(); });
  setInterval(() => { if (app.current && !document.hidden) app.renderActivity(); }, 60000);      // '3분 전' 같은 때 표기를 새로

  // ?est=demand:CN — 열자마자 그 부품의 식 작업대를 열고 추정한다(화면 점검·시간 재기)
  const want = new URLSearchParams(location.search).get('est');
  if (want && app.current) {
    const wait = setInterval(() => {
      if (!app.current.overview && !app.current.error) return;
      clearInterval(wait);
      const part = app.current.part(want);
      const view = app.current.openTab(part ? { type: 'bench', part: want } : { type: 'bench', draft: want });
      setTimeout(() => view.estimate(), 50);
    }, 60);
  }
  window.equionDesk = app;      // 개발자 도구·화면 점검용
}

main().catch((err) => {
  console.error(err);
  document.body.append(h('div', { style: { position: 'fixed', inset: '0', display: 'grid', 'place-items': 'center', padding: '40px', background: 'var(--paper)', 'white-space': 'pre-wrap' } },
    `Equion Desk 화면을 띄우지 못했습니다.\n\n${err.message}`));
});
