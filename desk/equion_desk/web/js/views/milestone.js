// 이정표 (D61) — 중요한 때의 정의·자료 회차·고정한 기록. 지금과 견주고(파일마다 같음 · 고침 · 새로 · 지움과 차이), 정의를 그때로 되돌린다.
// 되돌리기는 바뀜 기록 하나로 남아 그것도 되돌릴 수 있다. 계산은 하지 않는다 — 되돌린 뒤 필요하면 다시 푼다.

import { confirmDialog, nameRule } from '../dialog.js';
import { clear, flash, h, icon, when, WHO } from '../util.js';
import { diffBlock } from './lists.js';

const STATUS = { same: ['같음', ''], changed: ['고침', 'warn'], added: ['새로', 'accent'], removed: ['지움', 'warn'], missing: ['사본 없음', 'warn'] };

export function milestoneView(project, desc) {
  const name = desc.name;
  const el = h('div', { class: 'view milestone-view' });
  const st = { data: null, error: null };
  let loaded = false;

  async function load() {
    loaded = true;
    try { st.data = await project.get(`milestone?name=${encodeURIComponent(name)}`); st.error = null; } catch (err) { st.error = err.message; }
    render();
  }

  async function restore(files = null) {
    const d = st.data;
    const moved = d.files.filter((f) => f.status !== 'same' && (!files || files.includes(f.path)));
    const body = h('div', { class: 'adopt' },
      h('p', {}, '정의 파일을 이정표 ', h('b', { class: 'mono' }, name), ' 때로 되돌립니다. 그때 있던 파일은 그때 내용으로, 그 뒤에 생긴 파일은 지웁니다. 계산 기록은 그대로입니다.'),
      h('div', { class: 'diff' }, moved.map((f) => h('span', { class: `dl ${f.status === 'added' ? 'del' : 'add'}` }, `${f.status === 'added' ? '지움(그 뒤에 생김)' : f.status === 'removed' ? '되살림' : '그때 내용으로'}  ${f.path}`))),
      d.vintage !== d.vintage_now ? h('p', {}, '자료 회차도 ', h('b', { class: 'mono' }, d.vintage), ' 로 돌아갑니다(equion.toml).') : null,
      h('div', { class: 'cmd-note mono' }, `equion milestone restore ${name}${files ? files.map((f) => ` --file ${f}`).join('') : ''}`),
      h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    if (!(await confirmDialog({ title: '이정표로 되돌리기', body, confirm: files ? '이 파일만 되돌리기' : '되돌리기', wide: true }))) return;
    try {
      const res = await project.compute('milestone/restore', { name, ...(files ? { files } : {}) }, { quiet: true });
      flash(res.result.change ? `되돌렸습니다 — 바뀜 기록 ${res.result.change}` : '지금이 이정표와 같습니다(바꾼 것 없음)');
      project.loadOverview();
      await load();
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  function render() {
    clear(el);
    const d = st.data;
    const m = d?.milestone;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, icon('pin'), h('span', { class: 'mono' }, name), m?.note ? h('span', { class: 'tag' }, m.note) : null),
        h('div', { class: 'sub' }, m ? [h('span', {}, when(m.created)), h('span', {}, WHO[m.who] || m.who || ''), h('span', { class: 'mono' }, `자료 ${m.vintage || '(자료 파일)'}`),
          h('span', {}, `정의 파일 ${m.files}`), h('span', {}, `고정한 기록 ${m.records.length}`)] : null)),
      d && !d.defs_same ? h('div', { class: 'tools' }, h('button', { class: 'btn primary', type: 'button', 'data-act': 'restore', disabled: project.busy, onclick: () => restore() }, icon('rewind'), '정의를 이때로 되돌리기')) : null));
    if (st.error) { el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error))); return; }
    if (!d) { el.append(h('div', { class: 'empty-state' }, '읽는 중…')); return; }
    const moved = d.files.filter((f) => f.status !== 'same');
    el.append(h('div', { class: `banner ${d.same ? 'ok' : 'info'}` }, icon(d.same ? 'check' : 'info'),
      h('div', {}, d.same ? '정의도 자료 회차도 이정표 때와 같습니다.' : d.defs_same ? '정의는 이정표 때와 같습니다 — 자료 회차만 다릅니다(되돌리기는 정의만, 회차는 자료 탭에서).'
        : `이정표 뒤에 바뀐 정의 파일 ${moved.length}개`,
        d.vintage !== d.vintage_now ? [h('br'), `자료 회차 ${d.vintage} → 지금 ${d.vintage_now}`] : null)));
    if (moved.length) {
      el.append(h('div', { class: 'card-meta' }, moved.map((f) => {
        const [label, tone] = STATUS[f.status];
        return h('div', { class: 'pair' }, h('span', { class: `tag ${tone}`.trim() }, label),
          h('button', { class: 'file-chip', type: 'button', onclick: () => project.openTab({ type: 'file', path: f.path }) }, f.path),
          f.status === 'changed' ? h('span', { class: 'muted' }, h('span', { class: 'plus' }, `+${f.plus}`), ' ', h('span', { class: 'minus' }, `−${f.minus}`)) : null,
          moved.length > 1 ? h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'restore-file', onclick: () => restore([f.path]) }, '이 파일만 되돌리기') : null);
      })));
      el.append(h('p', { class: 'muted note' }, '차이는 이정표 → 지금입니다(+ 는 그 뒤에 더한 줄).'), diffBlock(d.diff));
    }
    if (m?.records.length) {
      el.append(h('h3', { class: 'cap' }, '이정표가 적은 기록'), h('div', { class: 'card-meta' }, m.records.map((r) => h('button', { class: 'file-chip mono', type: 'button', onclick: () => project.openRecord(r) }, r))));
    }
  }

  render();
  return {
    key: `milestone:${name}`, type: 'milestone', title: `이정표 ${name}`, icon: 'pin', el,
    desc: () => ({ type: 'milestone', name }),
    show() { if (!loaded) load(); },
    event(e) { if ((e.type === 'change' || e.type === 'defs') && loaded && el.isConnected) load(); },
    dispose() {},
  };
}

/** 이정표 만들기 — 이름과 메모를 받아 `equion milestone make` */
export async function makeMilestone(project) {
  const today = new Date().toISOString().slice(0, 7).replace('-', '_');
  const name = h('input', { class: 'mini-input wide', type: 'text', value: `m_${today}`, spellcheck: 'false', 'aria-label': '이정표 이름' });
  const note = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '예: 11월 전망 확정', 'aria-label': '메모' });
  const body = h('div', { class: 'adopt define-form' },
    h('p', {}, '지금의 정의 파일(식 · 모형 · 자료 정의 · 가정 · 시나리오 · 노트 · 보고서…) 사본과 자료 회차, 고정한 기록을 이름으로 묶어 둡니다. 나중에 지금과 견주거나 정의를 이때로 되돌립니다.'),
    h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '메모'), note),
    h('p', { class: 'muted' }, '정의 파일은 바뀌지 않습니다. 이정표가 적은 기록은 정리(equion work clean)에서 빠집니다.'));
  setTimeout(() => name.select(), 30);
  if (!(await confirmDialog({ title: '이정표 만들기', body, confirm: '만들기', wide: true, valid: () => nameRule(name.value, { what: '이정표 이름', max: 64 }), enter: true }))) return null;
  try {
    const res = await project.compute('milestone/make', { name: name.value.trim(), note: note.value.trim() }, { quiet: true });
    flash(`이정표 ${res.result.name} 를 만들었습니다 — 정의 파일 ${res.result.files}개`);
    project.side?.loadMilestones?.();
    project.openTab({ type: 'milestone', name: res.result.name });
    return res.result.name;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}

/** 묶어 보내기 — 원자료를 넣을지 · 기록을 얼마나 넣을지 고르고 `equion bundle make` */
export async function makeBundle(project) {
  const raw = h('input', { type: 'checkbox' });
  const records = h('select', { class: 'mini-select', 'aria-label': '기록' }, [['keep', '남길 기록만(채택 · 고정 · 노트·보고서가 가리키는 것)'], ['all', '모두'], ['none', '넣지 않음']].map(([v, l]) => h('option', { value: v }, l)));
  const body = h('div', { class: 'adopt define-form' },
    h('p', {}, '프로젝트를 zip 하나로 묶습니다 — 정의 · 노트 · 보고서 · 지금 자료 회차 · 이정표, 그리고 고른 기록. 받은 쪽은 Equion Desk 의 ‘묶음 열기’나 equion bundle open 으로 엽니다.'),
    h('label', { class: 'check-row' }, raw, h('span', {}, '원자료(DATA/raw/)도 넣기 — 받은 쪽에서 자료를 다시 만들 수 있게. 넣지 않아도 지금 자료 회차로 이어 합니다')),
    h('label', { class: 'field-row' }, h('span', {}, '기록'), records),
    h('p', { class: 'muted' }, '바뀜 기록과 화면 상태는 넣지 않습니다(그 PC의 것). 파일은 프로젝트의 exports/ 에 생깁니다.'));
  if (!(await confirmDialog({ title: '묶어 보내기', body, confirm: '묶기', wide: true }))) return null;
  try {
    const res = await project.compute('bundle', { raw: raw.checked, records: records.value }, { quiet: true });
    const r = res.result;
    project.notify({ level: 'info', key: 'bundle', timeout: 0,
      text: h('span', {}, '묶었습니다 — ', h('b', { class: 'mono' }, r.path)),
      sub: [h('span', {}, `파일 ${r.files} · ${(r.bytes / 1024 / 1024).toFixed(1)}MB`), h('span', {}, `기록 ${r.records.length}`), h('span', {}, r.raw ? '원자료 넣음' : '원자료 넣지 않음')],
      actions: [['경로 복사', () => navigator.clipboard?.writeText(`${r.folder}\\${r.path.replace(/\//g, '\\')}`).catch(() => {})]] });
    return r.path;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}
