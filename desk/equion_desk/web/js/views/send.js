// 보고서로 보내기 · 엑셀로 — 어느 결과 화면에서나 같은 대화상자를 쓴다(결과 카드·전망 작업대).
//
// 보고서는 사람의 글이다. 보내는 것은 기록의 표(와 차트)를 고른 모양으로 한 구역 — 구역에는 어느 기록에서 왔는지가 보이지 않게 적혀,
// 나중에 '보고서 검사'가 더 새 기록·낡음·손으로 고친 곳을 알린다. 기록은 고치지 않는다. 엑셀은 값·값의 종류·출처 시트를 exports/ 에 쓴다.

import { confirmDialog } from '../dialog.js';
import { flash, h } from '../util.js';

const SHOWS = [['level', '수준'], ['qoq', '전기비(%)'], ['yoy', '전년동기비(%)'], ['diff', '기준선 대비 차이']];

/** 보고서로 보내기. defaults: {rows(시리즈들), show, annual, title}. 보낸 뒤 그 보고서 탭을 연다 */
export async function sendToReport(project, record, defaults = {}) {
  let list = [];
  try { list = (await project.get('reports')).reports; } catch { /* 보고서 폴더가 아직 없다 */ }
  const kind = String(record).split(':')[0];
  const fresh = '__new__';
  const report = h('select', { class: 'mini-select wide', 'aria-label': '보고서' }, list.map((r) => h('option', { value: r.name }, `${r.name}${r.title ? ` — ${r.title}` : ''}`)), h('option', { value: fresh }, '새 보고서…'));
  const newName = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: forecast_2026_12', spellcheck: 'false', 'aria-label': '새 보고서 이름' });
  const newTitle = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '보고서 제목', 'aria-label': '새 보고서 제목' });
  const newRow = h('div', { class: 'new-report' }, h('label', { class: 'field-row' }, h('span', {}, '이름'), newName), h('label', { class: 'field-row' }, h('span', {}, '제목'), newTitle));
  const sync = () => { newRow.hidden = report.value !== fresh; };
  report.addEventListener('change', sync);
  if (!list.length) report.value = fresh;
  sync();
  const rows = h('input', { class: 'mini-input wide', type: 'text', value: (defaults.rows || []).join(', '), placeholder: '모두 — 또는 Y, CN, P', spellcheck: 'false', 'aria-label': '행(시리즈)' });
  const show = h('select', { class: 'mini-select' }, SHOWS.filter(([v]) => v !== 'diff' || kind === 'sim').map(([v, label]) => h('option', { value: v }, label)));
  show.value = defaults.show && [...show.options].some((o) => o.value === defaults.show) ? defaults.show : 'level';
  const annual = h('input', { type: 'checkbox' });
  annual.checked = !!defaults.annual;
  const chart = h('input', { type: 'checkbox' });
  const digits = h('input', { class: 'mini-input num', type: 'number', min: '0', max: '8', placeholder: '자동', 'aria-label': '소수점 자리' });
  const title = h('input', { class: 'mini-input wide plain', type: 'text', value: defaults.title || '', placeholder: '표 제목(번호는 저절로 붙습니다)', 'aria-label': '표 제목' });
  const under = h('select', { class: 'mini-select wide', 'aria-label': '보낼 곳' });
  const places = () => {            // 고른 보고서의 작은 제목들 — 그 제목 아래 끝에 넣는다
    const heads = list.find((r) => r.name === report.value)?.headings || [];
    under.replaceChildren(h('option', { value: '' }, '보고서 끝에'), ...heads.map((x) => h('option', { value: x }, `${x.replace(/^#+\s*/, '')} 아래에`)));
    underRow.hidden = !heads.length;
  };
  const underRow = h('label', { class: 'field-row' }, h('span', {}, '보낼 곳'), under);
  report.addEventListener('change', places);
  places();
  const series = kind === 'sim' || kind === 'hs';
  const body = h('div', { class: 'adopt define-form' },
    h('p', {}, h('b', { class: 'mono' }, record), ' 의 표를 보고서의 한 구역으로 보냅니다. 구역에는 어느 기록에서 왔는지가 적혀, 나중에 더 새 기록으로 바꿀 수 있습니다.'),
    h('label', { class: 'field-row' }, h('span', {}, '보고서'), report), newRow,
    series ? h('label', { class: 'field-row' }, h('span', {}, '행(시리즈)'), rows) : null,
    series ? h('div', { class: 'field-row' }, h('span', {}, '모양'), h('div', { class: 'inline-opts' }, show, h('label', { class: 'check-row' }, annual, h('span', {}, '연간으로')), h('label', { class: 'check-row' }, h('span', {}, '소수점'), digits))) : null,
    h('label', { class: 'field-row' }, h('span', {}, '표 제목'), title),
    underRow,
    h('label', { class: 'check-row' }, chart, h('span', {}, '차트도 함께(차트 자료는 보고서 옆 폴더로 복사합니다)')));
  if (!(await confirmDialog({ title: '보고서로 보내기', body, confirm: '보내기', wide: true }))) return null;
  try {
    let name = report.value;
    if (name === fresh) {
      name = newName.value.trim();
      await project.compute('report/new', { name, title: newTitle.value.trim() }, { quiet: true });
    }
    const res = await project.compute('report/add', {
      report: name, record, rows: rows.value.split(/[\s,]+/).filter(Boolean), show: show.value, annual: annual.checked, chart: chart.checked,
      ...(digits.value !== '' ? { digits: Number(digits.value) } : {}), title: title.value.trim(), under: name === report.value ? under.value : '',
    }, { quiet: true });
    flash(`${res.result.report} 에 보냈습니다`);
    project.openTab({ type: 'reports', report: name });
    return res.result;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}

/** 엑셀로 — 기록들의 값·값의 종류·출처를 exports/<이름>.xlsx 로 */
export async function exportXlsx(project, records, suggested = '') {
  const name = h('input', { class: 'mini-input wide', type: 'text', value: suggested || String(records[0]).split(':').pop().replace(/[^A-Za-z0-9_-]+/g, '_'), spellcheck: 'false', 'aria-label': '파일 이름' });
  const body = h('div', { class: 'adopt define-form' },
    h('p', {}, `기록 ${records.length}개를 엑셀 한 권으로 냅니다 — 값 · 값의 종류(실측·해·가정·채움) · 출처(기록·명령·자료 회차) 시트. 기록은 그대로입니다.`),
    h('div', { class: 'diff' }, records.map((r) => h('span', { class: 'dl' }, r))),
    h('label', { class: 'field-row' }, h('span', {}, '파일 이름'), name), h('p', { class: 'muted' }, '프로젝트의 exports/ 폴더에 .xlsx 로 씁니다.'));
  if (!(await confirmDialog({ title: '엑셀로 내보내기', body, confirm: '내보내기', wide: true }))) return null;
  try {
    const res = await project.compute('export', { records, name: name.value.trim() }, { quiet: true });
    project.notify({ level: 'info', text: h('span', {}, h('b', {}, res.result.path), ` 를 썼습니다 — 시트 ${res.result.sheets?.length ?? ''}개.`), sub: [h('span', { class: 'mono' }, res.result.command)], timeout: 12000 });
    return res.result;
  } catch (err) {
    if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    return null;
  }
}
