// 프레임워크 없이 node로 직접 실행: `node src/lib/reroute.test.js`
import assert from 'node:assert/strict'
import { blockAhead } from './reroute.js'

// o1 통과 가능, o2 통과불가(불법주정차)
const obs = [
  { id: 'o1', distanceM: 210, passable: true },
  { id: 'o2', distanceM: 320, passable: false },
]
const T = 150

assert.equal(blockAhead(obs, 200, T)?.id, 'o2', '막힌 o2 120m 앞 → 감지')
assert.equal(blockAhead(obs, 100, T), null, '220m 앞이면 아직 감지 안 함')
assert.equal(blockAhead(obs, 340, T)?.id, 'o2', '살짝(-20m) 지나쳐도 감지')
assert.equal(blockAhead(obs, 400, T), null, '완전히 지나가면 null')
assert.equal(blockAhead([{ id: 'o1', distanceM: 210, passable: true }], 200, T), null, '통과 가능만 있으면 null')

console.log('reroute.test.js: 모든 검증 통과 ✅')
