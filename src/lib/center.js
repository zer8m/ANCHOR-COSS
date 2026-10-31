// 관제센터 mock (React/DOM 의존 없음 → node로 직접 테스트).
// 실제 시스템에서는 관제센터 Python 프로그램이 같은 모양의 페이로드를 단말에 push한다.
// 단말(NaviView)은 이 반환값만 그린다 — 판정·경로 계산을 직접 하지 않는다.
// 지금은 pipeline/build_push.py(public/push/*.json)가 본 역할을 하고, 이 함수는 push 파일이 없을 때의 폴백.
// status: 'pass' | 'block' (| 'handoff' — 판정 보류, 파이썬 쪽만 냄).
import { isPassable } from './passable.js'
import { requiredWidthM } from '../data/vehicles.js'

// vehicle: VEHICLES 항목. segments: [{ id, cause: { effectiveWidthM } }].
// routes: { primary, detour, segmentPos } (src/data/pushedRoutes.js).
// ponytail: 우회 경로는 fixture 1개(routes.detour) 고정. 막힌 구간 조합별 경로 산출은
//           센터 프로그램(도로망 edge 제외)이 생기면 그쪽으로.
export function buildPush(vehicle, segments, routes) {
  const required = requiredWidthM(vehicle)
  const judged = segments.map((s) => ({
    id: s.id,
    pos: routes.segmentPos[s.id],
    status: isPassable(s.cause.effectiveWidthM, required) ? 'pass' : 'block',
  }))
  const rerouted = judged.some((s) => s.status === 'block')
  return {
    vehicleId: vehicle.id,
    requiredWidthM: required,
    segments: judged,
    rerouted,
    route: rerouted ? routes.detour : routes.primary,
    abandonedPath: rerouted ? routes.primary.path : [],
  }
}
