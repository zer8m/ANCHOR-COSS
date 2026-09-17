// 진입 기준 / 차종별 제원 테이블.
// ⚠️ verified:false 수치는 잠정값 — 소방 도메인 기준 조사(조서희) 결과로 교체하고 true로 바꿀 것.

// 통과 여유폭(m): 차폭에 더해 필요 통과폭을 만든다. 잠정: 양측 0.2m.
// (차폭 == 잔여 폭이면 사이드미러·측면 여유가 없어 실제로는 못 지나감)
export const CLEARANCE_M = 0.4

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

export const VEHICLES = [
  { id: 'ambulance', name: '구급차', widthM: 2.0, lengthM: 5.7, verified: false },
  { id: 'pump-s', name: '소형펌프차', widthM: 2.0, lengthM: 6.0, verified: false },
  { id: 'pump-m', name: '중형펌프차', widthM: 2.5, lengthM: 7.8, verified: false, note: '차폭 2.5m는 소방청 진입 기준의 기준 차량 폭' },
  { id: 'tank', name: '물탱크차', widthM: 2.5, lengthM: 8.6, verified: false },
  { id: 'ladder', name: '고가사다리차', widthM: 2.5, lengthM: 12.0, verified: false },
]
export const DEFAULT_VEHICLE_ID = 'pump-m'

// 필요 통과폭(m) = 차폭 + 여유폭, 0.1m 단위로 반올림(부동소수 오차 제거).
export function requiredWidthM(vehicle) {
  return Math.round((vehicle.widthM + CLEARANCE_M) * 10) / 10
}
