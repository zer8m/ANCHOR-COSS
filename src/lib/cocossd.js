// COCO-SSD 모델 로딩/차량 탐지 공용 (앱 전체 1회 로드).
let modelPromise = null
export function loadModel() {
  if (!modelPromise) {
    modelPromise = (async () => {
      await import('@tensorflow/tfjs')
      const cocoSsd = await import('@tensorflow-models/coco-ssd')
      return cocoSsd.load()
    })()
  }
  return modelPromise
}

// 진입 방해물: 차량 + 정적 장애물(나무=화분, 벤치, 소화전, 자전거 등)
const VEHICLE = new Set(['car', 'truck', 'bus', 'motorcycle', 'bicycle'])
export const OBSTRUCTION = new Set([...VEHICLE, 'bench', 'potted plant', 'fire hydrant', 'chair', 'suitcase', 'umbrella'])
const SCORE_MIN = 0.5

// video/이미지에서 진입 방해물(차량+정적 장애물) bounding box 배열 반환.
export async function detectVehicles(el) {
  const model = await modelPromise
  if (!model) return []
  const preds = await model.detect(el)
  return preds.filter((p) => OBSTRUCTION.has(p.class) && p.score >= SCORE_MIN)
}
export const isVehicle = (cls) => VEHICLE.has(cls)
