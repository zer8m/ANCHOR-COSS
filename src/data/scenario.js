// 데모 시나리오 mock 데이터.
// 무대: 서울 종로구 창신동 (을지로119안전센터 → 창신시장 인근 → 창신6길 주택가).
// 실제 배포 시 이 파일을 서버/공공 API 응답으로 교체.
// ⚠️ 출발·목적지·obstacles 좌표를 바꾸면 `node scripts/capture-routes.mjs`로 경로 fixture를 다시 만들 것.

export const dispatch = {
  // 출발: 을지로119안전센터
  currentPos: { lat: 37.5666, lng: 127.01195 },
  destination: { name: '창신6길 주택가', lat: 37.57657, lng: 127.01174 },
}

// 브리핑 화면(public/fire-dispatch.html)에 주입하는 신고 내용.
export const briefing = {
  address: '서울특별시 종로구 창신6길',
  addressSub: '(창신동 주택가 · 좁은 골목 밀집지역)',
  report: [
    { label: '발생 지점', text: '3층 다세대주택 2층에서 연기·불꽃 식별' },
    { label: '인명 현황', text: '다세대 다수 세대 거주, 미처 대피하지 못한 인원 3명 추정' },
    { label: '위험 요소', text: '좁은 골목·창신시장 인근 불법주정차로 진입로 협소, 주택 밀집' },
    { label: '현장 상황', text: '선착대 도착 3분 전, 인명 구조 우선 · 추가 지원 요청됨' },
  ],
}

// 우회 경로가 막힌 지점에서 최소 이만큼(m) 떨어져야 "피했다"로 인정. 캡처 스크립트와 fixture 테스트가 공유.
export const AVOID_MIN_M = 40

// CCTV 판정 구간. 운용 판정은 파이썬 pipeline(public/push/*.json)이 하고, 단말은 여기서 id·pos 만 쓴다.
// effectiveWidthM(잔여 폭)은 mock buildPush(테스트·fixture 검증) 전용 — 화면 판정에는 쓰이지 않는다.
// pos: 기획상 지점은 창신시장 골목(37.57318, 127.01142)이나, 그 골목은 Kakao 자동차 도로망에 없어
//      최단 경로가 지나는 최근접 지점(창신길 · 시장 입구, 서쪽 65m)으로 옮겨 둠.
export const obstacles = [
  {
    // o1 보다 94m 앞(출발지 쪽). 우회로가 이미 피해 가는 창신길 구간 안에 둠.
    id: 'o2',
    name: '창신길 하단 (시장 입구 전)',
    pos: { lat: 37.57228, lng: 127.01067 },
    cause: { type: '불법주정차', vehicleCount: 1, effectiveWidthM: 2.8 }, // mock 전용. 납품 S38 정답 잔여 폭 2.80m 에 맞춤
  },
  {
    id: 'o1',
    name: '창신시장 인근 (창신길)',
    pos: { lat: 37.57313, lng: 127.01069 },
    cause: { type: '불법주정차', vehicleCount: 1, effectiveWidthM: 2.9 }, // mock 전용. 납품 S33 정답 잔여 폭 2.92m 에 맞춤
  },
]
