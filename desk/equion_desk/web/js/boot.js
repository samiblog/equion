// 화면을 그리기 전에 바탕(밝게·어둡게)을 정한다 — 어두운 바탕을 쓰는 사람에게 흰 화면이 번쩍이지 않게.
// 설정값은 서버가 index.html 의 data-theme-setting 에 실어 준다(나머지 설정은 main.js 가 /api/state 에서 읽는다).
(function () {
  var root = document.documentElement;
  var setting = root.getAttribute('data-theme-setting');
  var dark = setting === 'dark' || (setting !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
})();
