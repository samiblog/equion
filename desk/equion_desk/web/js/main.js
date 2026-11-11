// Equion Desk 시험판(D0) — 식 작업대 한 화면: 부품을 고르거나 식을 쓰고 추정 → 계수표·진단·차트. 걸린 시간을 함께 보인다(S1: 1초 안).

import { getJSON, postJSON, ready } from './api.js';
import { drawFit } from './chart.js';
import { startTerminal } from './terminal.js';

const $ = (sel) => /** @type {HTMLElement} */ (document.querySelector(sel));
const STATS = [['r_squared', 'R²'], ['adj_r_squared', '조정 R²'], ['se_regression', '회귀 표준오차'], ['durbin_watson', 'Durbin-Watson'],
  ['log_likelihood', '로그우도'], ['aic', 'AIC'], ['bic', 'BIC']];

function num(v, digits = 4) {
  if (v == null || Number.isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-4 || a >= 1e7)) return v.toExponential(3);
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function row(cells) {
  const tr = document.createElement('tr');
  cells.forEach((c, i) => {
    const td = document.createElement('td');
    if (i) td.className = 'num';
    if (c && typeof c === 'object') { td.textContent = c.text; if (c.cls) td.classList.add(c.cls); } else td.textContent = c;
    tr.append(td);
  });
  return tr;
}

function fill(tbody, rows) {
  tbody.textContent = '';
  for (const r of rows) tbody.append(row(r));
}

function setWorker(text, cls = '') {
  const chip = $('#worker');
  chip.textContent = text;
  chip.className = `chip ${cls}`.trim();
}

function message(text, error = false) {
  const box = $('#message');
  box.textContent = text || '';
  box.classList.toggle('error', error);
}

function show(rec, timing) {
  $('#result').hidden = false;
  const head = $('#headline');
  head.textContent = '';
  const id = document.createElement('span');
  id.className = 'id';
  id.textContent = rec.id;
  head.append(id, ` · ${rec.dependent} · ${String(rec.method || '').toUpperCase()} · ${rec.sample?.[0]}~${rec.sample?.[1]} · 관측 ${rec.n}`);
  fill($('#coefs tbody'), (rec.coefs || []).map((c) => [c.name, num(c.coef, 6), num(c.se, 6), num(c.t, 3),
    { text: num(c.p, 4), cls: c.p > 0.05 ? 'weak' : '' }]));
  fill($('#stats tbody'), STATS.filter(([k]) => rec.stats?.[k] != null).map(([k, label]) => [label, num(rec.stats[k], 4)]));
  fill($('#diag tbody'), Object.values(rec.diagnostics || {}).map((d) => [d.name, num(d.stat, 3), { text: num(d.p, 4), cls: d.p < 0.05 ? 'weak' : '' }]));
  const crit = $('#criteria');
  crit.textContent = '';
  if (rec.criteria) {
    const mark = document.createElement('span');
    mark.className = rec.criteria.pass ? 'pass' : 'fail';
    mark.textContent = rec.criteria.pass ? '통과' : '걸림';
    crit.append(mark, rec.criteria.pass ? '' : ` — ${(rec.criteria.reasons || []).join(', ')}`);
  } else crit.textContent = '정한 기준이 없습니다';
  const implicit = $('#implicit');
  implicit.textContent = '';
  for (const line of rec.implicit?.length ? rec.implicit : ['없음']) {
    const li = document.createElement('li');
    li.textContent = line;
    implicit.append(li);
  }
  const began = performance.now();
  drawFit($('#chart'), rec.series);
  requestAnimationFrame(() => {
    const total = performance.now() - timing.clicked;
    $('#timing').textContent = `누른 뒤 화면까지 ${(total / 1000).toFixed(3)}초 · 계산 ${timing.seconds.toFixed(3)}초 · 차트 ${(performance.now() - began).toFixed(0)}ms`;
  });
}

let busy = false;

async function work(label, fn) {
  if (busy) return;
  busy = true;
  setWorker(`${label} 중…`, 'busy');
  $('#btn-cancel').hidden = false;
  /** @type {HTMLButtonElement} */ ($('#btn-est')).disabled = true;
  try {
    await fn();
    setWorker('작업 프로세스 준비됨', 'ok');
  } catch (err) {
    message(err.message + (err.detail ? `\n\n${err.detail}` : ''), true);
    setWorker(err.kind === 'cancelled' ? '취소함 — 다음 계산 때 다시 뜹니다' : err.kind === 'gone' ? '작업 프로세스가 끝남' : '작업 프로세스 준비됨',
      err.kind === 'input' ? 'ok' : 'bad');
  } finally {
    busy = false;
    $('#btn-cancel').hidden = true;
    /** @type {HTMLButtonElement} */ ($('#btn-est')).disabled = false;
  }
}

function estimate() {
  const target = /** @type {HTMLTextAreaElement} */ ($('#eq')).value.trim();
  if (!target) return;
  const clicked = performance.now();
  message('');
  work('추정', async () => {
    const res = await postJSON('/api/est', { target });
    show(res.result, { clicked, seconds: res.seconds });
    if (res.said.trim()) message(res.said.trim());
  });
}

function model(path, body, label) {
  const clicked = performance.now();
  work(label, async () => {
    const res = await postJSON(path, body);
    const r = res.result;
    $('#model-out').textContent = `${r.id}\n${(res.said || '').trim()}\n${((performance.now() - clicked) / 1000).toFixed(3)}초`;
  });
}

async function openWith(path) {
  message('');
  try {
    const res = await postJSON(path);
    if (res.root) location.reload();
  } catch (err) {
    message(err.message, true);
  }
}

async function loadProject() {
  const state = await getJSON('/api/state');
  if (!state.root) {
    $('#welcome').hidden = false;
    $('#est-form').hidden = true;
    $('#project').textContent = '연 프로젝트가 없습니다';
    /** @type {HTMLButtonElement} */ ($('#btn-open')).disabled = !state.can_pick;
    setWorker('작업 프로세스 —');
    return;
  }
  setWorker('작업 프로세스를 띄우는 중…', 'busy');
  let p;
  try {
    p = await getJSON('/api/project');
  } catch (err) {
    $('#project').textContent = '프로젝트를 열지 못했습니다';
    message(err.message, true);
    setWorker('작업 프로세스 없음', 'bad');
    return;
  }
  $('#project').textContent = p.info.project;
  $('#project').title = p.info.root;
  $('#versions').textContent = `Desk ${document.documentElement.dataset.version} · equion ${p.info.equion} · Python ${p.info.python}`;
  $('#versions').title = p.info.executable;
  setWorker(`작업 프로세스 준비됨 (${p.started_seconds.toFixed(1)}초에 뜸)`, 'ok');
  const list = $('#parts');
  list.textContent = '';
  for (const part of p.parts) {
    const li = document.createElement('li');
    li.title = `${part.text}\n${part.where}`;
    const kind = document.createElement('span');
    kind.className = 'kind';
    kind.textContent = part.kind === 'identity' ? '항등식' : '추정식';
    li.append(part.id, kind);
    if (part.kind !== 'identity') {
      li.addEventListener('click', () => {
        list.querySelectorAll('.on').forEach((n) => n.classList.remove('on'));
        li.classList.add('on');
        /** @type {HTMLTextAreaElement} */ ($('#eq')).value = part.id;
        estimate();
      });
    } else li.style.cursor = 'default';
    list.append(li);
  }
}

function splitter() {
  const bar = $('#split');
  bar.addEventListener('pointerdown', (down) => {
    bar.setPointerCapture(down.pointerId);
    const move = (e) => {
      const w = Math.min(Math.max(window.innerWidth - e.clientX, 260), window.innerWidth - 640);
      document.documentElement.style.setProperty('--term-w', `${w}px`);
    };
    bar.addEventListener('pointermove', move);
    bar.addEventListener('pointerup', () => bar.removeEventListener('pointermove', move), { once: true });
  });
}

async function main() {
  await ready();
  $('#est-form').addEventListener('submit', (e) => { e.preventDefault(); estimate(); });
  $('#eq').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); estimate(); } });
  $('#btn-cancel').addEventListener('click', () => postJSON('/api/cancel').catch(() => {}));
  $('#btn-hs').addEventListener('click', () => model('/api/hs', {}, '과거 재현'));
  $('#btn-sim').addEventListener('click', () => model('/api/sim', { scenario: 'base' }, '전망'));
  $('#btn-open').addEventListener('click', () => openWith('/api/open'));
  $('#btn-example').addEventListener('click', () => openWith('/api/example'));
  splitter();
  startTerminal().catch((err) => console.error(err));
  await loadProject();
  // ?est=demand:CN — 열자마자 그 부품(또는 식)을 추정한다. 화면 점검과, 나중의 'Desk에서 이 기록 보기'(equion desk show)가 쓴다
  const want = new URLSearchParams(location.search).get('est');
  if (want) { /** @type {HTMLTextAreaElement} */ ($('#eq')).value = want; estimate(); }
}

main();
