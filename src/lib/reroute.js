// 우회 판단 순수 로직 (React/DOM 의존 없음 → node로 직접 테스트 가능).

// 통과불가(passable=false)로 확정된, 차량 앞쪽(triggerM 이내) 장애물을 반환. 없으면 null.
// dist: 현재 이동거리(m). 살짝 지나친 지점(-30m)까지 허용해 감지 타이밍 오차를 흡수.
// 판정은 시나리오 확정값(o.passable)을 기준으로 해 데모에서 항상 안정적으로 트리거됨.
export function blockAhead(obstacles, dist, triggerM) {
  return (
    obstacles.find((o) => {
      if (o.passable) return false
      const ahead = o.distanceM - dist
      return ahead <= triggerM && ahead > -30
    }) ?? null
  )
}
