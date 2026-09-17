// 프레임워크 없이 node로 직접 실행: `node src/lib/center.test.js`
import assert from 'node:assert/strict'
import { buildPush } from './center.js'
import { VEHICLES, requiredWidthM } from '../data/vehicles.js'

const byId = (id) => VEHICLES.find((v) => v.id === id)

// 부동소수 오차 없이 0.1m 단위 (2.3 + 0.4 = 2.6999… 방지).
assert.equal(requiredWidthM({ widthM: 2.3, clearanceM: 0.4 }), 2.7)
// 여유폭은 차종별 값: 같은 차폭이라도 여유폭이 다르면 필요 통과폭이 달라진다.
assert.equal(requiredWidthM({ widthM: 2.5, clearanceM: 0.6 }), 3.1)
assert.equal(requiredWidthM(byId('pump-m')), 3.3)
assert.equal(requiredWidthM(byId('ambulance')), 2.8)

const primary = { path: [{ lat: 1, lng: 1 }], guides: [], distanceM: 100, durationSec: 10 }
const detour = { path: [{ lat: 2, lng: 2 }], guides: [], distanceM: 150, durationSec: 15, avoids: ['b'] }
const routes = { primary, detour, segmentPos: { a: { lat: 1, lng: 1 }, b: { lat: 1, lng: 2 } } }
const segments = [
  { id: 'a', cause: { effectiveWidthM: 3.5 } },
  { id: 'b', cause: { effectiveWidthM: 2.9 } },
]

// 같은 골목(잔여 폭 2.9m): 구급차는 통과 → 원 경로 그대로.
const amb = buildPush(byId('ambulance'), segments, routes)
assert.equal(amb.rerouted, false)
assert.equal(amb.route, primary)
assert.deepEqual(amb.abandonedPath, [])
assert.deepEqual(amb.segments.map((s) => s.passable), [true, true])

// 중형펌프차는 막힘 → 우회 경로 + 버려진 원 경로.
const pump = buildPush(byId('pump-m'), segments, routes)
assert.equal(pump.rerouted, true)
assert.equal(pump.route, detour)
assert.equal(pump.abandonedPath, primary.path)
assert.deepEqual(pump.segments, [
  { id: 'a', pos: { lat: 1, lng: 1 }, passable: true },
  { id: 'b', pos: { lat: 1, lng: 2 }, passable: false },
])
assert.equal(pump.requiredWidthM, 3.3)
assert.equal(pump.vehicleId, 'pump-m')

// 단말로 나가는 페이로드에 계산 근거(잔여 폭)는 싣지 않는다 — 판정 결과만.
assert.equal('effectiveWidthM' in pump.segments[1], false)

console.log('center.test.js: 모든 검증 통과 ✅')
