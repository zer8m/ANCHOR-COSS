// 프레임워크 없이 node로 직접 실행: `node src/lib/directions.test.js`
import assert from 'node:assert/strict'
import { roadsToSegments } from './directions.js'

// vertexes는 평면 [lng,lat,lng,lat,...] — lat/lng 순서 스왑 확인.
const sections = [
  {
    roads: [
      { traffic_state: 4, vertexes: [127.1, 36.1, 127.2, 36.2] }, // 정체 구간(2점)
      { traffic_state: 1, vertexes: [127.2, 36.2, 127.3, 36.3, 127.4, 36.4] }, // 원활(3점)
      { vertexes: [127.4, 36.4] }, // 1점뿐 → 세그먼트 제외
    ],
  },
]

const segs = roadsToSegments(sections)
assert.equal(segs.length, 2, '2점 이상 구간만 세그먼트로')
assert.deepEqual(segs[0].path[0], { lat: 36.1, lng: 127.1 }, 'lng/lat 스왑')
assert.equal(segs[0].state, 4, 'traffic_state 보존')
assert.equal(segs[1].path.length, 3, '3점 구간')
// traffic_state 누락 시 0(정보없음)로 폴백
assert.equal(roadsToSegments([{ roads: [{ vertexes: [127, 36, 128, 37] }] }])[0].state, 0, 'state 누락→0')

console.log('directions.test.js: 모든 검증 통과 ✅')
