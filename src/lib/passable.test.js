// 프레임워크 없이 node로 직접 실행: `node src/lib/passable.test.js`
import assert from 'node:assert/strict'
import { isPassable } from './passable.js'

// 경계값: 필요폭과 같으면 통과, 조금이라도 좁으면 불가.
assert.equal(isPassable(2.5, 2.5), true, '2.5 == 2.5 → 통과')
assert.equal(isPassable(2.4, 2.5), false, '2.4 < 2.5 → 불가')
assert.equal(isPassable(3.0, 2.5), true, '3.0 > 2.5 → 통과')

console.log('passable.test.js: 모든 검증 통과 ✅')
