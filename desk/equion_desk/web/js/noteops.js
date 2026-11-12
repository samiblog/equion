// 노트에 담기 (D57) — 기록 하나(그 명령과 카드)나 명령 줄들(후보 묶음)을 노트 끝의 블록 하나로. `equion note add`와 같다.
// 어느 노트에 담을지 고르고(있는 노트 · 새 노트), 무엇이 들어가는지 보이고 나서 쓴다. 바뀜 기록에 남아 되돌릴 수 있다.

import { confirmDialog } from './dialog.js';
import { flash, h } from './util.js';

/** record: 기록 이름(an:… · est:… · hs:… · sim:…) 또는 lines: 명령 줄들. suggest: 새 노트의 경로 제안. 돌려주는 것: 노트 경로 또는 null */
export async function addToNote(project, { record = null, lines = null, title = '', suggest = '' } = {}) {
  let notes = [];
  try { notes = (await project.get('notes')).notes.filter((n) => !n.error).map((n) => n.path); } catch { /* 목록 없이도 새 노트는 된다 */ }
  const NEW = '__new__';
  const pick = h('select', { class: 'mini-select', 'aria-label': '노트' }, notes.map((n) => h('option', { value: n }, n)), h('option', { value: NEW }, '새 노트…'));
  const path = h('input', { class: 'mini-input wide', type: 'text', value: suggest || 'notes/새노트.md', spellcheck: 'false', 'aria-label': '새 노트 경로' });
  const head = h('input', { class: 'mini-input wide plain', type: 'text', value: title, placeholder: '제목(새 노트)', 'aria-label': '제목' });
  const newRow = h('div', {}, h('label', { class: 'field-row' }, h('span', {}, '경로'), path), h('label', { class: 'field-row' }, h('span', {}, '제목'), head));
  if (suggest && notes.includes(suggest)) pick.value = suggest;
  else if (suggest || !notes.length) pick.value = NEW;
  const sync = () => { newRow.hidden = pick.value !== NEW; };
  pick.addEventListener('change', sync);
  sync();
  const what = record
    ? h('p', {}, h('b', { class: 'mono' }, record), ' 를 만든 명령과 그 결과(카드)를 노트 끝의 블록 하나로 담습니다 — 다음 회차에 그 블록을 다시 실행하면 새 기록으로 바뀝니다.')
    : h('div', {}, h('p', {}, `명령 ${lines.length}줄을 노트 끝의 블록 하나로 담습니다 — 실행은 노트에서(블록의 ▶ 또는 노트 전체 실행).`),
      h('div', { class: 'diff' }, lines.slice(0, 12).map((l) => h('span', { class: 'dl add' }, `+ ${l}`)), lines.length > 12 ? h('span', { class: 'dl' }, `… ${lines.length - 12}줄 더`) : null));
  const body = h('div', { class: 'adopt define-form' }, what, h('label', { class: 'field-row' }, h('span', {}, '노트'), pick), newRow,
    h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
  if (!(await confirmDialog({ title: '노트에 담기', body, confirm: '담기', wide: true }))) return null;
  let note = pick.value === NEW ? path.value.trim() : pick.value;
  if (!note) return null;
  if (!/\.md$/i.test(note)) note += '.md';
  if (!note.includes('/')) note = `notes/${note}`;
  try {
    const res = await project.compute('note/add', { note, ...(record ? { record } : { lines }), ...(pick.value === NEW && head.value.trim() ? { title: head.value.trim() } : {}) }, { quiet: true });
    flash(`${res.result.file} — 블록 ${res.result.block} 을 담았습니다`);
    project.side?.loadNotes?.();
    project.openTab({ type: 'note', path: res.result.file });
    return res.result.file;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}
