import { useEffect, useRef, useState } from 'react'
import { effectiveWidthFromBoxes, isPassable } from '../lib/passable.js'
import { OBSTRUCTION } from '../lib/cocossd.js'

const DETECT_INTERVAL_MS = 300 // throttle: 매 프레임 대신 ~300ms 간격
const SCORE_MIN = 0.5

// COCO-SSD 모델은 앱 전체에서 1회만 로드해 공유.
let modelPromise = null
async function loadModel() {
  if (!modelPromise) {
    modelPromise = (async () => {
      await import('@tensorflow/tfjs')
      const cocoSsd = await import('@tensorflow-models/coco-ssd')
      return cocoSsd.load()
    })()
  }
  return modelPromise
}

export default function CctvPanel({ obstacle, onClose }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const rafRef = useRef(0)
  const lastDetectRef = useRef(0)

  // 'video'(파일) | 'webcam' | 'fallback'(파일 없음 → mock)
  const [source, setSource] = useState('video')
  const [modelStatus, setModelStatus] = useState('loading') // loading | ready | error
  // 라이브 탐지 결과. fallback이면 mock 값 사용.
  const [result, setResult] = useState(null)

  const requiredWidthM = obstacle.requiredWidthM

  // 모델 로드
  useEffect(() => {
    let alive = true
    loadModel()
      .then(() => {
        if (alive) setModelStatus('ready')
      })
      .catch((e) => {
        console.error('COCO-SSD 로드 실패:', e)
        if (alive) setModelStatus('error')
      })
    return () => {
      alive = false
    }
  }, [])

  // 웹캠 소스 연결
  useEffect(() => {
    if (source !== 'webcam') return
    let stream
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        stream = s
        if (videoRef.current) videoRef.current.srcObject = s
      })
      .catch(() => setSource('fallback'))
    return () => stream?.getTracks().forEach((t) => t.stop())
  }, [source])

  // 탐지 루프 (video/webcam & 모델 준비 시)
  useEffect(() => {
    if (modelStatus !== 'ready' || source === 'fallback') return
    let alive = true

    async function tick(ts) {
      if (!alive) return
      const video = videoRef.current
      const canvas = canvasRef.current
      if (video && canvas && video.readyState >= 2 && ts - lastDetectRef.current > DETECT_INTERVAL_MS) {
        lastDetectRef.current = ts
        try {
          const model = await modelPromise
          const preds = (await model.detect(video)).filter(
            (p) => OBSTRUCTION.has(p.class) && p.score >= SCORE_MIN,
          )
          drawBoxes(canvas, video, preds)
          const count = preds.length
          const eff = effectiveWidthFromBoxes(preds, video.videoWidth)
          setResult({ count, effectiveWidthM: eff, passable: isPassable(eff, requiredWidthM), live: true })
        } catch (e) {
          console.error('탐지 오류:', e)
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      alive = false
      cancelAnimationFrame(rafRef.current)
    }
  }, [modelStatus, source, requiredWidthM])

  // 영상 파일 로드 실패 → mock 폴백
  function handleVideoError() {
    if (source === 'video') setSource('fallback')
  }

  // 표시할 판정값: 라이브 결과 우선, 없으면 mock.
  const shown =
    result ??
    {
      count: obstacle.cause.vehicleCount,
      effectiveWidthM: obstacle.cause.effectiveWidthM,
      passable: obstacle.passable,
      live: false,
    }

  return (
    <div className="cctv-backdrop" onClick={onClose}>
      <div className="cctv-panel glass" onClick={(e) => e.stopPropagation()}>
        <div className="cctv-head">
          <div>
            <b>진입로 CCTV 분석</b>
            <small> · {obstacle.distanceM}m 지점</small>
          </div>
          <button className="cctv-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <div className="cctv-stage">
          {source === 'fallback' ? (
            <FallbackFrame obstacle={obstacle} />
          ) : (
            <>
              <video
                ref={videoRef}
                className="cctv-video"
                src={source === 'video' ? obstacle.cctvVideo : undefined}
                autoPlay
                loop
                muted
                playsInline
                onError={handleVideoError}
              />
              <canvas ref={canvasRef} className="cctv-canvas" />
              <span className="cctv-anon-label">분석 전용 뷰 · 원본 영상 비표시</span>
            </>
          )}

          {modelStatus === 'loading' && source !== 'fallback' && (
            <div className="cctv-loading">모델 로딩 중…</div>
          )}
        </div>

        <div className={`cctv-verdict ${shown.passable ? 'ok' : 'blocked'}`}>
          <div className="verdict-stats">
            <span>탐지 장애물 <b>{shown.count}</b>개</span>
            <span>유효폭 <b>{shown.effectiveWidthM}</b>m</span>
            <span>필요폭 <b>{requiredWidthM}</b>m</span>
          </div>
          <div className="verdict-line">
            {shown.passable ? '✅ 소방차 진입 가능' : '⛔ 소방차 진입 불가'}
            <small>
              {' '}· 원인: {obstacle.cause.type} {shown.live ? '(실시간 분석)' : '(사전 데이터)'}
            </small>
          </div>
          {!shown.passable && <div className="verdict-reroute">↩ 우회 경로 안내로 전환됨</div>}
        </div>

        <div className="cctv-actions">
          {source !== 'webcam' && modelStatus === 'ready' && (
            <button onClick={() => setSource('webcam')}>웹캠으로 실시간 테스트</button>
          )}
          {source === 'webcam' && <button onClick={() => setSource('video')}>CCTV 영상으로 복귀</button>}
        </div>

        <div className="cctv-privacy">
          🔒 원본 영상은 관제센터 밖으로 나가지 않습니다 · 통과 상태값만 전송(번호판·얼굴 등 개인정보 비반출)
        </div>
      </div>
    </div>
  )
}

// 캔버스를 video 표시 크기에 맞추고 예측 박스를 스케일해 그림.
function drawBoxes(canvas, video, preds) {
  const w = video.clientWidth
  const h = video.clientHeight
  if (canvas.width !== w) canvas.width = w
  if (canvas.height !== h) canvas.height = h
  const sx = w / (video.videoWidth || w)
  const sy = h / (video.videoHeight || h)
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, w, h)
  ctx.lineWidth = 2
  ctx.strokeStyle = '#38bdf8'
  ctx.fillStyle = 'rgba(56,189,248,0.85)'
  ctx.font = '12px system-ui'
  for (const p of preds) {
    const [x, y, bw, bh] = p.bbox
    ctx.strokeRect(x * sx, y * sy, bw * sx, bh * sy)
    ctx.fillRect(x * sx, y * sy - 14, 46, 14)
    ctx.fillStyle = '#00121f'
    ctx.fillText(p.class, x * sx + 3, y * sy - 3)
    ctx.fillStyle = 'rgba(56,189,248,0.85)'
  }
}

// 영상 파일이 없을 때: mock 박스를 얹은 플레이스홀더 프레임.
function FallbackFrame({ obstacle }) {
  const boxes = Array.from({ length: obstacle.cause.vehicleCount }, (_, i) => i)
  return (
    <div className="cctv-fallback">
      <span className="cctv-fallback-label">CCTV · 사전 분석 결과 (영상 없음)</span>
      {boxes.map((i) => (
        <div key={i} className="fb-box" style={{ left: `${12 + i * 26}%`, bottom: `${18 + (i % 2) * 12}%` }}>
          car
        </div>
      ))}
    </div>
  )
}
