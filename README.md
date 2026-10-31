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
- 센터 push = `public/push/{차종id}.json` (파이썬 `pipeline/build_push.py` 산출물). 단말은 차종을 고르면 이 파일을 fetch해서 그린다.
- **push를 못 받으면 단말이 대신 판정하지 않는다.** 전 구간을 보류(handoff)로 두고 우회하며 "관제센터 판정 수신 실패" 배너를 띄운다(`center.js` `noCenterPush`). 단말 mock 판정(`buildPush`)은 테스트·fixture 검증에만 쓴다.
- **판정 보류(handoff)도 우회한다.** 팀 원칙 "불가를 통과로 오판하는 쪽이 더 나쁘다"에 따라, 관제요원이 확인하기 전까지는 보류 구간을 지나지 않는다(`REROUTE_STATUSES = block, handoff`, 파이썬·JS 동일).

```js
// public/push/pump-m.json
{ vehicleId, requiredWidthM, segments: [{ id, name, pos, status: 'pass'|'block'|'handoff', clip_id, reason }],
  rerouted, route, abandonedPath }
```

## 화면

1. **출동 브리핑** — 신고 내용·위치. "안내 시작"으로 내비 화면 진입.
2. **내비** — 안내 경로(파랑), 진입 불가로 버려진 원 경로(회색 점선), CCTV 판정 구간 마커(통과=회색 · 막힘=빨강 · 판정 보류=노랑), 턴 안내·속도·ETA.
   `handoff`(판정 보류)는 영상을 믿기 어려워(원거리·검출 붕괴·가림) 관제요원 확인으로 넘긴 상태 — 불가와 마찬가지로 우회하고 노란 배너를 띄운다.
   우상단 **차종 칩**을 누르면 *진입 기준 · 차종별 제원* 패널이 열리고, 차종을 바꾸면 같은 골목의 판정과 경로가 바뀐다
   (예: 데모 구간 S33 — det 추정 잔여 폭 2.95m, 여유 20cm → 경형펌프차(필요 2.7m)만 직진, 구급차·소형펌프차 이상은 우회).

## 판정 기준

`필요 통과폭 = 차폭 + 여유폭`, 잔여 폭이 이보다 좁으면 **진입 불가**. 데이터는 `src/data/vehicles.js`.

| 항목 | 값 | 출처 |
|---|---|---|
| 펌프차 4종 제원(전장·전폭·전고) | 규격 상한값 | 소방청 「2025년 소방자동차 다수공급자 계약(MAS) 차종별 제작규격」 |
| 여유폭 | 전 차종 0.8m | 현직 소방관 의견 "도로 폭 최소 3.25m"(명대신문, 2018-10-01) → 차폭 2.5m 대비 0.75m |
| 진입곤란·진입불가 정의 | 도로 폭 3m / 2m | 소방청 「소방차 진입곤란(불가) 지역 일제조사」 기준 |
| 법적 근거 | — | 「건축법 시행령」 제41조, 「소방기본법」 제21조의2·시행령 제7조의12~14 |

- 제원을 상한값으로 쓰는 이유: 불가를 가능으로 오판하는 쪽(현장 도착 후 진입 실패)이 불필요한 우회보다 더 나쁘다.
- 차종 목록·id·차폭 근거(`kind`: spec_max / class_max / legal_max)는 파이썬 `common/apparatus.py`와 1:1이다. 사다리차·굴절차는 폭 규격을 못 찾아 법정 상한 2.5m(`legal_max`)를 쓰며 화면에 "잠정"으로 표시된다.
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

### 테스트

`npm test`는 단말(JS)만 돈다. 파이썬 쪽은 따로 실행한다(프레임워크 없음, assert 스크립트).

```bash
npm test                                   # 단말: src/**/*.test.js
npm run lint && npm run build
python -X utf8 -m pipeline.test_pipeline   # pipeline: judge 연결·push 모양 (데이터 없이 돈다)
python -X utf8 -m eval.judge_metrics --source det   # 판정 지표(위험 통과·불필요 우회·이관), 데이터 필요
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
    pushedRoutes.js         경로 fixture (스크립트 산출물 — 직접 수정 금지). pipeline이 push JSON에 그대로 싣는다
public/push/{id}.json       차종별 센터 push (pipeline/build_push.py 산출물 — 직접 수정 금지)
  lib/
    center.js               단말 내 mock 센터 buildPush() — push 파일 없을 때 폴백
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
python -X utf8 -m eval.run --source gt --scale all   # 기준선·소실점·bbox 자기보정 비교
python -X utf8 -m scale.grid_check         # T03 마커 격자 거리별 검증
python -X utf8 -m common.apparatus         # 차종별 필요 통과폭 표
```

### pipeline — 추정 결과 → 단말 push

```
pipeline/cameras.json    CCTV 클립 id → 단말 판정 구간 id
pipeline/summarize.py    outputs/det/{clip}_bbox_h_occ2_mem15.json → 구간 잔여 폭 하나(최근 15프레임 최솟값)
                         + judge.handoff 래치로 이관 사유(out_of_range / det_collapse / occlusion_suspect) 감지
pipeline/build_push.py   judge.decide(잔여폭 − 여유 20cm ≥ 필요폭) → 차종별 public/push/{id}.json
                         (center.js buildPush 와 같은 모양, passable 대신 status: 통과→pass, 불가→block, 관제이관→handoff)
```

```bash
python -X utf8 -m eval.run --source det --scale bbox_h   # outputs/det/ 생성 (선행, 운용 조건: det bbox + 설치 높이)
python -X utf8 -m pipeline.build_push                     # public/push/*.json
python -X utf8 -m pipeline.test_pipeline
```

판정·이관 규칙과 근거는 `judge/README.md`. `handoff`는 단말이 노란 "판정 보류" 마커·배너로 표시하고 우회한다.

입력 가정: `summarize.py`가 gt 파일에서 읽는 것은 **카메라 설치 정보(높이·화각)와 단면 도로 경계 px**뿐이다 — judge/eval과 같은 "CCTV 설치 시 1회 측량한 값" 가정이며, 정답 잔여 폭·차량 좌표는 쓰지 않는다.

규칙: 정답 폭·월드 좌표를 예측 입력으로 쓰지 않는다. GT 모드 입력은 footprint px, 도로 경계 px, 차종뿐. 상세는 `scale/README.md`.
