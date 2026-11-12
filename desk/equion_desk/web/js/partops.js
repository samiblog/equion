// 식을 블록에 넣고 빼기 (DESK_V2 §3) — 개별 식으로 남기기 · 모형에 넣기. 패키지의 `equion block add·remove` 와 같은 일이다.
// 무엇이 어느 파일에 어떻게 적히는지(차이) 먼저 보이고, 누르면 쓴다. 바뀜 기록에 남아 되돌릴 수 있다.

import { confirmDialog } from './dialog.js';
import { flash, h } from './util.js';
import { diffBlock } from './views/lists.js';

export const SINGLE = 'single';        // 새 개별 식을 담는 블록(D53) — 어느 모형도 쓰지 않는 블록의 식은 모두 개별 식이다

/** 블록 파일에 식 한 줄 — 먼저 차이를 보이고 확인을 받는다. 돌려주는 것: 더한 부품 id 또는 null */
async function add(project, { block, text, desc = '', from = null, record = null, create = false, title, lead }) {
  let dry;
  try {
    dry = await project.post('part/add', { block, text, desc, from, record, create, dry: true });
  } catch (err) {
    project.notify({ level: 'error', text: err.message });
    return null;
  }
  const body = h('div', { class: 'adopt' }, lead,
    h('h4', {}, '바뀌는 파일'), diffBlock(dry.diff),
    record ? h('p', {}, '더한 식에 ', h('b', { class: 'mono' }, record), ' 를 채택합니다 — 모형은 그 계수로 풉니다.') : null,
    h('div', { class: 'cmd-note mono' }, dry.command),
    h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
  if (!(await confirmDialog({ title, body, confirm: title, wide: true }))) return null;
  try {
    const res = await project.compute('part/add', { block, text, desc, from, record, create }, { quiet: true });
    const r = res.result;
    if (r.adopt_error) project.notify({ level: 'warn', text: `식은 더했지만 채택하지 못했습니다 — ${r.adopt_error}` });
    project.loadOverview();
    return r.part || null;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}

/** 식 작업대의 새 식(부품 아님)을 개별 식으로 남긴다 — 블록 single 에(없으면 만든다). record: 그 식으로 추정한 기록(채택해 둔다) */
export async function saveSingle(project, text, record = null) {
  const exists = project.overview?.blocks?.some((b) => b.name === SINGLE);
  const pid = await add(project, {
    block: SINGLE, text, record, create: !exists, title: '개별 식으로 남기기',
    lead: h('p', {}, '이 식을 ', h('b', {}, '개별 식'), '으로 남깁니다 — 블록 ', h('b', { class: 'mono' }, SINGLE),
      exists ? '' : '(처음이라 새로 만듭니다)', ' 에 한 줄을 더합니다. 어느 모형도 이 블록을 쓰지 않으므로 모형 풀이에는 들어가지 않고, 왼쪽 ‘분석’ 탭의 개별 식에 놓입니다.'),
  });
  if (pid) { flash(`개별 식 ${pid} 를 남겼습니다`); project.side?.showSide('analysis'); }
  return pid;
}

/** 블록을 고르는 칸 — 모형이 쓰는 블록을 앞에 */
function blockPicker(project, skip = null) {
  const blocks = (project.overview?.blocks || []).filter((b) => b.name !== skip);
  const models = project.overview?.models || [];
  const usedBy = (b) => models.filter((m) => (m.blocks || []).includes(b.name)).map((m) => m.name);
  const sorted = [...blocks].sort((a, b) => (usedBy(b).length ? 1 : 0) - (usedBy(a).length ? 1 : 0));
  const select = h('select', { class: 'mini-select', 'aria-label': '블록' }, sorted.map((b) => h('option', { value: b.name },
    `${b.name}${b.desc ? ` — ${b.desc}` : ''}${usedBy(b).length ? `  (모형 ${usedBy(b).join(' · ')})` : '  (어느 모형도 쓰지 않음)'}`)));
  return select;
}

/** 모형에 넣기 — 개별 식(부품)을 모형의 블록으로 옮기거나(from), 분석이 낸 식 후보를 블록에 더한다(record 를 채택) */
export async function toModel(project, { text, from = null, record = null, desc = '' }) {
  const select = blockPicker(project, from ? from.split(':')[0] : null);
  if (!select.options.length) { flash('넣을 블록이 없습니다 — 모형 탭에서 블록을 먼저 만드세요'); return null; }
  const pickBody = h('div', { class: 'adopt' },
    h('p', {}, h('b', { class: 'mono' }, text)),
    h('label', { class: 'field-row' }, h('span', {}, '넣을 블록'), select),
    h('p', { class: 'muted' }, from ? `개별 식 ${from} 는 원래 블록에서 빠지고 고른 블록으로 옮겨집니다.` : '식이 그 블록의 한 줄이 됩니다. 모형이 그 블록을 쓰면 다음 조립·과거 재현부터 들어갑니다.'));
  if (!(await confirmDialog({ title: '모형에 넣기', body: pickBody, confirm: '다음 — 바뀔 내용 보기', wide: true }))) return null;
  const block = select.value;
  const pid = await add(project, {
    block, text, desc, from, record, title: '모형에 넣기',
    lead: h('p', {}, '블록 ', h('b', { class: 'mono' }, block), ' 에 이 식을 더합니다', from ? h('span', {}, ' — ', h('b', { class: 'mono' }, from), ' 는 빠집니다') : '', '.'),
  });
  if (pid) flash(`${pid} — 블록 ${block} 에 넣었습니다`);
  return pid;
}

/** 블록에서 식 한 줄을 뺀다(개별 식 지우기) — 채택표에서도 빠진다 */
export async function removePart(project, part) {
  const p = project.part(part);
  const body = h('div', { class: 'adopt' },
    h('p', {}, h('b', { class: 'mono' }, part), ' 를 블록 파일에서 뺍니다', p?.adopted ? ' — 채택표의 줄도 함께 빠집니다' : '', '. 추정 기록은 그대로 남습니다.'),
    p ? h('div', { class: 'diff' }, h('span', { class: 'dl del' }, `- ${p.text}`)) : null,
    h('div', { class: 'cmd-note mono' }, `equion block remove ${part}`),
    h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
  if (!(await confirmDialog({ title: '식 빼기', body, confirm: '빼기', tone: 'danger', wide: true }))) return false;
  try {
    await project.compute('part/remove', { part }, { quiet: true });
    project.loadOverview();
    flash(`${part} 를 뺐습니다`);
    return true;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return false;
  }
}
