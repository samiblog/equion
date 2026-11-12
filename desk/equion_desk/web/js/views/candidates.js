// 후보 목록 — 한 부품에 묶인 추정 기록들. 사람이 했든 Claude 가 했든 같은 목록에 쌓이고, 걸러진 것도 까닭과 함께 남는다(기획안 §2.4-5).
//
// - 줄을 누르면 그 기록이 아래에 보인다(다시 계산하지 않는다). 네모 칸은 겹쳐 볼 것을 고른다(넷까지).
// - 지금 보는 기록과 종속변수·표본이 다른 줄은 견줄 수 없는 칸(R²·SE, AIC·BIC)을 흐리게 하고 까닭을 알린다.
// - 같이 견줄 수 있는 줄 가운데 가장 좋은 값은 굵게.
// - 같은 식·표본·표준오차·자료로 여러 번 추정한 것은 한 줄로 모은다(×3) — 같은 계산이 목록을 메우지 않게. 기록은 모두 남아 있다.
// - 자리가 좁으면 덜 중요한 열부터 감춘다(bench.css 의 @container).

import { clear, cmdText, h, icon, put, when, WHO } from '../util.js';

export const MAX_OVERLAY = 4;

// 앞의 0만 떼어 짧게(.9871) — 반올림한 글자를 보고 뗀다: 0.99996 은 '1.0000'(값을 보고 떼면 '.0000'이 된다)
const noLead0 = (s) => (s.startsWith('0.') ? s.slice(1) : s);
export const r4 = (v) => (v == null ? '—' : noLead0(v.toFixed(4)));
const sig = (v) => (v == null ? '—' : Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 100 ? v.toFixed(1) : Math.abs(v) >= 1 ? v.toFixed(3) : v.toPrecision(3));
const d1 = (v) => (v == null ? '—' : v.toFixed(1));
const d2 = (v) => (v == null ? '—' : v.toFixed(2));
export const p3 = (v) => (v == null ? '—' : v < 0.001 ? '<.001' : noLead0(v.toFixed(3)));
const pct = (v) => (v == null ? '—' : `${v.toFixed(2)}%`);

// better: 클수록·작을수록 좋은 칸. needs: 무엇이 같아야 견줄 수 있나(dep 종속변수 · sample 종속변수와 표본)
const COLS = [
  { key: 'adj', label: 'R²adj', get: (r) => r.stats.adj_r_squared, fmt: r4, better: 'max', needs: 'dep', title: '조정 R²' },
  { key: 'se', label: 'SE', get: (r) => r.stats.se_regression, fmt: sig, better: 'min', needs: 'dep', title: '회귀 표준오차' },
  { key: 'dw', label: 'DW', get: (r) => r.stats.durbin_watson, fmt: d2, cls: 'p2', title: 'Durbin-Watson' },
  { key: 'aic', label: 'AIC', get: (r) => r.stats.aic, fmt: d1, better: 'min', needs: 'sample', cls: 'p2' },
  { key: 'bic', label: 'BIC', get: (r) => r.stats.bic, fmt: d1, better: 'min', needs: 'sample', cls: 'p4' },
  { key: 'lm', label: 'LM p', get: (r) => r.diag.lm, fmt: p3, test: true, cls: 'p3', title: '계열상관 LM 검정의 p값' },
  { key: 'white', label: 'White p', get: (r) => r.diag.white, fmt: p3, test: true, cls: 'p4', title: '이분산 White 검정의 p값' },
  { key: 'sim', label: '단독 모의', get: (r) => r.sim, fmt: pct, better: 'min', cls: 'p3', title: '식 하나의 동태 모의 RMSPE(다른 변수는 실측) — 추정할 때 ‘단독 모의’를 켠 기록만' },
];

const sameSample = (a, b) => a.sample?.[0] === b.sample?.[0] && a.sample?.[1] === b.sample?.[1];

/** 지금 보는 기록(ref)과 견줄 수 있는지 — 까닭 글 또는 null */
export function incomparable(row, ref, needs) {
  if (!ref || !needs || row.id === ref.id) return null;
  if (row.dependent !== ref.dependent) return `종속변수가 달라(${row.dependent} · ${ref.dependent}) 견줄 수 없습니다 — 단독 모의 RMSPE로 보세요`;
  if (needs === 'sample' && !sameSample(row, ref)) return `표본이 달라(${row.sample?.join('~')} · ${ref.sample?.join('~')}) 그대로 견주기 어렵습니다`;
  return null;
}

/**
 * 같은 계산(식·표본·표준오차·자료·추정법)을 한 줄로 모은다. 대표는 지금 보는 기록 > 채택한 기록 > 단독 모의가 있는 것 > 가장 새것.
 * 돌려주는 줄에는 members(모인 기록 이름들, 새것부터)·starred(채택한 기록이 들어 있는지)가 붙는다.
 */
export function groupRows(rows, selected, adopted) {
  const groups = new Map();
  for (const r of rows) {
    const key = [r.text, (r.sample || []).join('~'), r.cov || '', r.data || '', r.method || ''].join('\u0001');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  const out = [];
  for (const list of groups.values()) {
    const newest = [...list].reverse();
    const rep = newest.find((r) => r.id === selected) || newest.find((r) => r.id === adopted) || newest.find((r) => r.sim != null) || newest[0];
    out.push({ ...rep, members: newest.map((r) => r.id), starred: list.some((r) => r.id === adopted), latest: newest[0].created });
  }
  return out;
}

export function sortRows(rows, sort) {
  const col = COLS.find((c) => c.key === sort.key);
  const get = col ? col.get : sort.key === 'name' ? (r) => r.name : sort.key === 'pass' ? (r) => (r.pass == null ? 0.5 : r.pass ? 1 : 0) : (r) => r.latest || r.created;
  return [...rows].sort((a, b) => {
    const x = get(a), y = get(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;            // 값이 없는 줄은 늘 아래로
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * sort.dir || ((a.latest || a.created) < (b.latest || b.created) ? 1 : -1);
  });
}

/**
 * 후보 목록. on: {select(id), toggle(id), overlay(), sort(key), filter(bool), load(id)}.
 * update({rows, adopted, selected, checked, sort, onlyPass, fresh, mode, tall}) 로 다시 그린다. move(±1) 은 고른 줄을 위아래로 옮긴다.
 */
export function candidateRail(on) {
  const summary = h('div', { class: 'cand-sum' });
  const tools = h('div', { class: 'cand-tools' });
  const table = h('table', { class: 'cand' });
  const scroll = h('div', { class: 'cand-scroll', tabindex: '0', role: 'listbox', 'aria-label': '후보 목록' }, table);
  const el = h('section', { class: 'cands', 'aria-label': '후보' }, h('div', { class: 'cand-head' }, summary, tools), scroll);
  let shown = [];
  let state = null;

  scroll.addEventListener('keydown', (e) => {
    if (!state || !shown.length) return;
    const i = shown.findIndex((r) => r.id === state.selected);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      move(e.key === 'ArrowDown' ? 1 : -1);
    } else if (e.key === ' ' && i >= 0) { e.preventDefault(); on.toggle(shown[i].id); } else if (e.key === 'Enter' && i >= 0) { e.preventDefault(); on.load(shown[i].id); }
  });

  function move(delta) {
    if (!state || !shown.length) return;
    const i = shown.findIndex((r) => r.id === state.selected);
    const next = shown[Math.max(0, Math.min(shown.length - 1, (i < 0 ? 0 : i + delta)))];
    if (next && next.id !== state.selected) on.select(next.id);
  }

  function update(next) {
    state = next;
    const { adopted, selected, checked, sort, onlyPass, fresh, mode } = state;
    const rows = groupRows(state.rows, selected, adopted);
    scroll.classList.toggle('tall', !!state.tall);
    const passed = rows.filter((r) => r.pass === true).length;
    const failed = rows.filter((r) => r.pass === false).length;
    put(clear(summary), h('b', {}, '후보'), h('span', { class: 'n', title: rows.length === state.rows.length ? '' : `추정 기록 ${state.rows.length}개 — 같은 계산은 한 줄로 모았습니다` }, rows.length),
      passed ? h('span', { class: 'tag ok' }, `통과 ${passed}`) : null, failed ? h('span', { class: 'tag warn' }, `걸러짐 ${failed}`) : null);
    clear(tools);
    if (passed && failed) {
      tools.append(h('button', { class: 'btn small quiet', type: 'button', 'aria-pressed': String(onlyPass), title: '판단 기준을 통과한 후보만 보인다(걸러진 것은 지워지지 않는다)',
        onclick: () => on.filter(!onlyPass) }, onlyPass ? icon('check') : null, '통과만'));
    }
    const n = checked.size;
    tools.append(h('button', {
      class: `btn small ${mode === 'overlay' ? 'primary' : ''}`.trim(), type: 'button', disabled: n < 2 && mode !== 'overlay',
      title: n < 2 ? '네모 칸으로 둘에서 넷까지 고르면 겹쳐 봅니다' : '고른 후보의 적합·잔차·계수를 나란히', onclick: () => on.overlay(),
    }, icon('layers'), mode === 'overlay' ? '겹쳐 보기 닫기' : n >= 2 ? `겹쳐 보기 ${n}` : '겹쳐 보기'));

    if (rows.length > 4) {
      tools.append(h('button', { class: 'icon-btn', type: 'button', title: state.tall ? '목록을 낮게' : '목록을 높게', 'aria-label': '목록 높이', 'aria-pressed': String(!!state.tall), onclick: () => on.tall(!state.tall) }, icon('list')));
    }
    shown = sortRows(onlyPass ? rows.filter((r) => r.pass !== false || r.id === selected || r.starred) : rows, sort);
    const ref = rows.find((r) => r.id === selected) || null;
    // 가장 좋은 값 — 지금 보는 기록과 견줄 수 있는 줄 가운데서만
    const best = {};
    for (const col of COLS.filter((c) => c.better)) {
      const pool = shown.filter((r) => col.get(r) != null && !incomparable(r, ref, col.needs));
      if (pool.length < 2) continue;
      const values = pool.map(col.get);
      const top = col.better === 'max' ? Math.max(...values) : Math.min(...values);
      if (values.filter((v) => v === top).length < values.length) best[col.key] = top;      // 모두 같으면 가릴 것이 없다
    }
    const arrow = (key) => (sort.key === key ? h('span', { class: 'arrow' }, sort.dir > 0 ? '↑' : '↓') : null);
    const head = (key, label, cls = '', title = '') => h('th', { class: `${cls} ${sort.key === key ? 'sorted' : ''}`.trim(), title: title || `${label} 순으로`, onclick: () => on.sort(key) }, label, arrow(key));
    clear(table).append(h('thead', {}, h('tr', {},
      h('th', { class: 'c-check', title: '겹쳐 볼 것 고르기(넷까지)' }, ''), head('name', '기록', 'c-name'), h('th', { class: 'c-eq' }, '식'),
      COLS.map((c) => head(c.key, c.label, `num ${c.cls || ''}`, c.title)), head('pass', '기준', 'c-pass'), head('created', '때', 'c-when p4'))));
    const body = h('tbody', {});
    for (const r of shown) {
      const alpha = r.alpha ?? 0.05;
      const mine = r.members.find((id) => checked.has(id));      // 모인 기록 가운데 고른 것
      const on_ = !!mine;
      const full = !on_ && checked.size >= MAX_OVERLAY;
      const tr = h('tr', {
        class: `${r.id === selected ? 'on' : ''} ${r.pass === false ? 'out' : ''} ${r.members.some((id) => fresh.has(id)) ? 'fresh' : ''}`.trim().replace(/\s+/g, ' '), role: 'option', 'aria-selected': String(r.id === selected),
        'data-id': r.id, title: `${cmdText(r.command)}\n두 번 누르면 이 식을 식 칸으로 가져옵니다`,
        onclick: () => on.select(r.id), ondblclick: () => on.load(r.id),
      },
      h('td', { class: 'c-check' }, h('button', {
        class: 'check', type: 'button', role: 'checkbox', 'aria-checked': String(on_), disabled: full, 'aria-label': `${r.name} 겹쳐 보기에 넣기`,
        title: full ? `겹쳐 보기는 ${MAX_OVERLAY}개까지입니다` : '겹쳐 볼 것으로 고르기', onclick: (e) => { e.stopPropagation(); on.toggle(mine || r.id); },
      }, on_ ? icon('check') : null)),
      h('td', { class: 'c-name' }, r.starred ? h('span', { class: 'star', title: `채택한 기록${r.id === adopted ? '' : `(${adopted.split(':')[1]} — 같은 계산)`} — 모형은 이 계수로 푼다` }, '★') : null, h('span', { class: 'mono' }, r.name),
        r.members.length > 1 ? h('span', { class: 'times', title: `같은 식·표본·표준오차·자료로 ${r.members.length}번 추정했습니다:\n${r.members.map((id) => id.split(':')[1]).join(' · ')}` }, `×${r.members.length}`) : null,
        h('span', { class: `who ${r.who === 'claude' ? 'claude' : ''}`.trim() }, WHO[r.who] || r.who || '')),
      h('td', { class: 'c-eq mono' }, r.text || '', r.cov ? h('span', { class: 'mini', title: `계수 공분산: ${r.cov_label || r.cov}` }, r.cov.toUpperCase()) : null));
      for (const c of COLS) {
        const v = c.get(r);
        const why = incomparable(r, ref, c.needs);
        const cls = ['num', c.cls || ''];
        let title = '';
        if (why && v != null) { cls.push('nc'); title = why; } else if (c.test && v != null && v < alpha) { cls.push('alert'); title = `p < ${alpha} — 문제 없음 가설을 기각합니다`; } else if (best[c.key] != null && v === best[c.key]) { cls.push('best'); title = '견줄 수 있는 후보 가운데 가장 좋은 값'; }
        tr.append(h('td', { class: cls.join(' ').trim(), title }, c.fmt(v), why && v != null ? h('sup', {}, '≠') : null));
      }
      tr.append(h('td', { class: 'c-pass', title: (r.reasons || []).join('\n') },
        r.pass == null ? h('span', { class: 'muted' }, '—') : r.pass ? h('span', { class: 'tag ok' }, '통과') : h('span', { class: 'tag warn' }, (r.reasons || [])[0] || '걸러짐',
          r.reasons?.length > 1 ? ` +${r.reasons.length - 1}` : '')),
      h('td', { class: 'c-when p4' }, when(r.latest || r.created)));
      body.append(tr);
    }
    table.append(body);
    if (!shown.length) table.append(h('tbody', {}, h('tr', { class: 'none' }, h('td', { colspan: String(COLS.length + 5) }, rows.length ? '통과한 후보가 없습니다.' : '아직 후보가 없습니다 — 추정하면 여기에 쌓입니다. 터미널에서 친 것도 함께.'))));
    // 고른 줄이 목록 안에서 보이게 — 목록만 민다(화면 전체를 끌어오지 않는다. 아래 차트를 보는 중에 새 기록이 와도 화면이 튀지 않게)
    const row = table.querySelector('tbody tr.on');
    if (row) {
      const headH = table.tHead?.offsetHeight || 0;
      const top = row.offsetTop - headH;
      const bottom = row.offsetTop + row.offsetHeight;
      if (top < scroll.scrollTop) scroll.scrollTop = top;
      else if (bottom > scroll.scrollTop + scroll.clientHeight) scroll.scrollTop = bottom - scroll.clientHeight;
    }
  }

  return { el, update, move, focus: () => scroll.focus() };
}
