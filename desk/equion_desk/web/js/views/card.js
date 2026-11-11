// 결과 카드 — 기록 하나(`work/<종류>/<이름>/`)의 카드 `summary.md` 를 그린다. 손으로 낸 결과도 터미널·Claude 가 낸 결과도 같은 모양이다.
// 기록은 고치지 않는 파일이라(D33) 한 번 읽으면 다시 읽지 않는다.
//
// 카드 위에는 그 기록을 만든 명령을 그대로 보이고(눌러 복사), 바꿔 끼워 푼 과거 재현(`hs --swap … --vs …`)이면
// 변수마다 전후 RMSPE 를 먼저 보인다 — '이 후보로 과거 재현'을 누른 사람이 맨 먼저 알고 싶은 것이다.

import { renderDoc } from '../md.js';
import { bytes, clear, cmdText, copyText, h, icon, kindPill, when, whoLabel } from '../util.js';
import { exportXlsx, sendToReport } from './send.js';

/** 전후 비교(변수마다 RMSPE 가 얼마에서 얼마로) — 좋아진 것은 초록, 나빠진 것은 붉게 */
function compareStrip(vs) {
  const rows = Object.entries(vs.rmspe || {}).filter(([, v]) => Array.isArray(v) && v[0] != null && v[1] != null);
  if (!rows.length) return null;
  const EPS = 0.005;      // 보이는 자릿수(소수 둘째) 아래의 차이는 '그대로'
  const better = rows.filter(([, [a, b]]) => b < a - EPS).length;
  const worse = rows.filter(([, [a, b]]) => b > a + EPS).length;
  return h('div', { class: 'vs' },
    h('div', { class: 'vs-head' }, h('b', {}, '전후 비교'), h('span', { class: 'muted' }, `RMSPE% · ${vs.id} → 이 기록`),
      h('span', { class: 'grow' }), better ? h('span', { class: 'tag ok' }, `좋아짐 ${better}`) : null, worse ? h('span', { class: 'tag bad' }, `나빠짐 ${worse}`) : null),
    h('div', { class: 'vs-grid' }, rows.map(([name, [a, b]]) => {
      const d = b - a;
      const cls = d < -EPS ? 'good' : d > EPS ? 'poor' : '';
      return h('div', { class: `vs-cell ${cls}`.trim(), title: `${name}: ${a.toFixed(4)}% → ${b.toFixed(4)}%` },
        h('div', { class: 'k mono' }, name), h('div', { class: 'v' }, `${a.toFixed(2)} → ${b.toFixed(2)}`),
        h('div', { class: 'd' }, Math.abs(d) <= EPS ? '그대로' : `${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(2)}%p`));
    })));
}

export function cardView(project, desc) {
  const id = desc.id;
  const kind = String(id).split(':')[0];
  const el = h('div', { class: 'view' });
  let loaded = false;

  async function load() {
    loaded = true;
    clear(el);
    el.append(h('div', { class: 'empty-state' }, '기록을 읽는 중…'));
    let rec;
    try {
      rec = await project.get(`record?id=${encodeURIComponent(id)}`);
    } catch (err) {
      clear(el);
      el.append(h('div', { class: 'view-head' }, h('div', {}, h('h1', {}, kindPill(kind), h('span', { class: 'mono' }, id)))),
        h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message)));
      return;
    }
    const m = rec.meta || {};
    const command = cmdText(m.command);
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, kindPill(kind), h('span', { class: 'mono' }, id)),
        h('div', { class: 'sub' }, m.who ? whoLabel(m.who) : null, m.created ? h('span', {}, when(m.created)) : null, h('span', { class: 'mono' }, rec.path))),
      h('div', { class: 'tools' },
        kind === 'est' && m.part ? h('button', { class: 'btn', type: 'button', title: '이 기록을 후보 목록에서 고른 채로 식 작업대를 연다', onclick: () => project.openTab({ type: 'bench', part: m.part, shown: id }) }, icon('equation'), '식 작업대에서') : null,
        kind === 'sim' && m.model ? h('button', { class: 'btn', type: 'button', title: '이 전망을 고른 채로 전망 작업대를 연다', onclick: () => project.openTab({ type: 'forecast', model: m.model, shown: id }) }, icon('forward'), '전망 작업대에서') : null,
        kind === 'hs' && m.model && project.overview?.models.some((x) => x.name === m.model) ? h('button', { class: 'btn', type: 'button', title: '이 풀이를 고른 채로 모형 작업대를 연다 — 오차·풀이 상태·원인 따라가기',
          onclick: () => project.openTab({ type: 'model', model: m.model, shown: id }) }, icon('cube'), '모형 작업대에서') : null,
        ['est', 'hs', 'sim', 'an'].includes(kind) ? h('button', { class: 'btn quiet', type: 'button', 'data-act': 'to-report', title: '이 기록의 표를 보고서의 한 구역으로 보낸다', onclick: () => sendToReport(project, id) }, icon('doc'), '보고서로') : null,
        ['est', 'hs', 'sim'].includes(kind) ? h('button', { class: 'btn quiet', type: 'button', 'data-act': 'to-xlsx', title: '값·값의 종류·출처를 엑셀로', onclick: () => exportXlsx(project, [id]) }, icon('table'), '엑셀로') : null,
        h('button', { class: 'btn quiet', type: 'button', title: '이름 복사', onclick: () => copyText(id, `${id} — 복사했습니다`) }, icon('copy'), '이름'),
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 이름을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(id) }, icon('send'), '터미널로'))));
    if (command) {
      el.append(h('button', { class: 'cmdline', type: 'button', title: '이 기록을 만든 명령 — 누르면 복사합니다', onclick: () => copyText(command, '명령을 복사했습니다') },
        h('span', { class: 'prompt' }, '>'), h('span', { class: 'cmd' }, command), icon('copy')));
    }
    if (kind === 'hs' && m.vs?.rmspe) {
      const strip = compareStrip(m.vs);
      if (strip) el.append(strip);
    }
    const swaps = Object.entries(m.swaps || {});
    if (swaps.length) {
      el.append(h('div', { class: 'banner info' }, icon('layers'), h('div', {}, '바꿔 끼워 풀었습니다 — 파일은 그대로입니다. ',
        swaps.map(([part, value]) => h('span', { class: 'swap' }, h('b', { class: 'mono' }, part), ' ← ', h('span', { class: 'mono' }, String(value)),
          String(value).startsWith('est:') && project.part(part) ? h('button', { class: 'btn small', type: 'button', title: '그 후보를 고른 채로 식 작업대를 연다 — 채택은 거기서',
            onclick: () => project.openTab({ type: 'bench', part, shown: String(value) }) }, icon('equation'), '식 작업대에서') : null)))));
    }
    const doc = h('div', { class: 'of-record' });
    el.append(doc);
    if (rec.summary) {
      await renderDoc(doc, rec.summary, { pid: project.id, dir: rec.path, openFile: (path) => project.openTab({ type: 'file', path }) });
    } else doc.append(h('div', { class: 'empty-state' }, '이 기록에는 카드(summary.md)가 없습니다.'));
    el.append(h('div', { class: 'files-line' }, '파일', rec.files.map((f) => h('button', {
      class: 'file-chip', type: 'button', title: bytes(f.size), onclick: () => project.openTab({ type: 'file', path: `${rec.path}/${f.name}` }),
    }, f.name))));
  }

  return {
    key: `record:${id}`, type: 'record', title: id, mono: true, kind, el,
    desc: () => ({ type: 'record', id }),
    show() { if (!loaded) load(); },
    event() {},
    dispose() {},
  };
}
