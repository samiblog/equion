// 파일 보기(읽기만) — md 는 문서로, csv 는 표로, 그 밖의 글은 줄 번호와 함께. 파일이 바뀌면 다시 읽는다(계산은 하지 않는다).
// 고치는 것은 터미널·편집기·Lectern 에서 한다. 화면에서 고치기는 D2 부터.

import { blobURL, papi, query } from '../api.js';
import { renderDoc } from '../md.js';
import { bytes, clear, copyText, h, icon } from '../util.js';

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

function codeBlock(text, ext) {
  const lines = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
  return h('pre', { class: 'code' }, lines.map((line) => tint(line, ext)));
}

export function fileView(project, desc) {
  const path = desc.path;
  const name = path.split('/').pop();
  const ext = (/\.([^.\/]+)$/.exec(name)?.[1] || '').toLowerCase();
  const dir = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
  const el = h('div', { class: `view ${ext === 'csv' ? 'wide' : ''}`.trim() });
  let loaded = false;
  let mtime = 0;

  async function load() {
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
    if (file.mtime === mtime) return;
    mtime = file.mtime;
    const top = el.parentElement?.scrollTop || 0;
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, name), h('div', { class: 'sub' }, h('span', { class: 'mono' }, path), h('span', {}, bytes(file.size)),
        file.encoding && file.encoding !== 'utf-8-sig' ? h('span', { class: 'tag warn' }, file.encoding) : null)),
      h('div', { class: 'tools' },
        h('button', { class: 'btn quiet', type: 'button', onclick: () => copyText(path, '경로를 복사했습니다') }, icon('copy'), '경로'),
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 경로를 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(path) }, icon('send'), '터미널로'))));
    if (file.truncated) el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '큰 파일이라 앞부분만 보입니다.')));
    if (file.kind === 'image') {
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
    if (el.parentElement) el.parentElement.scrollTop = top;
  }

  return {
    key: `file:${path}`, type: 'file', title: name, icon: ext === 'md' ? 'doc' : ext === 'csv' ? 'table' : 'file', el,
    desc: () => ({ type: 'file', path }),
    show() { if (!loaded) load(); },
    event(e) {
      // 파일이 바뀌었을 수 있다 — 보이는 탭이면 다시 읽는다(고친 시각이 같으면 그대로 둔다)
      if ((e.type === 'defs' || e.type === 'tree' || e.type === 'record') && loaded && el.isConnected && !el.parentElement.hidden) load();
      else if (e.type === 'defs' || e.type === 'tree') loaded = false;
    },
    dispose() {},
  };
}
