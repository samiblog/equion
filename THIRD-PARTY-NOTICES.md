# Third-party notices

Equion은 MIT 라이선스입니다([LICENSE](LICENSE)). 아래는 Equion 안에 포함된 외부 자료와 그 고지입니다.

## 단위근·공적분 검정 수치표 — `equion/stats/_tables.py`

ADF·Engle-Granger p값 근사 계수(MacKinnon 1994), 임계값 반응곡면 계수(MacKinnon 2010), Johansen 임계값
(MacKinnon, Haug & Michelis 1999; J.P. LeSage의 Econometrics Toolbox에 정리된 값)을 statsmodels
(`statsmodels/tsa/adfvalues.py`, `statsmodels/tsa/coint_tables.py`)에 정리된 배열 그대로 옮겼습니다.
계산 코드는 Equion이 직접 작성했습니다(`equion/stats/unitroot.py`).

- MacKinnon, J.G. (1994). Approximate asymptotic distribution functions for unit-root and cointegration
  tests. *Journal of Business & Economic Statistics* 12, 167–176.
- MacKinnon, J.G. (2010). Critical values for cointegration tests. Queen's Economics Department Working
  Paper No. 1227.
- MacKinnon, J.G., Haug, A.A., Michelis, L. (1999). Numerical distribution functions of likelihood ratio
  tests for cointegration. *Journal of Applied Econometrics* 14, 563–577.

statsmodels 라이선스(BSD 3-Clause):

```
Copyright (C) 2006, Jonathan E. Taylor
All rights reserved.

Copyright (c) 2006-2008 Scipy Developers.
All rights reserved.

Copyright (c) 2009-2018 statsmodels Developers.
All rights reserved.


Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  a. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.
  b. Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.
  c. Neither the name of statsmodels nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.


THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL STATSMODELS OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGE.
```

## plotly.js 3.4.0 — `equion/assets/plotly-3.4.0.min.js.gz`

그래프 그리기 스크립트(plotly.js 배포본 `plotly.min.js`)를 gzip으로 줄여 그대로 내장했습니다. 명령줄 보고서
(`--plotlyjs copy`)·`GraphOutput.save(..., include_js="inline")`가 이 파일을 씁니다. plotly 파이썬 패키지는
쓰지 않습니다(선택 설치 `equion[plot]`). 배포본 머리말: "plotly.js v3.4.0 · Copyright 2012-2026, Plotly, Inc. ·
Licensed under the MIT license". 배포본 안에 함께 묶인 라이브러리(d3 등)의 고지는 배포본 안의 주석과
plotly.js 저장소(<https://github.com/plotly/plotly.js>)에 있습니다.

plotly.js 라이선스(MIT):

```
Copyright (c) 2012-2026 Plotly, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## 시험 기준값 — `tests/fixtures/stats_reference.json`

자체 구현을 검증하려고 statsmodels로 한 번 계산해 고정한 결과값입니다(`tests/fixtures/make_stats_reference.py`).
Equion 실행에는 쓰이지 않습니다.
