// 개발 시 1회 실행: dev 서버 프록시(/kakao-navi)로 Kakao 길찾기를 호출해 고정 경로 fixture를 만든다.
// 런타임 단말은 이 fixture만 읽는다(= "센터가 밀어준 경로"). 실행 전 `npm run dev`가 떠 있어야 함.
//   node scripts/capture-routes.mjs
import { writeFileSync } from 'node:fs'
import { getRoutes } from '../src/lib/directions.js'
import { detourWaypoint, nearestOnPath, minDistanceToPath } from '../src/lib/geo.js'
import { dispatch, obstacles, AVOID_MIN_M } from '../src/data/scenario.js'

const BASE = 'http://localhost:5173'
const AVOID_ID = 'o1' // 우회 경로가 피해야 하는 구간
const SNAP_MAX_M = 30 // 판정 구간 좌표가 원 경로에서 이보다 멀면 경로가 그 구간을 지나지 않는 것 → 중단
const OFFSETS_M = [80, -80, 130, -130, 200, -200, 300, -300]

// 교통 세그먼트(segments)는 캡처 시점 스냅샷이라 싣지 않는다.
// 우회 유도용 경유지는 센터 내부 사정이라 단말 턴 안내에서 뺀다('경유지' guide 제외).
const slim = (r) => ({
  path: r.path,
  guides: r.guides.filter((g) => g.guidance !== '경유지'),
  distanceM: r.distanceM,
  durationSec: r.durationSec,
})

const primary = (
  await getRoutes(dispatch.currentPos, dispatch.destination, [], BASE).catch((e) => {
    throw new Error(`${BASE} 호출 실패(${e.message}) — dev 서버(npm run dev)가 이 포트에 떠 있는지 확인`)
  })
)[0]
// 판정 구간(obstacles[].pos)을 원 경로에 투영. 마커 위치 = 투영점.
const snapped = Object.fromEntries(obstacles.map((o) => [o.id, nearestOnPath(primary.path, o.pos)]))
for (const [id, n] of Object.entries(snapped)) {
  console.log(`${id}: 원 경로 ${Math.round(n.distM)}m 지점, 지정 좌표와 ${Math.round(n.offM)}m`)
  if (n.offM > SNAP_MAX_M) throw new Error(`${id}: 원 경로가 이 구간을 지나지 않음(${Math.round(n.offM)}m) — scenario.js의 pos를 경로 위로 옮길 것`)
}
const segmentPos = Object.fromEntries(Object.entries(snapped).map(([id, n]) => [id, n.point]))
const avoidAtM = snapped[AVOID_ID].distM

const cands = []
for (const off of OFFSETS_M) {
  const wp = detourWaypoint(primary.path, avoidAtM, off)
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
