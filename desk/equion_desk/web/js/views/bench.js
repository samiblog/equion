// 식 작업대 — 부품(예: demand:CN)의 식을 보고, 고쳐 보고, 추정한다. 결과는 계수표·적합·진단·판단 기준·알아서 한 것·차트.
//
// - 화면을 여는 것만으로는 계산하지 않는다(기획안 §2.4-1). 그 부품의 가장 최근 추정 기록이 있으면 그것을 보이고, 추정은 단추나 Ctrl+Enter.
// - 식을 그대로 두고 추정하면 부품의 추정(`est demand:CN`), 고쳐서 추정하면 그 식 글자의 추정(같은 목표의 후보로 기록된다).
// - 쓰던 식(초안)과 보던 기록은 탭과 함께 기억한다 — 닫았다 열면 이어진다.
// D1 의 화면이다. 후보 목록·겹쳐 보기·채택은 D2a 에서 넣는다.

import { drawFit } from '../chart.js';
import { clear, copyText, h, icon, num, pval, seconds, when, whoLabel } from '../util.js';

const STATS = [['adj_r_squared', '조정 R²', 4], ['r_squared', 'R²', 4], ['se_regression', '회귀 표준오차', 4], ['durbin_watson', 'DW', 3],
  ['aic', 'AIC', 1], ['bic', 'BIC', 1], ['log_likelihood', '로그우도', 1]];

function fact(label, value, cls = '') {
  return h('div', { class: `fact ${cls}`.trim() }, h('div', { class: 'k' }, label), h('div', { class: 'v' }, value));
}

export function benchView(project, desc) {
  const partId = desc.part || null;
  const key = partId ? `bench:${partId}` : `bench:~${desc.free}`;
  const el = h('div', { class: 'view' });
  let shown = desc.shown || null;        // 보이는 기록 id
  let record = null;                     // 그 기록의 내용
  let timing = null;
  let said = '';
  let problem = null;
  let disposeChart = () => {};
  let loaded = false;

  const part = () => (partId ? project.part(partId) : null);
  const area = h('textarea', { rows: 1, spellcheck: 'false', autocomplete: 'off', placeholder: '식을 씁니다 — 예: CN c Y CN(-1)', 'aria-label': '식' });
  let touched = desc.draft != null;      // 사람이 식 칸을 고쳤는지 — 고치지 않았으면 부품의 식을 따라간다
  area.value = desc.draft ?? part()?.text ?? '';
  const grow = () => { area.style.height = 'auto'; area.style.height = `${Math.max(46, area.scrollHeight)}px`; };
  const head = h('div', { class: 'view-head' });
  const form = h('div', {});
  const out = h('div', {});
  el.append(head, form, out);

  const edited = () => !!part() && area.value.trim() !== part().text.trim();
  const runButton = h('button', { class: 'btn primary', type: 'button', onclick: () => estimate() }, icon('play'), '추정', h('kbd', {}, 'Ctrl+Enter'));
  const hint = h('span', { class: 'hint grow' });

  function renderHead() {
    clear(head);
    const p = part();
    const title = p ? h('h1', {}, h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'),
      h('span', { class: 'mono' }, p.id), p.adopted ? h('span', { class: 'tag accent', title: `채택한 기록 ${p.adopted} — 모형은 이 계수로 푼다` }, '★ 채택') : null)
      : h('h1', {}, partId ? h('span', { class: 'mono' }, partId) : '새 식');
    const sub = p ? h('div', { class: 'sub' }, p.desc ? h('span', {}, p.desc) : null, h('span', { class: 'mono' }, p.where),
      h('span', {}, p.kind === 'identity' ? '항등식' : '추정식'))
      : h('div', { class: 'sub' }, partId ? '이 부품은 지금 프로젝트에 없습니다(블록 파일에서 지워졌거나 이름이 바뀜).' : '부품에 없는 식을 써서 추정해 봅니다 — 목표가 같은 부품의 후보로 기록됩니다.');
    const name = p?.id || '';
    head.append(h('div', {}, title, sub), name ? h('div', { class: 'tools' },
      h('button', { class: 'btn quiet', type: 'button', title: '이름 복사', onclick: () => copyText(name, `${name} — 복사했습니다`) }, icon('copy'), '이름'),
      h('button', { class: 'btn quiet', type: 'button', title: '터미널에 이름을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(name) }, icon('send'), '터미널로')) : null);
  }

  function renderForm() {
    clear(form);
    const p = part();
    if (p?.kind === 'identity') {
      form.append(h('div', { class: 'readonly-eq' }, p.text),
        h('div', { class: 'banner info', style: { 'margin-top': '14px' } }, icon('info'), h('div', {},
          '항등식은 추정하지 않습니다. 실측으로 양변이 맞는지는 터미널에서 검사합니다. ',
          h('button', { class: 'btn small', type: 'button', style: { 'margin-left': '6px' }, onclick: () => project.sendToTerminal(`equion ident ${p.id} --check`) }, icon('send'), `equion ident ${p.id} --check`))));
      return;
    }
    form.append(h('div', { class: 'eq-box' }, area, h('div', { class: 'eq-foot' }, hint,
      h('button', { class: 'btn small', type: 'button', hidden: true, 'data-role': 'cancel', onclick: () => project.cancel() }, icon('stop'), '취소'), runButton)));
    renderHint();
    requestAnimationFrame(grow);
  }

  function renderHint() {
    clear(hint);
    const p = part();
    if (!p) { hint.append('한 줄에 식 하나 · ', h('code', {}, '종속변수 c 설명변수…'), ' 또는 ', h('code', {}, '좌변 = 식')); return; }
    if (edited()) {
      hint.append('부품의 식과 다릅니다 — 추정하면 후보로 기록됩니다(파일은 그대로). ',
        h('button', { class: 'reset', type: 'button', onclick: () => { area.value = p.text; touched = false; grow(); renderHint(); project.saveView(); } }, '원래 식으로'));
    } else hint.append('부품의 식 그대로입니다 — 고쳐서 추정하면 후보로 기록됩니다.');
  }

  function renderResult() {
    disposeChart();
    clear(out);
    if (problem) {
      out.append(h('div', { class: `banner ${problem.kind === 'cancelled' ? 'warn' : 'error'}`, style: { 'margin-top': '18px' } }, icon('alert'),
        h('div', {}, problem.message, problem.detail ? h('pre', {}, problem.detail) : null)));
    }
    const rec = record;
    if (!rec) {
      if (!problem && part()?.kind !== 'identity') {
        out.append(h('div', { class: 'empty-state' }, loaded ? '아직 추정한 기록이 없습니다. ‘추정’을 누르면 계산하고 기록을 남깁니다.' : '기록을 읽는 중…'));
      }
      return;
    }
    const p = part();
    const flags = [];
    if (p && rec.text && rec.text.trim() !== p.text.trim()) flags.push(h('span', { class: 'tag warn', title: `이 기록의 식: ${rec.text}` }, '부품의 지금 식과 다름'));
    const vintage = project.overview?.vintage?.id;
    if (vintage && rec.data?.id && rec.data.id !== vintage) flags.push(h('span', { class: 'tag warn', title: `이 기록은 자료 ${rec.data.id}로 계산했습니다` }, `자료 회차 다름(${rec.data.id})`));
    const crit = rec.criteria;
    out.append(h('div', { class: 'result-head' },
      h('button', { class: 'rid', type: 'button', title: '결과 카드로 열기', onclick: () => project.openTab({ type: 'record', id: rec.id }) }, rec.id),
      crit ? h('span', { class: `tag ${crit.pass ? 'ok' : 'warn'}`, title: crit.pass ? '판단 기준([criteria])을 통과했습니다' : (crit.reasons || []).join('\n') },
        crit.pass ? '기준 통과' : `걸러짐 — ${(crit.reasons || []).join(', ')}`) : null,
      flags,
      h('span', { class: 'meta' }, h('span', {}, String(rec.method || '').toUpperCase()), h('span', {}, `${rec.sample?.[0]} – ${rec.sample?.[1]}`),
        h('span', {}, `관측 ${rec.n}`), whoLabel(rec.who), h('span', {}, when(rec.created))),
      timing ? h('span', { class: 'timing', title: '누른 뒤 화면에 그리기까지 · 엔진이 계산한 시간' }, `화면까지 ${seconds(timing.total)} · 계산 ${seconds(timing.compute)}`) : null));
    // 기록의 식이 위 칸의 식과 다를 때만 따로 보인다(같으면 되풀이하지 않는다)
    if (rec.text && rec.text.trim() !== area.value.trim()) out.append(h('div', { class: 'readonly-eq', style: { 'margin-bottom': '14px' }, title: '이 기록이 추정한 식' }, rec.text));

    const s = rec.stats || {};
    out.append(h('div', { class: 'facts' }, STATS.filter(([k]) => s[k] != null).slice(0, 6).map(([k, label, d]) => fact(label, num(s[k], d)))));

    const signs = Object.fromEntries((crit?.signs || []).map((x) => [x.term, x]));
    const coefs = h('table', { class: 'grid' }, h('thead', {}, h('tr', {}, ['항', '계수', '표준오차', 't', 'p'].map((c) => h('th', {}, c)))),
      h('tbody', {}, (rec.coefs || []).map((c) => {
        const sign = signs[c.name];
        return h('tr', {}, h('td', {}, c.name, sign ? h('span', { class: `sign ${sign.ok ? 'ok' : 'bad'}`, title: `기대 부호 ${sign.want} — ${sign.ok ? '맞음' : '어긋남'}` }, sign.want) : null),
          h('td', {}, num(c.coef, 4)), h('td', { class: 'dim' }, num(c.se, 4)), h('td', {}, num(c.t, 2)),
          h('td', { class: c.p != null && c.p > 0.05 ? 'alert' : '', title: c.p != null && c.p > 0.05 ? '5% 수준에서 유의하지 않습니다' : '' }, pval(c.p), h('span', { class: 'flag' })));
      })));
    const alpha = crit?.alpha ?? 0.05;
    const diag = h('table', { class: 'grid plain' }, h('thead', {}, h('tr', {}, ['진단', '통계량', 'p'].map((c) => h('th', {}, c)))),
      h('tbody', {}, Object.values(rec.diagnostics || {}).map((d) => h('tr', {}, h('td', {}, d.name), h('td', { class: 'dim' }, num(d.stat, 3)),
        h('td', { class: d.p != null && d.p < alpha ? 'alert' : '', title: d.p != null && d.p < alpha ? `p < ${alpha} — 귀무가설(문제 없음)을 기각합니다` : '' }, pval(d.p), h('span', { class: 'flag' }))))));
    out.append(h('div', { class: 'tables' }, h('div', {}, h('h3', { class: 'cap' }, '계수'), coefs), h('div', {}, h('h3', { class: 'cap' }, '진단'), diag)));

    if (rec.series?.period?.length) {
      const box = h('div', {});
      out.append(h('h3', { class: 'cap' }, '실측 · 적합 · 잔차'), box);
      requestAnimationFrame(() => { disposeChart = drawFit(box, rec.series, { se: s.se_regression }); });
    }
    out.append(h('h3', { class: 'cap' }, '알아서 한 것'),
      h('ul', { class: 'implicit' }, (rec.implicit?.length ? rec.implicit : ['없음']).map((line) => h('li', {}, line))));
    if (said) out.append(h('div', { class: 'said' }, said));
  }

  async function loadShown() {
    // 보던 기록이 없으면 이 부품의 가장 최근 추정 기록
    const id = shown || (partId ? [...project.records].reverse().find((r) => r.kind === 'est' && r.part === partId)?.id : null);
    if (id) {
      try {
        const got = await project.get(`record?id=${encodeURIComponent(id)}`);
        record = { ...got.meta, id: got.id, series: got.series };
        shown = id;
      } catch { shown = null; }
    }
    loaded = true;
    renderResult();
  }

  async function estimate() {
    const text = area.value.trim();
    if (!text || project.busy) return;
    const target = partId && !edited() && part() ? partId : text;
    const clicked = performance.now();
    problem = null;
    setBusy(true);
    try {
      const res = await project.compute('est', { target }, { quiet: true });
      record = res.result;
      shown = record.id;
      said = (res.said || '').trim();
      timing = { total: (performance.now() - clicked) / 1000, compute: res.seconds };
      renderResult();
      requestAnimationFrame(() => {      // 그린 뒤의 시간으로 고친다(성공 기준 S1 — 누른 뒤 화면까지 1초 안)
        timing.total = (performance.now() - clicked) / 1000;
        const t = out.querySelector('.timing');
        if (t) t.textContent = `화면까지 ${seconds(timing.total)} · 계산 ${seconds(timing.compute)}`;
      });
      project.saveView();
    } catch (err) {
      problem = { message: err.message, detail: err.detail, kind: err.kind };
      renderResult();
    } finally {
      setBusy(false);
    }
  }

  function setBusy(on) {
    runButton.disabled = on || project.busy;
    const cancel = form.querySelector('[data-role="cancel"]');
    if (cancel) cancel.hidden = !on;
  }

  area.addEventListener('input', () => { touched = true; grow(); renderHint(); project.saveView(); });
  area.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); estimate(); } });

  renderHead();
  renderForm();
  renderResult();

  return {
    key, type: 'bench', title: partId || '새 식', mono: !!partId, kind: 'est', el,
    desc: () => ({ type: 'bench', ...(partId ? { part: partId } : { free: desc.free }), shown,
      ...(touched && (!part() || edited()) ? { draft: area.value } : {}) }),
    show() { if (!loaded) loadShown(); requestAnimationFrame(grow); runButton.disabled = project.busy; },
    event(e) {
      if (e.type === 'overview') {
        renderHead();
        if (!touched && part()) area.value = part().text;       // 블록 파일의 식이 바뀌었으면 따라간다(쓰던 초안은 그대로 둔다)
        renderForm();
        renderResult();
      } else if (e.type === 'job') runButton.disabled = project.busy;
      else if (e.type === 'records' && !loaded && el.isConnected) loadShown();
    },
    focus() { area.focus(); },
    estimate,
    dispose() { disposeChart(); },
  };
}
