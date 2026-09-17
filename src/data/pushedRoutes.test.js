// 프레임워크 없이 node로 직접 실행: `node src/data/pushedRoutes.test.js`
// 실제 데이터(시나리오 + 제원표 + fixture)가 서로 모순 없는지 검증.
import assert from 'node:assert/strict'
import routes from './pushedRoutes.js'
import { obstacles } from './scenario.js'
import { VEHICLES } from './vehicles.js'
import { buildPush } from '../lib/center.js'
import { minDistanceToPath } from '../lib/geo.js'

assert.ok(routes.primary.path.length >= 2 && routes.detour.path.length >= 2, '경로가 비어 있음')
for (const o of obstacles) assert.ok(routes.segmentPos[o.id], `segmentPos.${o.id} 없음`)

// 우회 경로는 피한다고 선언한 구간을 실제로 피해야 한다.
for (const id of routes.detour.avoids) {
  assert.ok(minDistanceToPath(routes.detour.path, routes.segmentPos[id]) >= 40, `우회 경로가 ${id}를 지남`)
}

// 어떤 차종이든, 막힌 구간은 전부 우회 경로가 피하는 구간이어야 한다(막힌 곳을 지나는 "우회로" 방지).
for (const v of VEHICLES) {
  const push = buildPush(v, obstacles, routes)
  for (const s of push.segments.filter((x) => !x.passable)) {
    assert.ok(routes.detour.avoids.includes(s.id), `${v.name}: ${s.id}가 막혔는데 우회 경로가 피하지 않음`)
  }
}

// 데모 핵심: 같은 골목에서 차종에 따라 판정이 갈린다.
const push = (id) => buildPush(VEHICLES.find((v) => v.id === id), obstacles, routes)
assert.equal(push('ambulance').rerouted, false, '구급차는 원 경로')
assert.equal(push('pump-m').rerouted, true, '중형펌프차는 우회')

console.log('pushedRoutes.test.js: 모든 검증 통과 ✅')
