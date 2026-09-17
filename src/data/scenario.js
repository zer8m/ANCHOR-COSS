// 데모 시나리오 mock 데이터.
// 무대: 서울 마포구 연남동 주택가 좁은 골목 (실제 도로망 위 임의 좌표).
// 실제 배포 시 이 파일을 서버/공공 API 응답으로 교체.

export const dispatch = {
  id: 'D-2026-0721-014',
  incident: '주택 화재 · 온새미로 주택',
  // 목적지: 대전 유성구 대학로137번길 46 (온새미로 주택)
  destination: { name: '대학로137번길 46 온새미로 주택', lat: 36.36312, lng: 127.34899 },
  // 출발: 대전 둔산소방서 월평119안전센터
  currentPos: { lat: 36.36, lng: 127.36688, heading: 280 }, // heading: 북=0, 시계방향(deg)
  distanceM: 1700,
  etaMin: 5,
  speedKmh: 32,

  // 브리핑 화면용 신고·출동 정보
  station: '대전 둔산소방서 월평119안전센터',
  vehicle: '고가사다리차 · 마포 사다리1',
  responseLevel: '대응 1단계',
  reportedAt: '07.21 · 09:42',
  reportText:
    '연남동 239-12 다세대주택 3층에서 연기 다량 발생. 거주자 2명 소재 미확인, 인명 구조 요청. 진입로 불법주정차 신고 접수.',
  tags: ['인명 위험', '3층 다세대', '진입로 협소'],
  truckImage: '/truck.png', // public/truck.png (배경 투명 PNG). 없으면 플레이스홀더로 폴백.
}

// 브리핑 첫 화면(목업 그대로).
export const briefing = {
  dispatchTag: '긴급 출동',
  unitTitle: '주력 펌프차 01',
  standby: 'EMERGENCY ON STANDBY',
  chips: ['출동가능', '장비점검', '주간편성'],
  priority: '최우선 순위: 화재 발생',
  address: '대전광역시 유성구 대학로137번길 46',
  addressSub: '(온새미로 주택 · 원룸촌 밀집지역)',
  // 카카오내비 목적지
  naviDest: { name: '대학로137번길 46 온새미로 주택', lat: 36.36312, lng: 127.34899 },
  stationBase: '월평119안전센터',
  shiftLabel: '7월 20일 · 주간 교대',
  date: { day: '20', month: 'JULY', time: '10:25', ampm: 'A.M.' },
  report: [
    { label: '발생 지점', text: '3층 원룸 건물 2층에서 연기·불꽃 식별' },
    { label: '인명 현황', text: '원룸 다수 세대 거주, 미처 대피하지 못한 인원 3명 추정' },
    { label: '위험 요소', text: '좁은 골목·불법주정차로 진입로 협소, 원룸촌 건물 밀집' },
    { label: '현장 상황', text: '선착대 도착 3분 전, 인명 구조 우선 · 추가 지원 요청됨' },
  ],
}

// 경로는 지도에 그릴 polyline 좌표열 ([lat, lng]).
// primary: 최단 경로(장애물 통과 구간 포함). alternate: 통과불가 시 우회로.
export const routes = {
  primary: [
    [37.5619, 126.9256],
    [37.5627, 126.9251],
    [37.5634, 126.9248], // 이 부근 obstacle o2 (통과불가)
    [37.5642, 126.9247],
    [37.5652, 126.9245],
  ],
  alternate: [
    [37.5619, 126.9256],
    [37.5626, 126.9262],
    [37.5636, 126.9261],
    [37.5645, 126.9254],
    [37.5652, 126.9245],
  ],
  alternateExtraMin: 2,
}

// CCTV 판정 구간. effectiveWidthM = 주차 차량을 뺀 잔여 통과 폭(m).
// 통과 여부는 데이터에 두지 않는다 — 차종별 필요 통과폭과 대조해 센터(center.js)가 판정.
export const obstacles = [
  {
    id: 'o1',
    distanceM: 2180, // 원 경로 위 지점 (총 ~2505m)
    cause: { type: '불법주정차', vehicleCount: 1, effectiveWidthM: 3.2 },
  },
  {
    id: 'o2',
    distanceM: 2350,
    cause: { type: '불법주정차', vehicleCount: 3, effectiveWidthM: 2.6 },
  },
]

export const facilities = [
  { id: 'h1', type: 'hydrant', pos: { lat: 37.5631, lng: 126.9253 } },
  { id: 'h2', type: 'hydrant', pos: { lat: 37.5648, lng: 126.9246 } },
  { id: 'f1', type: 'firelane', pos: { lat: 37.5624, lng: 126.9254 } },
]

// 소방 진입 위험 구간(최단경로가 지나면 위험) — 실제 경유지로 우회.
// radius(m) 원으로 지도에 표시.
export const hazardZones = [
  { id: 'z1', type: 'market', name: '연남 전통시장', pos: { lat: 37.5638, lng: 126.9258 }, radius: 55 },
  { id: 'z2', type: 'alley', name: '좁은 골목 (폭 2m)', pos: { lat: 37.5645, lng: 126.9250 }, radius: 38 },
  { id: 'z3', type: 'deadend', name: '막다른 길', pos: { lat: 37.563, lng: 126.924 }, radius: 32 },
]

// 위험구간을 피해 도는 안전 경유지(waypoint). 길찾기에 넣어 실제 우회 경로를 받음.
export const safeWaypoint = { lat: 37.5636, lng: 126.9263 }

// 구간이 "통과불가"로 토글되면 이 경유지를 추가해 실제 우회 경로 재계산.
// (Kakao는 특정 도로 edge 제외를 지원 안 하므로 경유지로 우회 유도 — 데모 근사)
export const blockDetour = { lat: 37.5624, lng: 126.9235 }

// 상습 진입곤란 구간 통계(Report). 데모용 mock — 좁은 골목·상가밀집·이면도로에 수치 집중.
// (실서비스는 경로 구간 상태값 이벤트를 축적해 산출)
export const reportPeriod = '2026.06.21 ~ 07.21'
export const chronicSegments = [
  { id: 's1', name: '연남동 먹자골목', type: 'market', count: 42, avgDelayMin: 6.2, trend: 'up', pos: { lat: 37.5638, lng: 126.9258 } },
  { id: 's2', name: '동교로 9번길', type: 'alley', count: 35, avgDelayMin: 5.1, trend: 'up', pos: { lat: 37.5645, lng: 126.925 } },
  { id: 's3', name: '성미산로 이면도로', type: 'backroad', count: 28, avgDelayMin: 4.3, trend: 'flat', pos: { lat: 37.563, lng: 126.924 } },
  { id: 's4', name: '연남로 12번길', type: 'deadend', count: 21, avgDelayMin: 3.8, trend: 'down', pos: { lat: 37.5652, lng: 126.9262 } },
  { id: 's5', name: '동교동 상가 밀집', type: 'market', count: 19, avgDelayMin: 3.2, trend: 'up', pos: { lat: 37.5619, lng: 126.9268 } },
  { id: 's6', name: '연남동 주택가 골목', type: 'alley', count: 14, avgDelayMin: 2.6, trend: 'flat', pos: { lat: 37.5626, lng: 126.9272 } },
]

// 관제실 무전 기록(로그용). 연결 시 순차적으로 흘러나오는 상황실 지령/보고.
// 시각(t)은 연결 시점 기준 실시간으로 찍음.
export const controlLog = [
  { who: '상황실', text: '출동 지령서가 연결되었습니다.' },
  { who: '상황실', text: '대응 1단계 발령. 인명 구조 최우선.' },
  { who: '상황실', text: '현장 3층 연기 다량, 거주자 2명 소재 미확인.' },
  { who: '지휘', text: '월평 사다리1 출동 확인, 진입로 접근 중.' },
  { who: '상황실', text: '진입로 불법주정차 신고 접수, CCTV 확인 요청.' },
  { who: '상황실', text: '우회 경로 안내 전송. 좁은 골목 진입 주의.' },
  { who: '지휘', text: '우회로 수신, 4분 내 현장 도착 예정.' },
  { who: '상황실', text: '인근 소화전 2개소 위치 공유 완료.' },
]

// 출동 대원 실시간 관제. status: ok | warn | danger, comm: on | lost.
export const crew = [
  { id: 'c1', name: '김반장', role: '지휘', pos: { lat: 37.5651, lng: 126.9247 }, status: 'ok', airPct: 84, hr: 98, comm: 'on' },
  { id: 'c2', name: '이현수', role: '관창', pos: { lat: 37.5653, lng: 126.9244 }, status: 'ok', airPct: 71, hr: 112, comm: 'on' },
  { id: 'c3', name: '박민재', role: '진입', pos: { lat: 37.565, lng: 126.9243 }, status: 'warn', airPct: 34, hr: 134, comm: 'on' },
  { id: 'c4', name: '정우진', role: '진입', pos: { lat: 37.5654, lng: 126.9242 }, status: 'danger', airPct: 22, hr: 148, comm: 'lost', lastSeen: '09:44' },
]
