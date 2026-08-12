import { useEffect, useRef } from 'react'
import { loadModel, detectVehicles } from '../lib/cocossd.js'
import { effectiveWidthFromBoxes, isPassable } from '../lib/passable.js'

const INTERVAL_MS = 900

// 숨김 CCTV 분석기: 한 지점의 CCTV 영상을 COCO-SSD로 계속 분석해 통과/막힘 상태를 콜백.
// 영상이 없으면(파일 미존재) 사전 데이터로 폴백.
export default function ObstacleCam({ obstacle, onStatus }) {
  const videoRef = useRef(null)

  function fallback() {
    onStatus(obstacle.id, {
      count: obstacle.cause.vehicleCount,
      effWidth: obstacle.cause.effectiveWidthM,
      passable: obstacle.passable,
      live: false,
    })
  }

  useEffect(() => {
    let alive = true
    let ready = false
    let raf = 0
    let last = 0
    loadModel().then(() => (ready = true)).catch(() => {})

    function tick(ts) {
      if (!alive) return
      const v = videoRef.current
      if (ready && v && v.readyState >= 2 && v.videoWidth > 0 && ts - last > INTERVAL_MS) {
        last = ts
        detectVehicles(v)
          .then((preds) => {
            if (!alive) return
            const count = preds.length
            // 박스 기반 유효폭(차량이 도로 가로폭을 실제로 차지하는 비율)
            const eff = effectiveWidthFromBoxes(preds, v.videoWidth)
            onStatus(obstacle.id, { count, effWidth: eff, passable: isPassable(eff, obstacle.requiredWidthM), live: true })
          })
          .catch(() => {})
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      alive = false
      cancelAnimationFrame(raf)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [obstacle.id])

  return (
    <video
      ref={videoRef}
      src={obstacle.cctvVideo || undefined}
      autoPlay
      loop
      muted
      playsInline
      onError={fallback}
      style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none' }}
    />
  )
}
