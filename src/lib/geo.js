// 지오메트리 순수 유틸 (React/DOM 의존 없음 → node 스크립트·테스트에서 공용).

export function haversine(a, b) {
  const R = 6371000
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(s))
}

// 경로 위 누적거리 distM 지점의 좌표(두 점 사이 선형 보간). 경로 끝을 넘으면 마지막 점.
export function pointAtDistance(path, distM) {
  let acc = 0
  for (let i = 1; i < path.length; i++) {
    const p = path[i - 1]
    const q = path[i]
    const seg = haversine(p, q)
    if (acc + seg >= distM) {
      const f = seg ? (distM - acc) / seg : 0
      return { lat: p.lat + (q.lat - p.lat) * f, lng: p.lng + (q.lng - p.lng) * f }
    }
    acc += seg
  }
  return path[path.length - 1] ?? null
}

// 점 p에서 경로(선분들)까지의 최소 거리(m). p를 원점으로 한 국소 평면 근사.
// 꼭짓점이 아니라 선분에 투영 — 긴 직선 도로는 꼭짓점 간격이 넓어 꼭짓점 기준이면
// "경로가 p를 지나는데 멀다"고 오판한다.
export function minDistanceToPath(path, p) {
  const mLat = 111320
  const mLng = 111320 * Math.cos((p.lat * Math.PI) / 180)
  const xy = (q) => [(q.lng - p.lng) * mLng, (q.lat - p.lat) * mLat]
  let best = Infinity
  for (let i = 1; i < path.length; i++) {
    const [ax, ay] = xy(path[i - 1])
    const [bx, by] = xy(path[i])
    const dx = bx - ax
    const dy = by - ay
    const len2 = dx * dx + dy * dy
    const t = len2 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0
    best = Math.min(best, Math.hypot(ax + t * dx, ay + t * dy))
  }
  return best
}

// 막힌 지점(distanceM)을 경로에서 찾아, 진행방향 수직으로 offsetM 떨어진 경유지 반환.
// 이 경유지로 길찾기하면 막힌 구간을 피해 도는 우회 경로가 나옴. (Kakao는 특정 도로 제외 미지원 → 경유지로 우회 유도)
export function detourWaypoint(path, distanceM, offsetM = 350) {
  if (path.length < 2) return null
  let acc = 0
  let i = 1
  for (; i < path.length; i++) {
    acc += haversine(path[i - 1], path[i])
    if (acc >= distanceM) break
  }
  if (i >= path.length) i = path.length - 1
  const a = path[i - 1]
  const b = path[i]
  const mLat = 111320
  const mLng = 111320 * Math.cos((b.lat * Math.PI) / 180)
  const dx = (b.lng - a.lng) * mLng // 동(m)
  const dy = (b.lat - a.lat) * mLat // 북(m)
  const len = Math.hypot(dx, dy) || 1
  const ox = (-dy / len) * offsetM // 수직(좌) 동성분
  const oy = (dx / len) * offsetM // 수직(좌) 북성분
  return { lat: b.lat + oy / mLat, lng: b.lng + ox / mLng }
}
