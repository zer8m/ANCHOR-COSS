// 개발 시 1회 실행: dev 서버 프록시(/kakao-navi)로 Kakao 길찾기를 호출해 고정 경로 fixture를 만든다.
// 런타임 단말은 이 fixture만 읽는다(= "센터가 밀어준 경로"). 실행 전 `npm run dev`가 떠 있어야 함.
//   node scripts/capture-routes.mjs
import { writeFileSync } from 'node:fs'
import { getRoutes } from '../src/lib/directions.js'
import { detourWaypoint, pointAtDistance, minDistanceToPath } from '../src/lib/geo.js'
import { dispatch, obstacles } from '../src/data/scenario.js'

const BASE = 'http://localhost:5173'
const AVOID_ID = 'o2' // 우회 경로가 피해야 하는 구간
const AVOID_MIN_M = 40 // 우회 경로가 막힌 지점에서 최소 이만큼 떨어져야 "피했다"로 인정
const OFFSETS_M = [130, -130, 200, -200, 300, -300]

// 교통 세그먼트(segments)는 캡처 시점 스냅샷이라 싣지 않는다.
const slim = (r) => ({ path: r.path, guides: r.guides, distanceM: r.distanceM, durationSec: r.durationSec })

const primary = (await getRoutes(dispatch.currentPos, dispatch.destination, [], BASE))[0]
const segmentPos = Object.fromEntries(obstacles.map((o) => [o.id, pointAtDistance(primary.path, o.distanceM)]))
const avoid = obstacles.find((o) => o.id === AVOID_ID)

const cands = []
for (const off of OFFSETS_M) {
  const wp = detourWaypoint(primary.path, avoid.distanceM, off)
  try {
    const r = (await getRoutes(dispatch.currentPos, dispatch.destination, [wp], BASE))[0]
    const clearM = minDistanceToPath(r.path, segmentPos[AVOID_ID])
    console.log(`offset ${off}m → ${r.distanceM}m, 막힌 지점과 ${Math.round(clearM)}m`)
    if (clearM >= AVOID_MIN_M) cands.push(r)
  } catch (e) {
    console.log(`offset ${off}m → 실패: ${e.message}`)
  }
}
if (!cands.length) throw new Error(`막힌 지점(${AVOID_ID})을 ${AVOID_MIN_M}m 이상 피하는 우회 경로 없음`)
const detour = cands.reduce((a, b) => (b.distanceM < a.distanceM ? b : a))

const out = {
  capturedAt: new Date().toISOString(),
  primary: slim(primary),
  detour: { ...slim(detour), avoids: [AVOID_ID] },
  segmentPos,
}
writeFileSync(
  new URL('../src/data/pushedRoutes.js', import.meta.url),
  '// scripts/capture-routes.mjs 산출물 — 직접 수정하지 말고 스크립트를 다시 실행할 것.\n' +
    `export default ${JSON.stringify(out)}\n`,
)
console.log(`저장: primary ${primary.distanceM}m / detour ${detour.distanceM}m`)
