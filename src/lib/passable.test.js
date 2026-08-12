// 프레임워크 없이 node로 직접 실행: `node src/lib/passable.test.js`
import assert from 'node:assert/strict'
import { isPassable, estimateEffectiveWidth } from './passable.js'

// 경계값: 필요폭과 같으면 통과, 조금이라도 좁으면 불가.
assert.equal(isPassable(2.5, 2.5), true, '2.5 == 2.5 → 통과')
assert.equal(isPassable(2.4, 2.5), false, '2.4 < 2.5 → 불가')
assert.equal(isPassable(3.0, 2.5), true, '3.0 > 2.5 → 통과')

// 차량 수 → 유효폭 추정 (base 5.0, 대당 1.0 잠식).
assert.equal(estimateEffectiveWidth(0), 5.0)
assert.equal(estimateEffectiveWidth(3), 2.0)
assert.equal(estimateEffectiveWidth(10), 0, '음수 방지')

console.log('passable.test.js: 모든 검증 통과 ✅')
