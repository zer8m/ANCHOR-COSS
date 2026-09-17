// 소방차 통과 판정. 우회 결정의 근거가 되는 핵심 로직.
// 잔여 폭 산출(기준물 픽셀 스케일 환산)은 관제센터 프로그램 쪽 몫 — 여기서는 폭 대조만 한다.

// 통과 가능 여부. 잔여 폭이 차종별 필요 통과폭 이상이면 통과.
export function isPassable(effectiveWidthM, requiredWidthM) {
  return effectiveWidthM >= requiredWidthM
}
