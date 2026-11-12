// 추정 결과 한 벌(기록 하나)과 겹쳐 보기(기록 둘에서 넷) — 식 작업대의 아래쪽.
//
// 결과는 기록에서 그린다(다시 계산하지 않는다). 단추가 하는 일은 모두 명령과 같다: 채택 = `equion adopt`,
// 이 후보로 과거 재현 = `equion hs --swap`, 진단 더 보기 = `equion an diag`. 'Claude로'는 이름과 요약을 터미널에 붙이기만 한다.

import { align, drawFit, drawLines, unionPeriods } from '../chart.js';
import { popMenu } from '../dialog.js';
import { clear, h, icon, num, pval, seconds, short, when, whoLabel } from '../util.js';

const STATS = [['adj_r_squared', '조정 R²', 4], ['se_regression', '표준오차', 4], ['durbin_watson', 'DW', 3], ['aic', 'AIC', 1], ['bic', 'BIC', 1]];
export const OVERLAY_COLORS = ['var(--k-est)', 'var(--k-sim)', 'var(--k-hs)', 'var(--k-an)'];

const termName = (name) => (name === 'const' ? 'c' : name);
/** 항 이름의 변수 — CN(-1) → CN, log(Y) → Y. 우클릭하면 변수 메뉴(DESK_V2 §2.2) */
const termVar = (name) => /^([A-Za-z_][A-Za-z0-9_]*)(\(-?\d+\))?$/.exec(name)?.[1] || /\(([A-Za-z_][A-Za-z0-9_]*)(\(-?\d+\))?\)/.exec(name)?.[1] || null;

/** 'Claude로' — 터미널에 붙일 한 줄(이름과 요약, Enter 없이) */
export function summaryLine(rec) {
  const s = rec.stats || {};
  const crit = rec.criteria;
  const bits = [`R²adj ${num(s.adj_r_squared, 4)}`, `SE ${num(s.se_regression, 4)}`, `DW ${num(s.durbin_watson, 2)}`];
  if (rec.sim?.rmspe != null) bits.push(`단독 모의 RMSPE ${rec.sim.rmspe.toFixed(2)}%`);
  if (crit) bits.push(crit.pass ? '기준 통과' : `걸러짐: ${(crit.reasons || []).join(', ')}`);
  return `${rec.part ? `${rec.part} 후보 ` : ''}${rec.id} — ${bits.join(' · ')}`;
}

/** 단독 모의 시리즈(모의한 구간만) — {period, actual, sim} 또는 null */
function simSeries(rec) {
  const s = rec.series || {};
  const key = Object.keys(s).find((k) => k.endsWith('_sim'));
  if (!key) return null;
  const actual = s[key.slice(0, -4)] || [];
  const keep = (s.period || []).map((_, i) => i).filter((i) => s[key][i] != null);
  if (!keep.length) return null;
  return { period: keep.map((i) => s.period[i]), actual: keep.map((i) => actual[i]), sim: keep.map((i) => s[key][i]) };
}

function segmented(options, value, pick) {
  return h('div', { class: 'segmented small', role: 'tablist' }, options.map(([key, label, off, title]) => h('button', {
    type: 'button', role: 'tab', 'aria-pressed': String(key === value), disabled: !!off, title: title || '', onclick: () => pick(key),
  }, label)));
}

/**
 * 기록 하나의 결과. ctx: {project, part, adopted, vintage, timing, said, view:{tab, picked}, setView(patch),
 *   actions: {adopt, hsSwap, toEditor, send, diag, card, dummy}}. 돌려주는 것: 치우는 함수.
 */
export function renderSingle(box, rec, ctx) {
  clear(box);
  let dispose = () => {};
  const { part, actions } = ctx;
  const crit = rec.criteria;
  const s = rec.stats || {};
  const isAdopted = ctx.adopted === rec.id;

  const flags = [];
  if (rec.cov) flags.push(h('span', { class: 'tag', title: `계수의 표준오차·t·p는 ${rec.cov.label || rec.cov.type} 기준입니다(계수는 같다)` }, `표준오차 ${String(rec.cov.type).toUpperCase()}`));
  if (part && rec.text && rec.text.trim() !== part.text.trim()) flags.push(h('span', { class: 'tag', title: `블록 파일의 지금 식: ${part.text}` }, '파일의 식과 다름'));
  if (ctx.vintage && rec.data?.id && rec.data.id !== ctx.vintage) flags.push(h('span', { class: 'tag warn', title: `이 기록은 자료 ${rec.data.id}로 계산했습니다 — 지금 회차는 ${ctx.vintage}` }, `자료 회차 다름(${rec.data.id})`));

  const models = part?.models || [];
  const hsButton = h('button', {
    class: 'btn small', type: 'button', disabled: !models.length,
    title: models.length ? `equion hs ${models[0]} --swap ${part.id}=${rec.id} — 파일은 그대로 두고 이 후보를 끼워 모형을 풀어, 지금 파일로 푼 것과 견준다` : '이 부품을 쓰는 모형이 없습니다',
    onclick: (e) => {
      if (models.length <= 1) { actions.hsSwap(rec, models[0]); return; }
      popMenu(e.currentTarget, [h('div', { class: 'menu-title' }, '어느 모형에 끼워 풀까요'),
        ...ctx.orderedModels(models).map((m) => ({ label: m.name, hint: m.note, onPick: () => actions.hsSwap(rec, m.name) }))]);
    },
  }, icon('rewind'), '이 후보로 과거 재현', models.length > 1 ? icon('chevron', 'down') : null);

  box.append(h('div', { class: 'result-head' },
    h('button', { class: 'rid', type: 'button', title: '결과 카드로 열기', onclick: () => actions.card(rec) }, rec.id),
    isAdopted ? h('span', { class: 'tag accent', title: '이 부품이 채택한 기록 — 모형은 이 계수로 푼다' }, '★ 채택') : null,
    crit ? h('span', { class: `tag ${crit.pass ? 'ok' : 'warn'}`, title: crit.pass ? '판단 기준([criteria])을 통과했습니다' : (crit.reasons || []).join('\n') },
      crit.pass ? '기준 통과' : `걸러짐 — ${(crit.reasons || []).join(', ')}`) : null,
    flags,
    h('span', { class: 'meta' }, h('span', {}, rec.method_label || String(rec.method || '').toUpperCase()), h('span', {}, `${rec.sample?.[0]} – ${rec.sample?.[1]}`), h('span', {}, `관측 ${rec.n}`),
      whoLabel(rec.who), h('span', {}, when(rec.created))),
    ctx.timing ? h('span', { class: 'timing', title: '누른 뒤 화면에 그리기까지 · 엔진이 계산한 시간' }, `화면까지 ${seconds(ctx.timing.total)} · 계산 ${seconds(ctx.timing.compute)}`) : null),
  h('div', { class: 'result-actions' },
    h('button', {
      class: `btn small ${isAdopted ? '' : 'primary'}`.trim(), type: 'button', disabled: isAdopted || !part,
      title: isAdopted ? '이미 채택한 기록입니다' : part ? `equion adopt ${rec.id} — 블록 파일의 그 줄을 이 식으로 바꾸고 모형이 이 계수로 풀게 한다(바뀜 기록에 남는다)` : '어느 부품의 후보인지 모르는 기록입니다',
      onclick: () => actions.adopt(rec),
    }, icon('pin'), isAdopted ? '채택됨' : '채택'),
    hsButton,
    h('button', { class: 'btn small quiet', type: 'button', title: '이 기록의 식을 위의 식 칸으로 가져와 고쳐 본다', onclick: () => actions.toEditor(rec) }, icon('equation'), '식 칸으로'),
    h('button', { class: 'btn small quiet', type: 'button', title: `터미널에 붙인다(Enter 는 직접): ${summaryLine(rec)}`, onclick: () => actions.send(rec) }, icon('send'), 'Claude로'),
    h('button', { class: 'btn small quiet more', type: 'button', title: '더 보기', 'aria-label': '더 보기', onclick: (e) => popMenu(e.currentTarget, [
      { label: '진단 더 보기', hint: 'CUSUM·Chow — equion an diag', onPick: () => actions.diag(rec) },
      { label: '결과 카드로 열기', hint: 'summary.md', onPick: () => actions.card(rec) },
      { label: '이름 복사', hint: rec.id, onPick: () => actions.copy(rec) }], { align: 'right', cls: 'plain' }) }, icon('list'))));

  if (rec.text && ctx.editorText != null && rec.text.trim() !== ctx.editorText.trim()) {
    box.append(h('div', { class: 'readonly-eq compact', title: '이 기록이 추정한 식' }, rec.text));
  }
  box.append(h('div', { class: 'statline' }, STATS.filter(([k]) => s[k] != null).map(([k, label, d]) => h('span', { class: 'st', title: k === 'adj_r_squared' ? `R² ${num(s.r_squared, 4)}` : '' }, h('span', { class: 'k' }, label), h('b', {}, num(s[k], d)))),
    rec.sim?.rmspe != null ? h('span', { class: 'st', title: `${rec.sim.start}~${rec.sim.end} 식 하나의 동태 모의(다른 변수는 실측)의 RMSPE` }, h('span', { class: 'k' }, '단독 모의'), h('b', {}, `${rec.sim.rmspe.toFixed(2)}%`)) : null));

  const signs = Object.fromEntries((crit?.signs || []).map((x) => [x.term, x]));
  const coefs = h('table', { class: 'grid' }, h('thead', {}, h('tr', {}, ['항', '계수', '표준오차', 't', 'p'].map((c) => h('th', {}, c)))),
    h('tbody', {}, (rec.coefs || []).map((c) => {
      const sign = signs[c.name];
      return h('tr', {}, h('td', { 'data-var': termVar(c.name) }, termName(c.name), sign ? h('span', { class: `sign ${sign.ok ? 'ok' : 'bad'}`, title: `기대 부호 ${sign.want} — ${sign.ok ? '맞음' : '어긋남'}` }, sign.want) : null),
        h('td', {}, num(c.coef, 4)), h('td', { class: 'dim' }, num(c.se, 4)), h('td', {}, num(c.t, 2)),
        h('td', { class: c.p != null && c.p > 0.05 ? 'alert' : '', title: c.p != null && c.p > 0.05 ? '5% 수준에서 유의하지 않습니다' : '' }, pval(c.p), h('span', { class: 'flag' })));
    })));
  const alpha = crit?.alpha ?? 0.05;
  const diag = h('table', { class: 'grid plain' }, h('thead', {}, h('tr', {}, ['진단', '통계량', 'p'].map((c) => h('th', {}, c)))),
    h('tbody', {}, Object.values(rec.diagnostics || {}).map((d) => h('tr', {}, h('td', {}, d.name), h('td', { class: 'dim' }, num(d.stat, 3)),
      h('td', { class: d.p != null && d.p < alpha ? 'alert' : '', title: d.p != null && d.p < alpha ? `p < ${alpha} — 문제 없음 가설을 기각합니다` : '' }, pval(d.p), h('span', { class: 'flag' }))))));
  box.append(h('div', { class: 'tables' },
    h('div', {}, h('h3', { class: 'cap' }, '계수', rec.cov ? h('small', {}, ` — 표준오차는 ${rec.cov.label || rec.cov.type}`) : null), coefs),
    h('div', {}, h('h3', { class: 'cap' }, '진단'), diag)));

  // 차트 — 실측·적합·잔차 / 단독 모의
  const sim = simSeries(rec);
  const hasFit = !!rec.series?.period?.length;
  if (hasFit) {
    const tab = ctx.view.tab === 'sim' && sim ? 'sim' : 'fit';
    const chart = h('div', {});
    const pinned = h('div', { class: 'pinned', hidden: true });
    box.append(h('div', { class: 'chart-head' }, h('h3', { class: 'cap' }, '차트'),
      segmented([['fit', '실측 · 적합 · 잔차'], ['sim', '단독 모의', !sim, sim ? '' : '이 기록에는 단독 모의가 없습니다 — ‘단독 모의’를 켜고 추정하세요']], tab, (key) => ctx.setView({ tab: key }))), pinned, chart);
    const se = s.se_regression;
    const showPinned = (i) => {
      const p = rec.series.period[i];
      const r = rec.series.resid[i];
      pinned.hidden = false;
      clear(pinned).append(h('b', {}, p), h('span', {}, `실측 ${short(rec.series.actual[i])}`), h('span', {}, `적합 ${short(rec.series.fitted[i])}`),
        h('span', { class: se && Math.abs(r) > 2 * se ? 'alert' : '' }, `잔차 ${r > 0 ? '+' : ''}${short(r)}${se ? ` (${(r / se).toFixed(1)}σ)` : ''}`),
        h('span', { class: 'grow' }),
        h('button', { class: 'btn small', type: 'button', title: `식 칸에 @d(${p}) 를 붙인다 — 계산은 추정을 누를 때`, onclick: () => actions.dummy(p) }, icon('plus'), `이 기간 더미 @d(${p})`),
        h('button', { class: 'icon-btn', type: 'button', title: '짚은 것 풀기', 'aria-label': '짚은 것 풀기', onclick: () => ctx.setView({ picked: null }) }, icon('x')));
    };
    requestAnimationFrame(() => {
      if (tab === 'sim') {
        dispose = drawLines(chart, { period: sim.period, title: '단독 모의', note: `${rec.sim.start}~${rec.sim.end} · RMSPE ${rec.sim.rmspe.toFixed(2)}% — 다른 변수는 실측`,
          lines: [{ label: '실측', values: sim.actual, color: 'var(--c-actual)', width: 1.5 }, { label: '단독 모의', values: sim.sim, color: 'var(--c-fitted)', dashed: true, width: 1.7 }] });
      } else {
        const picked = ctx.view.picked != null ? rec.series.period.indexOf(ctx.view.picked) : -1;
        dispose = drawFit(chart, rec.series, { se, picked, onPick: (i) => ctx.setView({ picked: rec.series.period[i] }) });
        if (picked >= 0) showPinned(picked);
      }
    });
  }
  box.append(h('h3', { class: 'cap' }, '알아서 한 것'),
    h('ul', { class: 'implicit' }, (rec.implicit?.length ? rec.implicit : ['없음']).map((line) => h('li', {}, line))));
  if (ctx.said) box.append(h('div', { class: 'said' }, ctx.said));
  return () => dispose();
}

/**
 * 겹쳐 보기. recs: 기록 둘에서 넷(고른 순). ctx: {view:{otab}, setView, remove(id), close(), select(id)}. 돌려주는 것: 치우는 함수.
 */
export function renderOverlay(box, recs, ctx) {
  clear(box);
  let dispose = () => {};
  const color = (i) => OVERLAY_COLORS[i % OVERLAY_COLORS.length];
  const deps = new Set(recs.map((r) => r.dependent));
  const samples = new Set(recs.map((r) => (r.sample || []).join('~')));
  const sims = recs.map(simSeries);

  box.append(h('div', { class: 'result-head' }, h('b', { class: 'ov-title' }, `겹쳐 보기 — ${recs.length}개`),
    h('span', { class: 'grow' }), h('button', { class: 'btn small', type: 'button', onclick: () => ctx.close() }, icon('x'), '닫기')),
  h('div', { class: 'ov-legend' }, recs.map((r, i) => h('div', { class: 'ov-item', style: { '--c': color(i) } },
    h('span', { class: 'sw' }), h('button', { class: 'rid', type: 'button', title: '이 기록만 보기', onclick: () => ctx.select(r.id) }, r.id.split(':')[1]),
    h('span', { class: 'mono eq' }, r.text), whoLabel(r.who),
    h('button', { class: 'icon-btn', type: 'button', title: '겹쳐 보기에서 빼기', 'aria-label': '빼기', onclick: () => ctx.remove(r.id) }, icon('x'))))));
  if (deps.size > 1) box.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, `종속변수가 다릅니다(${[...deps].join(' · ')}) — 적합값과 R²·SE·AIC·BIC는 견줄 수 없습니다. 단독 모의로 견주세요.`)));
  else if (samples.size > 1) box.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, `표본이 다릅니다(${[...samples].join(' · ')}) — AIC·BIC는 그대로 견주기 어렵습니다.`)));

  const anySim = sims.some(Boolean);
  const tab = ctx.view.otab === 'sim' && anySim ? 'sim' : ctx.view.otab === 'fit' && deps.size === 1 ? 'fit' : ctx.view.otab === 'resid' ? 'resid' : deps.size === 1 ? 'fit' : 'resid';
  const chart = h('div', {});
  box.append(h('div', { class: 'chart-head' }, h('h3', { class: 'cap' }, '차트'),
    segmented([['fit', '적합', deps.size > 1, deps.size > 1 ? '종속변수가 달라 한 축에 놓을 수 없습니다' : ''], ['resid', '잔차'],
      ['sim', '단독 모의', !anySim, anySim ? '' : '고른 기록에 단독 모의가 없습니다 — ‘단독 모의’를 켜고 추정하세요']], tab, (key) => ctx.setView({ otab: key }))), chart);
  requestAnimationFrame(() => {
    if (tab === 'sim') {
      const period = unionPeriods(sims.filter(Boolean).map((x) => x.period));
      const base = sims.filter(Boolean).sort((a, b) => b.period.length - a.period.length)[0];
      const missing = recs.filter((_, i) => !sims[i]).map((r) => r.id.split(':')[1]);
      dispose = drawLines(chart, { period, title: '단독 모의 겹쳐 보기', note: missing.length ? `단독 모의 없음: ${missing.join(', ')}` : '다른 변수는 실측',
        lines: [{ label: '실측', values: align(period, base.period, base.actual), color: 'var(--c-actual)', width: 1.5 },
          ...recs.map((r, i) => (sims[i] ? { label: `${r.id.split(':')[1]}${r.sim?.rmspe != null ? ` (${r.sim.rmspe.toFixed(2)}%)` : ''}`, values: align(period, sims[i].period, sims[i].sim), color: color(i) } : null)).filter(Boolean)] });
    } else {
      const period = unionPeriods(recs.map((r) => r.series?.period));
      const key = tab === 'fit' ? 'fitted' : 'resid';
      const longest = [...recs].sort((a, b) => (b.series?.period?.length || 0) - (a.series?.period?.length || 0))[0];
      dispose = drawLines(chart, { period, zero: tab === 'resid', title: tab === 'fit' ? '적합 겹쳐 보기' : '잔차 겹쳐 보기',
        lines: [...(tab === 'fit' ? [{ label: '실측', values: align(period, longest.series.period, longest.series.actual), color: 'var(--c-actual)', width: 1.5 }] : []),
          ...recs.map((r, i) => ({ label: r.id.split(':')[1], values: align(period, r.series?.period, r.series?.[key]), color: color(i) }))] });
    }
  });

  // 계수와 적합 통계를 나란히 — 항은 처음 나온 순서로 모은다
  const terms = [];
  for (const r of recs) for (const c of r.coefs || []) if (!terms.includes(c.name)) terms.push(c.name);
  const cell = (r, name) => {
    const c = (r.coefs || []).find((x) => x.name === name);
    if (!c) return h('td', { class: 'dim' }, '·');
    return h('td', { class: c.p != null && c.p > 0.05 ? 'insig' : '', title: `표준오차 ${num(c.se, 4)} · p ${pval(c.p)}` }, num(c.coef, 4), h('small', {}, ` (${num(c.t, 1)})`));
  };
  const statRow = (label, get, cls = '') => h('tr', { class: cls }, h('td', {}, label), recs.map((r) => h('td', {}, get(r))));
  const table = h('table', { class: 'grid ov-table' },
    h('thead', {}, h('tr', {}, h('th', {}, '항 — 계수 (t)'), recs.map((r, i) => h('th', {}, h('span', { class: 'sw', style: { '--c': color(i) } }), r.id.split(':')[1])))),
    h('tbody', {}, terms.map((name) => h('tr', {}, h('td', { 'data-var': termVar(name) }, termName(name)), recs.map((r) => cell(r, name)))),
      statRow('조정 R²', (r) => num(r.stats?.adj_r_squared, 4), 'first'), statRow('회귀 표준오차', (r) => num(r.stats?.se_regression, 4)),
      statRow('DW', (r) => num(r.stats?.durbin_watson, 2)), statRow('AIC', (r) => num(r.stats?.aic, 1)), statRow('BIC', (r) => num(r.stats?.bic, 1)),
      statRow('LM p', (r) => pval(r.diagnostics?.lm?.p)), statRow('White p', (r) => pval(r.diagnostics?.white?.p)),
      statRow('단독 모의 RMSPE', (r) => (r.sim?.rmspe != null ? `${r.sim.rmspe.toFixed(2)}%` : '—')),
      statRow('표본', (r) => `${r.sample?.[0]}–${r.sample?.[1]}`), statRow('관측', (r) => String(r.n)),
      statRow('기준', (r) => (r.criteria == null ? '—' : r.criteria.pass ? h('span', { class: 'tag ok' }, '통과') : h('span', { class: 'tag warn', title: (r.criteria.reasons || []).join('\n') }, (r.criteria.reasons || [])[0] || '걸러짐')))));
  box.append(h('h3', { class: 'cap' }, '계수와 적합'), h('div', { class: 'ov-wrap' }, table));
  return () => dispose();
}
