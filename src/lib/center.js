// 관제센터 mock (React/DOM 의존 없음 → node로 직접 테스트).
// 실제 판정은 파이썬 pipeline/build_push.py 가 public/push/*.json 으로 내보낸다. 여기 함수들은
//  - buildPush   : 시나리오 고정값으로 같은 모양의 push 를 만드는 mock(테스트·fixture 검증용)
//  - noCenterPush: 단말이 push 파일을 못 받았을 때 — 판정하지 않고 전 구간 '보류'로 안전하게 우회
// 단말(NaviView)은 push 모양만 그린다 — 판정·경로 계산을 직접 하지 않는다.
import { isPassable } from './passable.js'
import { requiredWidthM } from '../data/vehicles.js'

// 우회를 일으키는 상태. 팀 원칙 "불가를 통과로 오판하는 쪽이 더 나쁘다" → 판정 보류(handoff)도 우회한다.
// (pipeline/build_push.py 의 REROUTE_STATUSES 와 같게 유지)
export const REROUTE_STATUSES = ['block', 'handoff']

// 판정된 구간들에 경로를 붙여 push 모양을 완성한다. routes: { primary, detour, segmentPos } (src/data/pushedRoutes.js).
// ponytail: 우회 경로는 fixture 1개(routes.detour) 고정. 막힌 구간 조합별 경로 산출은 센터 프로그램(route/) 몫.
export function withRoute(vehicle, judged, routes) {
  const rerouted = judged.some((s) => REROUTE_STATUSES.includes(s.status))
  return {
    vehicleId: vehicle.id,
    requiredWidthM: requiredWidthM(vehicle),
    segments: judged,
    rerouted,
    route: rerouted ? routes.detour : routes.primary,
    abandonedPath: rerouted ? routes.primary.path : [],
  }
}

// mock 판정. segments: [{ id, cause: { effectiveWidthM } }] (src/data/scenario.js). 여유폭 없이 폭만 대조한다.
export function buildPush(vehicle, segments, routes) {
  const required = requiredWidthM(vehicle)
  const judged = segments.map((s) => ({
    id: s.id,
    pos: routes.segmentPos[s.id],
    status: isPassable(s.cause.effectiveWidthM, required) ? 'pass' : 'block',
  }))
  return withRoute(vehicle, judged, routes)
}

// 센터 push 를 못 받았을 때. 단말이 대신 판정하면 파일 하나 빠진 것만으로 판정이 위험한 쪽으로 뒤집힐 수 있으므로
// 판정하지 않고 전 구간을 보류(handoff)로 두고 우회한다. noCenter 로 화면에 "판정 수신 실패"를 띄운다.
export function noCenterPush(vehicle, segments, routes) {
  const judged = segments.map((s) => ({ id: s.id, pos: routes.segmentPos[s.id], status: 'handoff', reason: 'no_center_push' }))
  return { ...withRoute(vehicle, judged, routes), noCenter: true }
}
