// 진입 기준 / 차종별 제원 테이블. 차종 목록은 파이썬 common/apparatus.py 와 1:1 — 한쪽을 고치면 다른 쪽도 맞출 것.

export const CRITERIA_SOURCE = '소방청 「소방차 진입곤란(불가) 지역 일제조사」 기준 · 중형펌프차 폭 2.5m 기준'
export const ENTRY_CRITERIA = [
  {
    id: 'blocked',
    label: '진입불가',
    rule: '도로 폭 2m 이하, 또는 이동 불가능한 장애물로 진입 불가 구간이 100m 이상',
  },
  {
    id: 'difficult',
    label: '진입곤란',
    rule: '도로 폭 3m 이상 도로 중 이동 불가능한 장애물로 진입곤란 구간이 100m 이상, 또는 상습 주차로 상시 진입·활동에 장애',
  },
]

// 법적 근거. 판정 임계값이 아니라 "왜 이 서비스가 필요한가"의 근거 — 판정은 위 기준 + 차종별 필요 통과폭으로 한다.
// 주의: 건축법 시행령 제41조①의 통로 유효폭(0.9/1.5/3m)은 일반 건축물 통로 기준이라 소방차 통과폭으로 쓰면 안 된다.
export const LEGAL_BASIS = [
  {
    id: 'access-road',
    label: '소방차 접근 통로',
    rule: '다중이용·준다중이용 건축물, 11층 이상 건축물이 있는 대지는 소방자동차의 접근이 가능한 통로를 설치해야 함',
    meaning: '소방차가 건축물까지 접근할 수 있는 경로가 확보되어야 한다는 법적 근거',
    source: '「건축법 시행령」 제41조②',
  },
  {
    id: 'passage-width',
    label: '일반 통로 유효폭',
    rule: '단독주택 0.9m 이상, 일부 대규모 시설 3m 이상, 그 밖의 건축물 1.5m 이상',
    meaning: '일반적인 건축물 통로 기준 — 소방차 통과폭으로 그대로 사용하면 안 됨',
    source: '「건축법 시행령」 제41조①',
  },
  {
    id: 'fire-zone',
    label: '소방자동차 전용구역',
    rule: '일정 규모 공동주택은 소방자동차 전용구역을 설치해야 함',
    meaning: '소방차가 실제 소방활동을 할 수 있는 공간 확보',
    source: '「소방기본법」 제21조의2, 시행령 제7조의12~13',
  },
  {
    id: 'zone-obstruction',
    label: '전용구역 진입 방해',
    rule: '전용구역 진입로에 물건을 쌓거나 주차하여 소방자동차의 진입을 가로막는 행위 금지',
    meaning: '불법주정차 등으로 진입로가 막히는 문제를 서비스가 다루는 근거',
    source: '「소방기본법 시행령」 제7조의14',
  },
]

// 차폭 값의 종류(kind) — 파이썬 common/apparatus.py 와 같은 구조·id. 센터 push의 vehicleId가 이 id로 온다.
//   spec_max  : 소방청 제작규격의 "○○mm 이하" 상한
//   class_max : 소방장비 분류표의 차종 구간 상한("○○mm 미만")
//   legal_max : 차종 규격에서 폭을 못 찾아 자동차 폭 법정 상한(2.5m)을 쓴 값 → 화면에 "잠정" 표시(VehiclePanel)
// 전장·전폭·전고는 규격의 "이하"(상한) 값. 실차는 이보다 작을 수 있으나
// 판정은 상한 기준이 안전하다(불가를 가능으로 오판하는 쪽이 더 나쁨).
// 모든 차폭은 사이드미러 등 돌출부 제외 기준 — 미러는 여유폭이 흡수한다.
export const SOURCES = {
  mas_2025: {
    short: '소방청 MAS 제작규격',
    label: '소방청 「2025년 소방자동차 다수공급자 계약(MAS) 차종별 제작규격」(2024-11-11 게시)',
    url: 'https://www.nfsa.go.kr/nfa/releaseinformation/0010/0001/?boardId=bbs_0000000000000566&mode=view&cntId=266',
  },
  equip_class: {
    short: '소방장비 분류표',
    label: '「소방장비관리법 시행규칙」 [별표 1] 소방장비의 분류 및 내용연수 — 특수구급차 크기 구간',
    url: 'https://www.law.go.kr/LSW/flDownload.do?flSeq=146205053&bylClsCd=200201',
  },
  sejong_tank_2025: {
    short: '세종소방 물탱크차 규격서(안)',
    label: '세종소방 「2025년 소방물탱크차 규격서(안)」 대형(12,000ℓ 이상) 전폭 2,500mm 이하',
    url: 'https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK00665217&bidPbancOrd=000&fileType=&fileSeq=4',
  },
  molit_width: {
    short: '국토부 자동차 폭 법정 상한',
    label: '국토교통부 운행제한차량 안내 — 국내 모든 자동차 폭 2.5m 이하 제작(후사경 등 돌출부 제외)',
    url: 'https://www.molit.go.kr/wrocm/USR/WPGE0201/m_20076/DTL.jsp',
  },
}

// clearanceM = 차종별 통과 여유폭(m). 차폭에 더해 필요 통과폭을 만든다.
// (차폭 == 잔여 폭이면 사이드미러·측면 여유가 없어 실제로는 못 지나감)
// 전 차종 0.8m. 근거: 현직 소방관 의견 "도로 폭이 최소 3.25m는 넘어야 소방차 진입 가능(4m는 돼야 원활)" —
//    중형펌프차 폭 2.5m 대비 여유 0.75m ≈ 0.8m. 소방청 진입곤란 기준선(3m = 차폭 + 0.5m)보다 보수적으로 잡은 값.
//    차종별로 달리할 근거가 생기면 행마다 교체.
export const CLEARANCE_SOURCE = '명대신문 「화재 안전 사각지대」(2018-10-01) · 현직 소방관 "최소 3.25m"'
export const CLEARANCE_SOURCE_URL = 'https://news.mju.ac.kr/news/articleView.html?idxno=4325'
export const VEHICLES = [
  { id: 'pump-xs', name: '경형펌프차', widthM: 1.9, clearanceM: 0.8, lengthM: 5.2, heightM: 2.8, kind: 'spec_max', source: 'mas_2025' },
  { id: 'pump-s', name: '소형펌프차', widthM: 2.2, clearanceM: 0.8, lengthM: 6.8, heightM: 2.8, kind: 'spec_max', source: 'mas_2025' },
  { id: 'pump-m', name: '중형펌프차', widthM: 2.5, clearanceM: 0.8, lengthM: 8.0, heightM: 3.2, kind: 'spec_max', source: 'mas_2025', note: '진입 기준의 기준 차량' },
  { id: 'pump-l', name: '대형펌프차', widthM: 2.5, clearanceM: 0.8, lengthM: 8.5, heightM: 3.4, kind: 'spec_max', source: 'mas_2025' },
  { id: 'tank-l', name: '대형물탱크차', widthM: 2.5, clearanceM: 0.8, kind: 'spec_max', source: 'sejong_tank_2025', note: '시도 규격서(안) 값. MAS 규격 원문 대조 필요' },
  { id: 'ladder', name: '고가사다리차', widthM: 2.5, clearanceM: 0.8, kind: 'legal_max', source: 'molit_width', note: '사다리·굴절차는 MAS가 아닌 경쟁입찰 차종이라 공통 폭 규격 미확인 → 법정 상한' },
  { id: 'aerial', name: '굴절차', widthM: 2.5, clearanceM: 0.8, kind: 'legal_max', source: 'molit_width', note: '사다리차와 동일' },
  { id: 'amb-s', name: '구급차(소형)', widthM: 2.0, clearanceM: 0.8, lengthM: 6.0, kind: 'class_max', source: 'equip_class', note: '7~14인승 기반, 분류표 "2,000mm 미만"' },
  { id: 'amb-m', name: '구급차(중형)', widthM: 2.1, clearanceM: 0.8, lengthM: 6.28, kind: 'class_max', source: 'equip_class', note: '15~24인승 기반, 분류표 "2,100mm 미만"' },
]
export const DEFAULT_VEHICLE_ID = 'pump-m'

// 필요 통과폭(m) = 차폭 + 차종별 여유폭, 0.1m 단위로 반올림(부동소수 오차 제거).
export function requiredWidthM(vehicle) {
  return Math.round((vehicle.widthM + vehicle.clearanceM) * 10) / 10
}
