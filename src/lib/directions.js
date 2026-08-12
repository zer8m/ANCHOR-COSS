// Kakao Mobility Directions(자동차 길찾기) 호출/파싱.
// dev 프록시 경유(/kakao-navi). REST 키는 vite.config 프록시가 헤더로 주입.

// sections[].roads[].vertexes(평면 [lng,lat,lng,lat,...]) → [{lat,lng}, ...]
function roadsToPath(sections = []) {
  const path = []
  for (const s of sections) {
    for (const road of s.roads || []) {
      const v = road.vertexes || []
      for (let i = 0; i < v.length; i += 2) {
        path.push({ lat: v[i + 1], lng: v[i] })
      }
    }
  }
  return path
}

// sections[].roads[] → 구간별 교통상태 세그먼트 [{path:[{lat,lng}...], state}]
// state: Kakao traffic_state (0 정보없음 · 1 원활 · 2 서행 · 3 지체 · 4 정체).
export function roadsToSegments(sections = []) {
  const segs = []
  for (const s of sections) {
    for (const road of s.roads || []) {
      const v = road.vertexes || []
      const path = []
      for (let i = 0; i < v.length; i += 2) path.push({ lat: v[i + 1], lng: v[i] })
      if (path.length >= 2) segs.push({ path, state: road.traffic_state ?? 0, speed: road.traffic_speed ?? null })
    }
  }
  return segs
}

// sections[].guides[] → 턴 안내 [{name, guidance, lat, lng, distance, type}]
function sectionsToGuides(sections = []) {
  const guides = []
  for (const s of sections) {
    for (const g of s.guides || []) {
      guides.push({
        name: g.name || '',
        guidance: g.guidance || '',
        lat: g.y,
        lng: g.x,
        distance: g.distance ?? 0,
        type: g.type ?? 0,
      })
    }
  }
  return guides
}

// origin/destination: {lat, lng}. waypoints: [{lat,lng}...] (위험구간 회피용 경유지).
// 성공 시 경로 배열(0=추천, 1=대안) 반환, 실패 시 throw.
export async function getRoutes(origin, destination, waypoints = []) {
  const o = `${origin.lng},${origin.lat}`
  const d = `${destination.lng},${destination.lat}`
  const wp = waypoints.length
    ? `&waypoints=${waypoints.map((w) => `${w.lng},${w.lat}`).join('|')}`
    : ''
  // 긴급출동 → 최소시간(TIME) 경로. (RECOMMEND는 이 구간에서 더 길고 느렸음)
  const url = `/kakao-navi/v1/directions?origin=${o}&destination=${d}${wp}&priority=TIME&alternatives=true`

  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()

  const ok = (data.routes || []).filter((r) => r.result_code === 0)
  if (!ok.length) {
    throw new Error(data.routes?.[0]?.result_msg || 'no route')
  }
  return ok.map((r) => ({
    path: roadsToPath(r.sections),
    segments: roadsToSegments(r.sections),
    guides: sectionsToGuides(r.sections),
    distanceM: r.summary?.distance ?? null,
    durationSec: r.summary?.duration ?? null,
  }))
}
