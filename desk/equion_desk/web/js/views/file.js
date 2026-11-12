// 파일 보기 — md 는 문서로, csv 는 표로, 그 밖의 글은 줄 번호와 함께. 파일이 바뀌면 다시 읽는다(계산은 하지 않는다).
// 정의 파일(블록 파일·equion.toml·자료 정의·시나리오·스크립트·노트·보고서)은 '고치기'로 글을 고친다(D3): 치는 동안 문법을 보고(블록 파일은 줄마다,
// TOML 은 문법과 설정), 저장하면 패키지가 바뀜 기록에 'Desk'로 남긴다. 쓰던 글은 탭과 함께 기억한다. 그 밖의 파일은 읽기만 한다.
// 쓰던 글은 고치기 시작한 파일 내용의 지문(base)과 함께 기억한다 — 고치는 동안이든 앱을 껐다 켠 뒤든 파일이 밖에서 바뀌었으면 알리고
// (무엇이 바뀌는지 차이로) 덮기 전에 묻는다. 서버도 저장할 때 그 지문을 견줘, 화면이 모르는 바뀜이 있으면 쓰지 않는다(409).

import { blobURL, papi, query } from '../api.js';
import { renderDoc } from '../md.js';
import { confirmDialog } from '../dialog.js';
import { bytes, clear, copyText, debounce, flash, h, icon } from '../util.js';

const MAX_ROWS = 2000;

/** csv 한 줄 나누기 — 따옴표 안의 쉼표를 지킨다 */
function splitCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false; } else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; } else if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; if (rows.length > MAX_ROWS) break; } else if (ch !== '\r') cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function sheet(text) {
  const rows = splitCsv(text);
  if (!rows.length) return h('div', { class: 'empty-state' }, '빈 파일입니다.');
  const [head, ...body] = rows;
  const shown = body.slice(0, MAX_ROWS);
  const isNum = (v) => v !== '' && !Number.isNaN(Number(v));
  const table = h('table', {}, h('thead', {}, h('tr', {}, head.map((c) => h('th', {}, c)))),
    h('tbody', {}, shown.map((r) => h('tr', {}, r.map((c, i) => h('td', { class: i && !isNum(c) && c !== '' ? 't' : '' },
      i && isNum(c) && c.includes('.') && c.length > 12 ? Number(c).toPrecision(8).replace(/\.?0+$/, '') : c))))));
  return h('div', {}, h('div', { class: 'sheet' }, table),
    body.length > MAX_ROWS ? h('div', { class: 'banner info', style: { 'margin-top': '10px' } }, `앞의 ${MAX_ROWS}줄만 보입니다(모두 ${body.length}줄 이상).`) : null);
}

function tint(line, ext) {
  // 아주 가벼운 색 입히기 — 주석, 구역 머리, 따옴표 글
  const out = h('span', { class: 'ln' });
  const comment = ext === 'json' ? -1 : (() => {
    let q = null;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (q) { if (ch === q) q = null; } else if (ch === '"' || ch === "'") q = ch; else if (ch === '#') return i;
    }
    return -1;
  })();
  const code = comment >= 0 ? line.slice(0, comment) : line;
  if ((ext === 'toml' && /^\s*\[.*\]\s*$/.test(code)) || (ext === 'eqs' && /^\s*$/.test(code) && /^#\s*#|^##/.test(line))) out.append(h('span', { class: 'h' }, code));
  else if (ext === 'eqs' && /^\s*(param|expect|run|py)\b/.test(code)) {
    const m = /^(\s*)(\w+)(.*)$/.exec(code);
    out.append(m[1], h('span', { class: 'k' }, m[2]), m[3]);
  } else {
    let rest = code;
    const re = /"[^"\n]*"|'[^'\n]*'/;
    while (rest) {
      const m = re.exec(rest);
      if (!m) { out.append(rest); break; }
      out.append(rest.slice(0, m.index), h('span', { class: 's' }, m[0]));
      rest = rest.slice(m.index + m[0].length);
    }
  }
  if (comment >= 0) out.append(h('span', { class: /^##/.test(line.trim()) ? 'h' : 'c' }, line.slice(comment)));
  return out;
}

/** 두 글의 줄 차이 — [{op: ' ' | '-' | '+', line}]. 앞뒤의 같은 줄을 떼고 가운데만 견준다(정의 파일은 작다) */
function lineDiff(a, b) {
  const split = (t) => t.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
  const x = split(a), y = split(b);
  let s = 0;
  while (s < x.length && s < y.length && x[s] === y[s]) s++;
  let e = 0;
  while (e < x.length - s && e < y.length - s && x[x.length - 1 - e] === y[y.length - 1 - e]) e++;
  const xs = x.slice(s, x.length - e), ys = y.slice(s, y.length - e);
  const mid = [];
  if (xs.length * ys.length > 4e6) {              // 아주 크게 다르면 통째로 — 빠르게
    for (const line of xs) mid.push({ op: '-', line });
    for (const line of ys) mid.push({ op: '+', line });
  } else {
    const n = xs.length, m = ys.length;
    const L = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = xs[i] === ys[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (xs[i] === ys[j]) { mid.push({ op: ' ', line: xs[i] }); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) mid.push({ op: '-', line: xs[i++] }); else mid.push({ op: '+', line: ys[j++] });
    }
    while (i < n) mid.push({ op: '-', line: xs[i++] });
    while (j < m) mid.push({ op: '+', line: ys[j++] });
  }
  return [...x.slice(0, s).map((line) => ({ op: ' ', line })), ...mid, ...x.slice(x.length - e).map((line) => ({ op: ' ', line }))];
}

/** 지금 파일 → 쓰던 글의 차이(저장하면 이렇게 바뀐다) — 바뀐 줄과 앞뒤 두 줄만, 나머지는 '같은 줄 n' 으로 접는다 */
function diffView(now, mine) {
  const rows = lineDiff(now, mine);
  if (!rows.some((r) => r.op !== ' ')) return h('div', { class: 'muted' }, '지금 파일과 쓰던 글이 같습니다.');
  const keep = rows.map(() => false);
  rows.forEach((r, i) => { if (r.op !== ' ') for (let k = Math.max(0, i - 2); k <= Math.min(rows.length - 1, i + 2); k++) keep[k] = true; });
  const out = [];
  let skipped = 0;
  const fold = () => { if (skipped) out.push(h('span', { class: 'dl hunk' }, `… 같은 줄 ${skipped}`)); skipped = 0; };
  rows.forEach((r, i) => {
    if (!keep[i]) { skipped++; return; }
    fold();
    out.push(h('span', { class: `dl ${r.op === '+' ? 'add' : r.op === '-' ? 'del' : ''}`.trim() }, `${r.op} ${r.line}`));
  });
  fold();
  return h('div', { class: 'edit-diff' }, h('div', { class: 'edit-diff-key' }, h('span', { class: 'del' }, '− 지금 파일'), h('span', { class: 'add' }, '+ 쓰던 글'),
    h('span', { class: 'muted' }, '저장하면 지금 파일이 쓰던 글이 됩니다')), h('div', { class: 'diff' }, out));
}

function codeBlock(text, ext) {
  const lines = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
  return h('pre', { class: 'code' }, lines.map((line) => tint(line, ext)));
}

/** 화면에서 고칠 수 있는 파일인가 — 바뀜 기록이 지켜보는 정의 파일(작업 프로세스가 한 번 더 가린다) */
function editable(project, path) {
  if (/^(equion\.toml|EQUATIONS\/[^/]+\.(txt|toml)|DATA\/(series\.toml|derived\.txt)|(ASSUMPTIONS|ADDFACTORS)\/[^/]+\.(csv|toml)|(SCENARIOS|VIEWS)\/[^/]+\.toml|(notes|reports)\/[^/]+\.md|FLOWS\/[^/]+\.eqs)$/.test(path)) return true;
  return (project.overview?.blocks || []).some((b) => b.file === path);
}

export function fileView(project, desc) {
  const path = desc.path;
  const name = path.split('/').pop();
  const ext = (/\.([^.\/]+)$/.exec(name)?.[1] || '').toLowerCase();
  const dir = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
  const el = h('div', { class: `view ${ext === 'csv' ? 'wide' : ''}`.trim() });
  let loaded = false;
  let mtime = 0;
  let text = '';                                  // 파일의 지금 내용
  let draft = typeof desc.draft === 'string' ? desc.draft : null;       // 고치는 중인 글(없으면 보기만)
  let restored = draft != null;                   // 지난번에 쓰던 글을 되살렸다(앱을 껐다 켬)
  let baseHash = restored && typeof desc.base === 'string' ? desc.base : null;     // 고치기 시작한 파일 내용의 지문 — 쓰던 글과 함께 기억한다
  let baseText = null;                            // 고치기 시작한 내용(되살린 글은 모른다)
  let fileHash = null;                            // 지금 파일의 지문(마지막으로 읽은 것)
  let showDiff = false;
  let wantEdit = !!desc.edit || draft != null;
  let problems = [];
  let area = null;
  const noteBox = h('div', { class: 'edit-note' });
  const view = { key: `file:${path}`, type: 'file', title: name, icon: ext === 'md' ? 'doc' : ext === 'csv' ? 'table' : 'file', el };

  let tries = 0;
  const check = debounce(async () => {
    if (draft == null || !['txt', 'toml'].includes(ext)) return;
    const asked = draft;
    try {
      const res = await project.post('text/check', { path, text: asked });
      if (draft !== asked) return;
      if (res.busy) { if (tries++ < 8) setTimeout(check, 800); return; }       // 계산이 도는 중 — 조금 뒤에 다시 본다(치지 않아도)
      problems = res.problems;
      tries = 0;
    } catch { return; }               // 검사를 못 해도 저장은 할 수 있다
    drawNote();
  }, 350);

  /** 고치기 시작한 뒤(또는 되살린 글을 쓰던 때 뒤) 파일이 밖에서 바뀌었는가 — 쓰던 글과 이미 같으면 덮을 것이 없다 */
  const moved = () => draft != null && fileHash != null && baseHash !== fileHash && draft !== text;
  /** 사람이 고친 것이 있는가 — 고치기만 누르고 치지 않았으면 기억하지도 묻지도 않는다 */
  const edited = () => draft != null && draft !== (baseText ?? text);

  /** 고치기를 그만둔다 — 화면 상태를 바로 적는다(곧 창을 닫아도 버린 글이 되살아나지 않게) */
  function stop() {
    draft = null; wantEdit = false; problems = []; baseHash = null; baseText = null; restored = false; showDiff = false; mtime = 0;
    project.persist();
    load();
  }

  function drawNote() {
    clear(noteBox);
    if (draft == null) return;
    const dirty = draft !== text;
    if (moved()) {
      const why = !restored ? '고치는 동안 파일이 밖(Claude · 편집기 · 명령)에서 바뀌었습니다 — 저장하면 그 바뀜을 덮습니다.'
        : baseHash ? '앱을 닫았던 동안 파일이 밖에서 바뀌었습니다 — 저장하면 그 바뀜을 덮습니다.'
          : '앱을 닫기 전에 쓰던 글입니다 — 그 뒤 파일이 바뀌었는지 몰라 저장할 때 묻습니다.';
      noteBox.append(h('div', { class: 'banner warn', 'data-note': 'moved' }, icon('alert'), h('div', { class: 'grow' }, why),
        h('div', { class: 'banner-acts' },
          h('button', { class: 'btn small', type: 'button', 'data-act': 'moved-diff', 'aria-expanded': String(showDiff), title: '지금 파일과 쓰던 글의 차이 — 저장하면 무엇이 바뀌는지', onclick: () => { showDiff = !showDiff; drawNote(); } }, showDiff ? '차이 접기' : '차이 보기'),
          h('button', { class: 'btn small', type: 'button', 'data-act': 'reload', title: '쓰던 글을 버리고 지금 파일을 다시 읽는다', onclick: stop }, '다시 읽기(쓰던 글 버림)'))));
      if (showDiff) noteBox.append(diffView(text, draft));
    }
    if (problems.length) {
      noteBox.append(h('div', { class: 'edit-problems' }, h('b', {}, `읽을 수 없는 곳 ${problems.length}`), problems.slice(0, 8).map((x) => h('button', {
        class: 'problem', type: 'button', title: '그 줄로', onclick: () => gotoLine(x.line),
      }, x.line ? h('span', { class: 'mono' }, `${x.line}줄`) : null, h('span', {}, x.text)))));
    } else if (['txt', 'toml'].includes(ext)) {
      noteBox.append(h('div', { class: 'eq-status ok' }, icon('check'), h('span', {}, dirty ? '읽을 수 있습니다 — 아직 저장하지 않았습니다.' : '바뀐 것이 없습니다.')));
    }
  }

  function gotoLine(n) {
    if (!area || !n) return;
    const lines = area.value.split('\n');
    const start = lines.slice(0, n - 1).reduce((a, l) => a + l.length + 1, 0);
    area.focus();
    area.setSelectionRange(start, start + (lines[n - 1] || '').length);
    const lh = parseFloat(getComputedStyle(area).lineHeight) || 20;
    const pane = el.parentElement;
    if (pane) pane.scrollTop = Math.max(0, area.offsetTop + (n - 4) * lh);
  }

  async function saveDraft() {
    if (draft == null) return;
    if (draft === text) { flash(baseHash !== fileHash ? '바뀐 것이 없습니다 — 파일이 이미 쓰던 글과 같습니다' : '바뀐 것이 없습니다'); return; }
    const expect = fileHash;                    // 사람이 본(덮겠다고 고른) 내용 — 묻는 동안 또 바뀌면 서버가 쓰지 않는다
    if (moved()) {
      const body = h('div', { class: 'adopt' }, h('p', {}, restored ? '이 글을 쓴 뒤(앱을 닫았던 동안) 파일이 밖(Claude · 편집기 · 다른 명령)에서 바뀌었습니다. '
        : '고치는 동안 이 파일이 밖(Claude · 편집기 · 다른 명령)에서 바뀌었습니다. ', '저장하면 아래처럼 지금 파일을 쓰던 글로 바꿉니다 — 붉은 줄(밖에서 더하거나 고친 것도)이 사라집니다. '
        + '덮인 내용은 바뀜 기록에 남아 거기서 되돌릴 수 있습니다.'), diffView(text, draft), h('p', { class: 'muted' }, '그 바뀜을 살리려면 취소하고 ‘다시 읽기’로 새 내용에서 다시 고치세요.'));
      if (!(await confirmDialog({ title: '밖에서 바뀐 파일을 덮을까요', body, confirm: '덮어 저장', tone: 'danger', wide: true }))) return;
    }
    if (problems.length) {
      const body = h('div', { class: 'adopt' }, h('p', {}, '읽을 수 없는 곳이 있습니다. 이대로 저장하면 이 파일에 기대는 계산이 멈출 수 있습니다.'),
        h('div', { class: 'diff' }, problems.slice(0, 8).map((x) => h('span', { class: 'dl del' }, `${x.line ? `${x.line}줄  ` : ''}${x.text}`))));
      if (!(await confirmDialog({ title: '문제가 있는 채로 저장할까요', body, confirm: '그래도 저장', tone: '', wide: true }))) return;
    }
    try {
      // 덮을 내용의 지문을 함께 보낸다 — 그 사이 파일이 또 바뀌었으면 서버가 쓰지 않는다(409)
      const res = await project.compute('text/write', { path, text: draft, ...(expect ? { expect } : {}) }, { quiet: true });
      const change = res.result.change;
      flash(change ? `저장했습니다 — 바뀜 기록 ${change}` : '바뀐 것이 없습니다');
      draft = null; wantEdit = false; problems = []; baseHash = null; baseText = null; restored = false; showDiff = false; mtime = 0;
      project.persist();
      await load();
    } catch (err) {
      if (err.kind === 'conflict') {            // 화면이 아직 모르는 바뀜 — 새 내용을 읽고 알린다(쓰던 글은 그대로)
        flash('저장하지 않았습니다 — 그 사이 파일이 밖에서 바뀌었습니다');
        await load({ force: true });
        return;
      }
      if (err.kind !== 'busy') { clear(noteBox).append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message))); }
    }
  }

  function editor() {
    area = h('textarea', { class: 'edit-area', spellcheck: 'false', autocomplete: 'off', wrap: ext === 'md' ? 'soft' : 'off', 'aria-label': `${name} 고치기` });
    area.value = draft;
    const fit = () => { area.style.height = 'auto'; area.style.height = `${Math.max(220, area.scrollHeight + 4)}px`; };
    area.addEventListener('input', () => { draft = area.value; fit(); drawNote(); check(); project.saveView(); });
    area.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveDraft(); }
      else if (e.key === 'Tab' && !e.shiftKey && !e.ctrlKey) { e.preventDefault(); area.setRangeText('    ', area.selectionStart, area.selectionEnd, 'end'); area.dispatchEvent(new Event('input')); }
    });
    requestAnimationFrame(fit);
    return h('div', { class: 'edit-box' }, area);
  }

  async function load({ force = false } = {}) {
    loaded = true;
    let file;
    try {
      file = await project.get(`file${query({ path })}`);
    } catch (err) {
      clear(el);
      el.append(h('div', { class: 'view-head' }, h('div', {}, h('h1', {}, name), h('div', { class: 'sub mono' }, path))),
        h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message)));
      return;
    }
    if (file.mtime === mtime && (file.hash ?? null) === fileHash && !force) return;
    const first = mtime === 0;
    mtime = file.mtime;
    fileHash = file.hash ?? null;
    if (draft != null && !first) {                  // 고치는 중에는 화면을 갈아엎지 않는다 — 밖에서 바뀌었다고만 알린다(지문으로 견준다)
      if (file.text !== text || force) { text = file.text; drawNote(); }
      return;
    }
    text = file.kind === 'text' ? file.text : '';
    const canEdit = file.kind === 'text' && !file.truncated && editable(project, path);
    if (wantEdit && canEdit && draft == null) { draft = text; baseText = text; baseHash = fileHash; restored = false; }
    if (!canEdit) { draft = null; wantEdit = false; }
    const top = el.parentElement?.scrollTop || 0;
    clear(el);
    const editing = draft != null;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, name, editing ? h('span', { class: 'tag accent' }, '고치는 중') : null), h('div', { class: 'sub' }, h('span', { class: 'mono' }, path), h('span', {}, bytes(file.size)),
        file.encoding && file.encoding !== 'utf-8-sig' ? h('span', { class: 'tag warn' }, file.encoding) : null)),
      editing ? h('div', { class: 'tools' },
        h('button', { class: 'btn', type: 'button', 'data-act': 'stop', title: '고치기를 그만둔다 — 쓰던 글은 버린다', onclick: stop }, '그만두기'),
        h('button', { class: 'btn primary', type: 'button', 'data-act': 'save', title: '저장한다(Ctrl+S) — 바뀜 기록에 남고, 거기서 되돌릴 수 있다', onclick: saveDraft }, icon('check'), '저장'))
        : h('div', { class: 'tools' },
          canEdit ? h('button', { class: 'btn', type: 'button', 'data-act': 'edit', title: '이 정의 파일을 화면에서 고친다 — 저장하면 바뀜 기록에 남는다', onclick: () => { wantEdit = true; mtime = 0; load(); } }, icon('doc'), '고치기') : null,
          h('button', { class: 'btn quiet', type: 'button', onclick: () => copyText(path, '경로를 복사했습니다') }, icon('copy'), '경로'),
          h('button', { class: 'btn quiet', type: 'button', title: '터미널에 경로를 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(path) }, icon('send'), '터미널로'))));
    if (file.truncated) el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '큰 파일이라 앞부분만 보입니다.')));
    if (editing) {
      el.append(noteBox, editor());
      drawNote();
      check();
      area.focus();
    } else if (file.kind === 'image') {
      const img = h('img', { alt: name, style: { 'max-width': '100%' } });
      blobURL(papi(project.id, `raw${query({ path })}`)).then((url) => { img.src = url; }).catch(() => {});
      el.append(img);
    } else if (file.kind !== 'text') {
      el.append(h('div', { class: 'empty-state' }, '글 파일이 아니어서 보이지 않습니다.'));
    } else if (ext === 'md') {
      const doc = h('div', {});
      el.append(doc);
      await renderDoc(doc, file.text, { pid: project.id, dir, openFile: (p) => project.openTab({ type: 'file', path: p }) });
    } else if (ext === 'csv') el.append(sheet(file.text));
    else el.append(codeBlock(file.text, ext));
    if (el.parentElement && !editing) el.parentElement.scrollTop = top;
  }

  return Object.assign(view, {
    // 쓰던 글은 고치기 시작한 내용의 지문과 함께 — 다시 열 때 그 사이 파일이 밖에서 바뀌었는지 견준다
    desc: () => ({ type: 'file', path, ...(edited() ? { draft, ...(baseHash ? { base: baseHash } : {}) } : {}) }),
    /** 탭을 닫기 전에 묻는 글 — 저장하지 않은 고침이 있을 때만 */
    unsaved: () => {
      if (!edited() || draft === text) return null;
      const a = text.split('\n'), b = draft.split('\n');
      let i = 0;
      while (i < a.length && i < b.length && a[i] === b[i]) i++;
      return `${path} 에 저장하지 않은 고침이 있습니다(${i + 1}줄부터) — 닫으면 그 고침을 버립니다.`;
    },
    show() { if (!loaded) load(); },
    open(next) { if (next.edit && draft == null) { wantEdit = true; mtime = 0; if (loaded) load(); } },
    event(e) {
      // 파일이 바뀌었을 수 있다 — 보이는 탭이면 다시 읽는다(고친 시각이 같으면 그대로 둔다)
      if ((e.type === 'defs' || e.type === 'tree' || e.type === 'record') && loaded && el.isConnected && !el.parentElement.hidden) load();
      else if (e.type === 'defs' || e.type === 'tree') loaded = false;
    },
    dispose() {},
  });
}
