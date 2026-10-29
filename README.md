# ANCHOR-COSS · 소방 출동 단말

앵커×코스 융합해커톤 (앵커팀 **길든타임** × 코스팀 **BISA**)

소방차 출동 경로에서 **불법주정차로 진입이 막힌 구간**을 관제 CCTV로 판정하고, 그 구간을 피한 **우회경로**를 소방 출동 단말에 표출한다.
이 저장소는 그중 **소방 출동 단말(웹)** 과, 관제센터 프로그램이 붙기 전까지 그 자리를 대신하는 **mock 센터**를 담고 있다.

## 시스템 구성

```
관제센터 프로그램   CCTV 영상 → 차량 검출 → 잔여 폭 산출 → 진입 판정 → 우회경로 산출
──────────────────  판정 결과와 경로만 전송 (영상·계산 근거는 센터 밖으로 나가지 않음)
소방 출동 단말      진입 불가 구간과 우회경로를 지도에 표출   ← 이 저장소
```

- 관제 영상은 관제센터 밖으로 반출할 수 없다. 그래서 단말은 **표출만** 한다 — 검출·판정·경로 계산을 하지 않고, 주행 화면에 잔여 폭 같은 계산 과정도 띄우지 않는다.
- 전송은 출동 지령 시점의 **1회 단방향 push**다. 주행 중 경로 전환 로직은 없다.
- 지금은 `src/lib/center.js`의 `buildPush()`가 센터 역할을 한다(순수 함수). 관제센터 프로그램이 같은 모양의 JSON을 내보내면 이 함수만 교체하면 된다.

```js
buildPush(vehicle, segments, routes)
// → { vehicleId, requiredWidthM, segments: [{ id, pos, passable }], rerouted, route, abandonedPath }
```

## 화면

1. **출동 브리핑** — 신고 내용·위치. "안내 시작"으로 내비 화면 진입.
2. **내비** — 안내 경로(파랑), 진입 불가로 버려진 원 경로(회색 점선), CCTV 판정 구간 마커(막힘=빨강), 턴 안내·속도·ETA.
   우상단 **차종 칩**을 누르면 *진입 기준 · 차종별 제원* 패널이 열리고, 차종을 바꾸면 같은 골목의 판정과 경로가 바뀐다
   (예: 잔여 폭 2.9m 구간 — 구급차·경형펌프차는 직진, 소형펌프차 이상은 우회).

## 판정 기준

`필요 통과폭 = 차폭 + 여유폭`, 잔여 폭이 이보다 좁으면 **진입 불가**. 데이터는 `src/data/vehicles.js`.

| 항목 | 값 | 출처 |
|---|---|---|
| 펌프차 4종 제원(전장·전폭·전고) | 규격 상한값 | 소방청 「2025년 소방자동차 다수공급자 계약(MAS) 차종별 제작규격」 |
| 여유폭 | 전 차종 0.8m | 현직 소방관 의견 "도로 폭 최소 3.25m"(명대신문, 2018-10-01) → 차폭 2.5m 대비 0.75m |
| 진입곤란·진입불가 정의 | 도로 폭 3m / 2m | 소방청 「소방차 진입곤란(불가) 지역 일제조사」 기준 |
| 법적 근거 | — | 「건축법 시행령」 제41조, 「소방기본법」 제21조의2·시행령 제7조의12~14 |

- 제원을 상한값으로 쓰는 이유: 불가를 가능으로 오판하는 쪽(현장 도착 후 진입 실패)이 불필요한 우회보다 더 나쁘다.
- 구급차·물탱크차·고가사다리차 제원은 아직 **잠정값**이다(`verified: false`, 화면에 "잠정" 표시).
- 건축법 시행령 제41조①의 통로 유효폭(0.9/1.5/3m)은 일반 건축물 통로 기준이라 소방차 통과폭으로 쓰지 않는다.

## 데모 시나리오

서울 종로구 창신동: 을지로119안전센터 → (창신시장 인근 창신길, 불법주정차) → 창신6길 주택가. 데이터는 `src/data/scenario.js`.

경로는 Kakao 길찾기를 **개발 시 1회** 호출해 고정 fixture(`src/data/pushedRoutes.js`)로 저장한 것이다. 앱 런타임은 길찾기 API를 호출하지 않는다.
우회 경로는 Kakao가 특정 도로 제외를 지원하지 않아 **경유지로 회피를 유도한 근사**이며, 캡처 스크립트가 "막힌 지점에서 40m 이상 떨어졌는지"를 검사해 통과한 후보 중 최단 경로를 고른다.

## 실행

```bash
npm install
cp .env.example .env   # VITE_KAKAO_MAP_KEY(지도 JS 키) 입력
npm run dev            # http://localhost:5173
```

- 지도 표시에 **Kakao Maps JavaScript 키**가 필요하다(Kakao Developers → 플랫폼 Web 도메인에 `http://localhost:5173` 등록).
- `KAKAO_REST_KEY`는 경로 fixture를 다시 캡처할 때만 필요하다.

```bash
npm test       # node --test, 프레임워크 없음
npm run lint   # oxlint
npm run build
```

### 시나리오 좌표를 바꿨을 때

`scenario.js`의 출발·목적지·판정 구간 좌표를 바꾸면 fixture를 다시 만들어야 한다. dev 서버가 떠 있는 상태에서:

```bash
node scripts/capture-routes.mjs
```

- 판정 구간 좌표가 원 경로에서 30m 넘게 벗어나 있으면 중단된다(차가 다니는 도로 위 좌표여야 함).
- 다시 캡처하지 않으면 `pushedRoutes.test.js`가 실패하며 알려준다.

## 구조

```
src/
  App.jsx                   브리핑 ↔ 내비 화면 전환
  components/
    Briefing.jsx            public/fire-dispatch.html(디자인 export)을 iframe으로 띄우고 값만 주입
    NaviView.jsx            push 결과 표출 (지도·경로·마커·HUD)
    VehiclePanel.jsx        진입 기준 · 차종별 제원 패널
  data/
    scenario.js             출발·목적지·판정 구간(잔여 폭)
    vehicles.js             차종 제원, 여유폭, 진입 기준, 법적 근거
    pushedRoutes.js         경로 fixture (스크립트 산출물 — 직접 수정 금지)
  lib/
    center.js               mock 관제센터: buildPush()
    passable.js             폭 대조 판정
    geo.js                  haversine, 경로 투영, 점–경로 거리, 우회 경유지
    directions.js           Kakao 길찾기 호출·파싱 (캡처 스크립트 전용)
scripts/capture-routes.mjs  경로 fixture 캡처
```

## 범위 밖 / 한계

- 영상 분석(차량 검출, 기준물 기반 잔여 폭 환산)과 실제 관제망 연동은 이 저장소에 없다. 잔여 폭은 시나리오의 고정값이다.
- 우회 경로는 도로망에서 구간을 제외해 재산출한 것이 아니라 경유지 기반 근사다.
- 길찾기 프록시는 Vite dev 서버에만 있다. 정적 빌드는 fixture만으로 동작하지만, fixture 재캡처는 dev 환경에서만 된다.

## 관제센터 분석 (Python) — 잔여 폭 추정

CCTV 영상에서 불법주정차 옆 잔여 폭(m)을 추정하는 관제센터 쪽 코드. 단말(웹)과 별개로 돌린다.

```
common/    BISA 데이터 로더, 소방 진입 기준·차종별 차폭(apparatus.py)
scale/     픽셀→미터 스케일(소실점 보정), 단면 잔여 폭 측정, T03 격자 검증
eval/      전 클립 채점 — BISA 납품 tools/validate_width.py 를 그대로 사용
data/      BISA_납품_* 폴더를 여기에 둔다 (git 제외)
```

```bash
pip install -r requirements.txt
python -X utf8 -m eval.run --source gt     # 기준선 vs 소실점 보정 전후 비교
python -X utf8 -m scale.grid_check         # T03 마커 격자 거리별 검증
python -X utf8 -m common.apparatus         # 차종별 필요 통과폭 표
```

규칙: 정답 폭·월드 좌표를 예측 입력으로 쓰지 않는다. GT 모드 입력은 footprint px, 도로 경계 px, 차종뿐. 상세는 `scale/README.md`.
