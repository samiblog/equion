// 같은 분석의 두 기록 비교 (2차판 — DESK_SOLO 장면 4, D58) — 이번 달과 지난달처럼 같은 분석·같은 대상의 기록 둘을 나란히.
// 위에는 한 줄 결과(카드의 요약 줄)를 줄마다 견주어 바뀐 줄을, 판단(→ 뒤)이 바뀐 줄은 따로 강조한다. 아래에는 두 카드를 나란히.
// 무엇이 달랐는지(자료 회차 · 표본 · 옵션)도 보인다 — 숫자가 바뀐 까닭을 짐작할 수 있게.

import { renderDoc } from '../md.js';
import { clear, h, icon, when } from '../util.js';

const judge = (line) => (String(line).split('→')[1] || '').trim();
const key = (line) => String(line).trim().split(/\s{2,}|\s/)[0] || '';

export function ancompareView(project, desc) {
  let a = desc.a;
  const b = desc.b;
  const el = h('div', { class: 'view an-compare' });
  const st = { recs: {}, hist: null, error: null };
  let loaded = false;

  async function load() {
    loaded = true;
    try {
      const [ra, rb, hist] = await Promise.all([project.get(`record?id=${encodeURIComponent(a)}`), project.get(`record?id=${encodeURIComponent(b)}`),
        project.get(`an-history?id=${encodeURIComponent(b)}`)]);
      st.recs = { [a]: ra, [b]: rb };
      st.hist = hist;
      st.error = null;
    } catch (err) { st.error = err.message; }
    render();
  }

  /** 두 기록의 한 줄 결과를 줄마다 — 앞 낱말(시리즈 이름 등)이 같은 줄끼리 짝짓는다 */
  function pairs(la, lb) {
    const rows = [];
    const used = new Set();
    for (const x of la) {
      const j = lb.findIndex((y, k) => !used.has(k) && key(y) === key(x));
      if (j >= 0) { used.add(j); rows.push([x, lb[j]]); } else rows.push([x, null]);
    }
    lb.forEach((y, k) => { if (!used.has(k)) rows.push([null, y]); });
    return rows;
  }

  function metaLine(rec, id) {
    const m = rec.meta || {};
    return h('div', { class: 'cmp-meta' }, h('button', { class: 'rid', type: 'button', title: '카드를 따로 연다', onclick: () => project.openRecord(id) }, id),
      h('span', {}, when(m.created)), m.data?.id ? h('span', { class: 'mono' }, m.data.id) : null, m.sample ? h('span', {}, `${m.sample[0]}–${m.sample[1]}`) : null,
      Object.entries(m.options || {}).some(([, v]) => v != null) ? h('span', { class: 'mono' }, Object.entries(m.options).filter(([, v]) => v != null).map(([k, v]) => `${k}=${v}`).join(' ')) : null);
  }

  async function render() {
    clear(el);
    const ra = st.recs[a];
    const rb = st.recs[b];
    const hist = st.hist;
    const others = (hist?.records || []).filter((r) => r.id !== b);
    const pick = h('select', { class: 'mini-select', 'aria-label': '견줄 기록' }, others.map((r) => h('option', { value: r.id }, `${r.id} · ${r.vintage || ''} · ${when(r.created)}`)));
    pick.value = a;
    pick.addEventListener('change', () => { a = pick.value; project.saveView(); load(); });
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, `${hist?.label || '분석'} — 두 기록`), h('div', { class: 'sub' }, h('span', { class: 'mono' }, hist?.target_label || hist?.target || ''),
        h('span', {}, `같은 분석·같은 대상의 기록 ${hist?.records?.length || 0}개`))),
      h('div', { class: 'tools' }, others.length > 1 ? h('label', { class: 'opt' }, h('span', {}, '견줄 기록'), pick) : null)));
    if (st.error) { el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error))); return; }
    if (!ra || !rb) { el.append(h('div', { class: 'empty-state' }, '읽는 중…')); return; }
    const ma = ra.meta || {};
    const mb = rb.meta || {};
    const why = [];
    if ((ma.data || {}).id !== (mb.data || {}).id) why.push(`자료 회차 ${(ma.data || {}).id || '-'} → ${(mb.data || {}).id || '-'}`);
    if ((ma.sample || []).join('~') !== (mb.sample || []).join('~')) why.push(`표본 ${(ma.sample || []).join('–')} → ${(mb.sample || []).join('–')}`);
    if (JSON.stringify(ma.options || {}) !== JSON.stringify(mb.options || {})) why.push('옵션이 다름');
    const rows = pairs(ma.lines || [], mb.lines || []);
    const changed = rows.filter(([x, y]) => x !== y).length;
    const flipped = rows.filter(([x, y]) => x && y && judge(x) && judge(y) && judge(x) !== judge(y)).length;
    el.append(h('div', { class: `banner ${flipped ? 'warn' : 'info'}` }, icon(flipped ? 'alert' : 'info'),
      h('div', {}, flipped ? h('b', {}, `판단이 바뀐 줄 ${flipped}개`) : '판단이 바뀐 줄은 없습니다', ` · 숫자가 바뀐 줄 ${changed}개`, why.length ? ` — ${why.join(' · ')}` : '')));
    el.append(h('table', { class: 'grid plain cmp-lines' },
      h('thead', {}, h('tr', {}, h('th', {}, h('span', { class: 'muted' }, '앞 '), a), h('th', {}, h('span', { class: 'muted' }, '뒤 '), b))),
      h('tbody', {}, rows.map(([x, y]) => {
        const flip = x && y && judge(x) && judge(y) && judge(x) !== judge(y);
        return h('tr', { class: `${x !== y ? 'changed' : ''} ${flip ? 'flipped' : ''}`.trim() },
          h('td', { class: 'mono' }, x ?? '—'), h('td', { class: 'mono' }, y ?? '—', flip ? h('span', { class: 'tag warn' }, '판단이 바뀜') : null));
      }))));
    const docA = h('div', { class: 'of-record' });
    const docB = h('div', { class: 'of-record' });
    el.append(h('div', { class: 'cmp-cols' }, h('div', {}, metaLine(ra, a), docA), h('div', {}, metaLine(rb, b), docB)));
    const ctx = (rec) => ({ pid: project.id, dir: rec.path, openFile: (path) => project.openTab({ type: 'file', path }) });
    await Promise.all([ra.summary ? renderDoc(docA, ra.summary, ctx(ra)) : null, rb.summary ? renderDoc(docB, rb.summary, ctx(rb)) : null]);
  }

  render();
  return {
    key: `ancompare:${b}`, type: 'ancompare', title: `${b.split(':')[1]} 견주기`, icon: 'diff', mono: true, el,
    desc: () => ({ type: 'ancompare', a, b }),
    show() { if (!loaded) load(); },
    open(next) { if (next.a && next.a !== a) { a = next.a; if (loaded) load(); } },
    event() {},
    dispose() {},
  };
}
