// 아이콘 — 16×16 선 그림(굵기 1.5, 끝은 둥글게). 이 앱을 위해 새로 그린 것이다(다른 프로그램의 아이콘을 옮기지 않는다 — D13).
// 값은 <svg> 안에 들어갈 글자다. 색은 currentColor.

export const ICONS = {
  plus: '<path d="M8 3.5v9M3.5 8h9"/>',
  x: '<path d="M4 4l8 8M12 4l-8 8"/>',
  chevron: '<path d="M6 3.5L10.5 8 6 12.5"/>',
  check: '<path d="M3.2 8.4l3.1 3.1 6.5-7"/>',
  home: '<path d="M2.5 7.5L8 2.8l5.5 4.7"/><path d="M4 6.6v6.6h8V6.6"/><path d="M6.8 13.2V9.6h2.4v3.6"/>',
  folder: '<path d="M2 4.6c0-.7.5-1.2 1.2-1.2h3l1.5 1.7h5.1c.7 0 1.2.5 1.2 1.2v5.5c0 .7-.5 1.2-1.2 1.2H3.2c-.7 0-1.2-.5-1.2-1.2z"/>',
  file: '<path d="M4 2.5h5l3 3v8H4z"/><path d="M9 2.5v3h3"/>',
  doc: '<path d="M4 2.5h5l3 3v8H4z"/><path d="M9 2.5v3h3"/><path d="M6 8.5h4M6 10.8h3"/>',
  table: '<rect x="2.5" y="3" width="11" height="10" rx="1.2"/><path d="M2.5 6.4h11M2.5 9.7h11M6.6 6.4V13"/>',
  code: '<path d="M5.6 5L2.8 8l2.8 3M10.4 5l2.8 3-2.8 3"/>',
  equation: '<path d="M3 5.2h10M3 8h7M3 10.8h10"/>',
  cube: '<path d="M8 2.2l5 2.8v6L8 13.8 3 11V5z"/><path d="M3 5l5 2.8L13 5M8 7.8v6"/>',
  layers: '<path d="M8 2.6l5.6 3L8 8.6 2.4 5.6z"/><path d="M2.4 8.4L8 11.4l5.6-3"/><path d="M2.4 11L8 14l5.6-3" opacity=".55"/>',
  chart: '<path d="M2.5 13.5h11"/><path d="M3.2 10.2l3-3.4 2.5 2 4-4.8"/>',
  rewind: '<path d="M3 8a5 5 0 1 0 1.6-3.7"/><path d="M3 3v3.2h3.2"/><path d="M8 5.6V8l1.8 1.2"/>',
  forward: '<path d="M2.5 11.5c1.6-3.6 4-5.4 7.6-5.4"/><path d="M8.3 3.5l2.7 2.6-2.7 2.6"/><path d="M13.5 3v10" opacity=".55"/>',
  play: '<path d="M5 3.4l7 4.6-7 4.6z"/>',
  stop: '<rect x="4" y="4" width="8" height="8" rx="1.2"/>',
  refresh: '<path d="M13 8a5 5 0 1 1-1.5-3.6"/><path d="M13 2.8V5.6h-2.8"/>',
  copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.3"/><path d="M10.5 5.5V3.8c0-.7-.6-1.3-1.3-1.3H3.8c-.7 0-1.3.6-1.3 1.3v5.4c0 .7.6 1.3 1.3 1.3h1.7"/>',
  send: '<rect x="2" y="3" width="12" height="10" rx="1.4"/><path d="M4.8 6.6L7 8.3 4.8 10M8.4 10.2h2.8"/>',
  terminal: '<rect x="2" y="3" width="12" height="10" rx="1.4"/><path d="M4.8 6.6L7 8.3 4.8 10M8.4 10.2h2.8"/>',
  sidebar: '<rect x="2" y="3" width="12" height="10" rx="1.4"/><path d="M6.2 3v10"/>',
  gear: '<circle cx="8" cy="8" r="2.1"/><path d="M8 1.9v1.7M8 12.4v1.7M1.9 8h1.7M12.4 8h1.7M3.7 3.7l1.2 1.2M11.1 11.1l1.2 1.2M12.3 3.7l-1.2 1.2M4.9 11.1l-1.2 1.2"/>',
  history: '<circle cx="8" cy="8" r="5.5"/><path d="M8 4.8V8l2.2 1.5"/>',
  diff: '<path d="M5 2.8v6.4M1.8 6h6.4"/><path d="M8.2 12.4h6"/><path d="M12.6 2.5L3.4 13.5" opacity=".5"/>',
  list: '<path d="M5.5 4.2h8M5.5 8h8M5.5 11.8h8"/><path d="M2.5 4.2h.01M2.5 8h.01M2.5 11.8h.01" stroke-width="2"/>',
  alert: '<path d="M8 2.4l6 10.6H2z"/><path d="M8 6.6v3M8 11.3h.01"/>',
  info: '<circle cx="8" cy="8" r="5.6"/><path d="M8 7.4v3.4M8 5.2h.01"/>',
  spark: '<path d="M8 1.8l1.5 4.7L14.2 8l-4.7 1.5L8 14.2 6.5 9.5 1.8 8l4.7-1.5z" fill="currentColor" stroke="none"/>',
  sun: '<circle cx="8" cy="8" r="2.8"/><path d="M8 1.6v1.6M8 12.8v1.6M1.6 8h1.6M12.8 8h1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M12.5 3.5l-1.1 1.1M4.6 11.4l-1.1 1.1"/>',
  moon: '<path d="M13 9.6A5.6 5.6 0 0 1 6.4 3 5.6 5.6 0 1 0 13 9.6z"/>',
  auto: '<rect x="2" y="3" width="12" height="8.4" rx="1.3"/><path d="M5.8 13.6h4.4M8 11.4v2.2"/>',
  minus: '<path d="M3.5 8h9"/>',
  data: '<ellipse cx="8" cy="4.2" rx="5" ry="1.9"/><path d="M3 4.2v7.6c0 1 2.2 1.9 5 1.9s5-.9 5-1.9V4.2"/><path d="M3 8c0 1 2.2 1.9 5 1.9s5-.9 5-1.9"/>',
  flask: '<path d="M6.2 2.5h3.6M6.8 2.5v3.6L3.4 12c-.5.9.1 1.6 1 1.6h7.2c.9 0 1.5-.7 1-1.6L9.2 6.1V2.5"/><path d="M5 10h6"/>',
  arrow: '<path d="M3 8h9.5M9 4.5L12.5 8 9 11.5"/>',
  inbox: '<path d="M2.5 9.2l1.6-5.4c.1-.4.5-.7 1-.7h5.8c.5 0 .9.3 1 .7l1.6 5.4v2.6c0 .6-.5 1.1-1.1 1.1H3.6c-.6 0-1.1-.5-1.1-1.1z"/><path d="M2.5 9.2h3.2l.8 1.5h3l.8-1.5h3.2"/>',
  search: '<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2l3.3 3.3"/>',
  pin: '<path d="M9.6 2.4l4 4-2.2.7-2.3 2.3.2 2.8-1.2 1.2-2.8-2.8L2.6 13.3l-.1-.1 2.7-2.7-2.8-2.8 1.2-1.2 2.8.2 2.3-2.3z"/>',
  external: '<path d="M9 3h4v4M13 3L7.6 8.4"/><path d="M11.5 9.5v2.8c0 .4-.3.7-.7.7H3.7c-.4 0-.7-.3-.7-.7V5.2c0-.4.3-.7.7-.7h2.8"/>',
};

/** 앱의 얼굴 — 세 가로줄(항등 '≡'이자 E)과 점 하나. 아이콘 파일(assets/equion-desk.ico)과 같은 그림이다(desk/build/icon.py). */
export const LOGO = `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#16918a"/><stop offset="1" stop-color="#075450"/></linearGradient></defs>
<rect x="4" y="4" width="56" height="56" rx="14" fill="url(#lg)"/>
<rect x="17" y="18" width="30" height="6" rx="3" fill="#fff"/>
<rect x="17" y="29" width="19" height="6" rx="3" fill="#fff"/>
<rect x="17" y="40" width="30" height="6" rx="3" fill="#fff"/>
<circle cx="44" cy="32" r="3.6" fill="#ffd27a"/>
</svg>`;
