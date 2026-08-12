// 소방차 통과 판정 로직. 우회 결정의 근거가 되는 유일한 핵심 로직.

// 표준 골목 도로폭(m). 라이브 탐지 시 유효폭 추정의 기준.
const BASE_ROAD_WIDTH_M = 5.0
// 주정차 차량 1대가 잠식하는 유효폭(m) 근사치.
// ponytail: 픽셀→미터 정밀 변환 대신 대수 기반 근사. 정밀 필요시 원근 보정 추가.
const OCCUPY_PER_VEHICLE_M = 1.0

// 탐지된 차량 수 → 유효 도로폭(m) 추정 (대수 기반, 폴백용).
export function estimateEffectiveWidth(vehicleCount, baseWidthM = BASE_ROAD_WIDTH_M) {
  const w = baseWidthM - vehicleCount * OCCUPY_PER_VEHICLE_M
  return Math.max(0, Math.round(w * 10) / 10)
}

// 탐지 박스 기반 유효 도로폭(m) 추정 — 대수가 아니라 차량이 프레임 가로폭을
// 실제로 얼마나 차지하는지(겹침 제외 union)로 계산해 정확도를 높임.
// preds: [{bbox:[x,y,w,h]}], frameW: 영상 가로 픽셀.
// ponytail: 원근·차선폭 보정은 생략한 근사. 정밀화하려면 호모그래피/캘리브레이션 필요.
export function effectiveWidthFromBoxes(preds, frameW, baseWidthM = BASE_ROAD_WIDTH_M) {
  if (!frameW || !preds || !preds.length) return baseWidthM
  // 차량 bbox의 x-구간을 union으로 합쳐 실제 점유 픽셀 계산(겹침 중복 제거)
  const iv = preds.map((p) => [p.bbox[0], p.bbox[0] + p.bbox[2]]).sort((a, b) => a[0] - b[0])
  let covered = 0
  let curS = iv[0][0]
  let curE = iv[0][1]
  for (let i = 1; i < iv.length; i++) {
    const [s, e] = iv[i]
    if (s > curE) {
      covered += curE - curS
      curS = s
      curE = e
    } else {
      curE = Math.max(curE, e)
    }
  }
  covered += curE - curS
  const frac = Math.min(1, covered / frameW)
  return Math.max(0, Math.round(baseWidthM * (1 - frac) * 10) / 10)
}

// 통과 가능 여부. 유효폭이 소방차 필요폭 이상이면 통과.
export function isPassable(effectiveWidthM, requiredWidthM) {
  return effectiveWidthM >= requiredWidthM
}
