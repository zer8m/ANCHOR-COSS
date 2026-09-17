// 프레임워크 없이 node로 직접 실행: `node src/lib/geo.test.js`
import assert from 'node:assert/strict'
import { haversine, pointAtDistance, minDistanceToPath, nearestOnPath, detourWaypoint } from './geo.js'

const near = (actual, expected, tol, msg) =>
  assert.ok(Math.abs(actual - expected) <= tol, `${msg}: ${actual} ≉ ${expected}`)

// 위도 0.001° ≈ 111.2m
const a = { lat: 36.36, lng: 127.35 }
const b = { lat: 36.361, lng: 127.35 }
near(haversine(a, b), 111.2, 0.5, 'haversine')

// 경로 위 거리 → 좌표 보간. 끝을 넘으면 마지막 점.
near(pointAtDistance([a, b], 55.6).lat, 36.3605, 0.00001, '중간점')
assert.deepEqual(pointAtDistance([a, b], 9999), b)
assert.equal(pointAtDistance([], 10), null)

// 점-경로 최소거리는 꼭짓점이 아니라 선분 기준이어야 한다:
// 꼭짓점이 111m 간격인 직선 경로의 한가운데 옆 50m 지점 → 50m (꼭짓점 기준이면 ~75m로 틀림).
const mLng = 111320 * Math.cos((36.3605 * Math.PI) / 180)
const side = { lat: 36.3605, lng: 127.35 + 50 / mLng }
near(minDistanceToPath([a, b], side), 50, 1, '선분 투영')
near(minDistanceToPath([a, b], { lat: 36.3605, lng: 127.35 }), 0, 0.5, '경로 위의 점')

// 점 → 경로 투영: 경로 한가운데 옆 50m 점은 누적거리 ~55.6m, 투영점은 경로 위, 떨어진 거리 50m.
const near1 = nearestOnPath([a, b], side)
near(near1.distM, 55.6, 0.5, '투영 누적거리')
near(near1.offM, 50, 1, '투영 거리')
near(near1.point.lng, 127.35, 0.00001, '투영점은 경로 위')

// 우회 경유지: 진행방향(북) 기준 수직으로 offset만큼 떨어진 점.
const wp = detourWaypoint([a, b], 100, 130)
near(haversine(wp, b), 130, 2, '경유지 offset')
near(wp.lat, b.lat, 0.00001, '수직 방향(위도 동일)')

console.log('geo.test.js: 모든 검증 통과 ✅')
