import { useEffect, useMemo, useRef, useState } from 'react'
import { useKakaoLoader, Map, Polyline, CustomOverlayMap } from 'react-kakao-maps-sdk'
import { dispatch, obstacles, controlLog } from '../data/scenario.js'
import { getRoutes } from '../lib/directions.js'
import { blockAhead } from '../lib/reroute.js'
import CctvPanel from './CctvPanel.jsx'
import ObstacleCam from './ObstacleCam.jsx'

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY
const SPEED_LIMIT = 50
const PLAYBACK_RATE = 6 // 데모 배속 (실제 소요시간을 이만큼 압축해 재생). 속도계·ETA는 실제값 유지.
const REROUTE_ARM_M = 700 // 막힌 지점 이만큼 앞에서 우회 경로를 미리 계산(정지 없이 대비)
const REROUTE_SWAP_M = 350 // 막힌 지점 이만큼 앞(anchor) 도달 시 우회로로 전환

// 소방차 긴급주행 속도 모델 (calibration 노브).
// 설계 최고속도 80~113km/h는 차량 스펙. 도심 실주행 평균은 40~70km/h 유지, 5분 내 도착 목표.
// 실시간 교통 평균에 긴급 계수(신호우선·차로양보로 일반 통행보다 빠름)를 곱해 밴드로 clamp.
const TRUCK_AVG_MIN = 40
const TRUCK_AVG_MAX = 70
const EMERGENCY_BOOST = 2.2

function haversine(a, b) {
  const R = 6371000
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(s))
}
const fmtDist = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`)
const pad2 = (n) => String(n).padStart(2, '0')
const arrowFor = (t = '') =>
  t.includes('좌회전') ? '↰' : t.includes('우회전') ? '↱' : t.includes('유턴') ? '⤾' : t.includes('도착') ? '⚑' : '↑'

// 혼잡 레벨 → 색상 (1 원활·2 서행·3 지체·4 정체).
const TRAFFIC_COLORS = { 1: '#2fa84f', 2: '#f4c430', 3: '#f08a24', 4: '#e5352b' }
const trafficColor = (lvl) => TRAFFIC_COLORS[lvl] ?? '#2fa84f'
// Kakao traffic_state는 speed와 모순돼(예: 65km/h인데 정체) 신뢰 불가 → 실측 통행속도(km/h)로 판정.
const speedToLevel = (kmh) => (kmh == null ? 1 : kmh >= 40 ? 1 : kmh >= 25 ? 2 : kmh >= 15 ? 3 : 4)
const TRAFFIC_LEGEND = [[1, '원활'], [2, '서행'], [3, '지체'], [4, '정체']]

// 막힌 지점(distanceM)을 경로에서 찾아, 진행방향 수직으로 offsetM 떨어진 경유지 반환.
// 이 경유지로 길찾기하면 막힌 구간을 피해 도는 우회 경로가 나옴. (Kakao는 특정 도로 제외 미지원 → 경유지로 우회 유도)
function detourWaypoint(path, distanceM, offsetM = 350) {
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

// 경로(path) 위 dist(m) 지점의 좌표를 두 점 사이 보간으로 반환.
function pointOnPath(path, cum, dist) {
  if (!path.length) return null
  let hi = cum.findIndex((c) => c >= dist)
  if (hi < 0) hi = path.length - 1
  const lo = Math.max(0, hi - 1)
  const segLen = cum[hi] - cum[lo] || 1
  const f = Math.min(1, Math.max(0, (dist - cum[lo]) / segLen))
  return {
    lat: path[lo].lat + (path[hi].lat - path[lo].lat) * f,
    lng: path[lo].lng + (path[hi].lng - path[lo].lng) * f,
  }
}

const initStatus = Object.fromEntries(
  obstacles.map((o) => [o.id, { count: o.cause.vehicleCount, effWidth: o.cause.effectiveWidthM, passable: o.passable, live: false }]),
)

// 소방 진입 내비 — 2D 지도 위에 속도·턴 안내·CCTV 통과상태·ETA HUD를 겹쳐 표시.
export default function NaviView({ onExit }) {
  const [loading] = useKakaoLoader({ appkey: KAKAO_KEY ?? '', url: 'https://dapi.kakao.com/v2/maps/sdk.js' })
  const [route, setRoute] = useState(null)
  const [rerouted, setRerouted] = useState(false) // 우회 전환 완료 여부
  const [pendingRoute, setPendingRoute] = useState(null) // 미리 계산해둔 우회 경로
  const armedRef = useRef(false) // 우회 경로 pre-fetch 시작 여부(1회)
  const [warning, setWarning] = useState(null) // CCTV 감지 경고 메시지
  const [travelled, setTravelled] = useState(0) // 경로 위 이동 거리(m)
  const [status, setStatus] = useState(initStatus)
  const [selectedId, setSelectedId] = useState(null)
  const [comm, setComm] = useState(true) // 진입 시 관제실 자동 연결 → 무전 기록 바로 표시
  const [commMsgs, setCommMsgs] = useState([]) // 흘러나온 무전 기록(최신순, 실시간 timestamp)

  useEffect(() => {
    let alive = true
    getRoutes(dispatch.currentPos, dispatch.destination)
      .then((rs) => {
        if (!alive) return
        setRoute(rs[0])
      })
      .catch((e) => console.warn('경로 실패:', e.message))
    return () => {
      alive = false
    }
  }, [])


  // 관제실 연결 시 무전 기록을 순차적으로 흘려보냄(최신 항목이 맨 위, 실시간 시각).
  useEffect(() => {
    if (!comm || commMsgs.length >= controlLog.length) return
    const id = setTimeout(() => {
      const next = controlLog[commMsgs.length]
      const t = new Date().toLocaleTimeString('ko-KR', { hour12: false })
      setCommMsgs((prev) => [{ ...next, t }, ...prev])
    }, commMsgs.length === 0 ? 300 : 2200)
    return () => clearTimeout(id)
  }, [comm, commMsgs])

  const onStatus = (id, s) => setStatus((prev) => ({ ...prev, [id]: s }))
  const path = route?.path ?? []
  const segments = route?.segments ?? []
  const guides = route?.guides ?? []

  const { guideIdx, cum, total, truckAvgKmh, fireDurationSec } = useMemo(() => {
    const p = route?.path ?? []
    if (!p.length) return { guideIdx: [], cum: [], total: 0, truckAvgKmh: 0, fireDurationSec: 0 }
    const cum = [0]
    for (let i = 1; i < p.length; i++) cum[i] = cum[i - 1] + haversine(p[i - 1], p[i])
    const guideIdx = (route.guides || []).map((g) => {
      let best = 0
      let bestD = Infinity
      for (let i = 0; i < p.length; i++) {
        const d = haversine(p[i], g)
        if (d < bestD) {
          bestD = d
          best = i
        }
      }
      return best
    })
    const total = cum[cum.length - 1]
    // 실시간 교통 평균(km/h) → 긴급주행 계수 → 40~70 밴드로 유지.
    const routeAvgKmh = route.durationSec ? (total / route.durationSec) * 3.6 : 0
    const truckAvgKmh = Math.min(TRUCK_AVG_MAX, Math.max(TRUCK_AVG_MIN, Math.round(routeAvgKmh * EMERGENCY_BOOST)))
    const fireDurationSec = truckAvgKmh > 0 ? total / (truckAvgKmh / 3.6) : route.durationSec || 0
    return { guideIdx, cum, total, truckAvgKmh, fireDurationSec }
  }, [route])

  // 소방차 긴급주행 소요시간(fireDurationSec)에 맞춰 경과 시간 비례로 경로를 전진.
  // 경로가 우회로로 바뀌어도 현재 진행 지점(travelled)부터 이어서 재생(원점 순간이동 방지).
  useEffect(() => {
    if (!route || total <= 0 || !fireDurationSec) return
    const dur = (fireDurationSec * 1000) / PLAYBACK_RATE
    const startFrac = Math.min(1, travelled / total)
    const start = performance.now() - startFrac * dur
    let raf
    const step = (now) => {
      const t = Math.min(1, (now - start) / dur)
      setTravelled(total * t)
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // travelled는 재개 지점 계산용으로 최초 실행 시에만 읽음 — 의도적으로 deps 제외.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route, total])

  // 불법주정차(통과불가) 지점에 접근하면:
  //  ① ARM: 멀리서(REROUTE_ARM_M) anchor 지점 기준 우회 경로를 미리 계산해 둠 (정지 없이 대비).
  //  ② SWAP: anchor(REROUTE_SWAP_M 앞)에 도달하면 준비된 우회로로 즉시 전환 + 경고.
  useEffect(() => {
    if (rerouted || !path.length || total <= 0) return
    const dist = Math.min(travelled, total)
    const blocked = blockAhead(obstacles, dist, REROUTE_ARM_M)
    if (!blocked) return
    const swapAtM = Math.max(0, blocked.distanceM - REROUTE_SWAP_M)

    // ① 우회 경로 pre-fetch (최초 1회). anchor에서 시작하는, 막힌 지점 회피 경로.
    if (!armedRef.current) {
      armedRef.current = true
      const anchor = pointOnPath(path, cum, swapAtM)
      const wps = [130, -130].map((off) => detourWaypoint(path, blocked.distanceM, off)).filter(Boolean)
      Promise.all(
        wps.map((wp) =>
          getRoutes(anchor, dispatch.destination, [wp])
            .then((rs) => rs[0])
            .catch(() => null),
        ),
      )
        .then((cands) => {
          const valid = cands.filter(Boolean)
          if (valid.length) setPendingRoute(valid.reduce((a, b) => (b.distanceM < a.distanceM ? b : a)))
        })
        .catch((e) => console.warn('우회 pre-fetch 실패:', e.message))
    }

    // ② anchor 도달 + 우회로 준비 완료 → 정지 없이 즉시 전환.
    if (pendingRoute && dist >= swapAtM) {
      const s = status[blocked.id]
      const live = s?.live && s.count > 0
      setWarning({
        distanceM: blocked.distanceM,
        cause: blocked.cause?.type ?? '불법주정차',
        count: live ? s.count : blocked.cause.vehicleCount,
        effWidth: live ? s.effWidth : blocked.cause.effectiveWidthM,
        requiredWidthM: blocked.requiredWidthM,
      })
      setRoute(pendingRoute) // anchor에서 시작하는 우회 경로
      setTravelled(0) // 새 경로 처음부터 (= 현재 위치, 튀지 않음)
      setRerouted(true)
    }
    // travelled가 매 프레임 갱신 → 최신 path/cum closure 확보. path/cum은 deps 제외.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [travelled, status, rerouted, pendingRoute, total])

  // 경고 메시지는 8초 후 자동 해제 (우회 안내 배너는 CCTV 패널에 계속 유지).
  useEffect(() => {
    if (!warning) return
    const t = setTimeout(() => setWarning(null), 8000)
    return () => clearTimeout(t)
  }, [warning])

  const liveObstacles = obstacles.map((o) => {
    const s = status[o.id]
    // 라이브 탐지가 실제로 차량을 잡았을 때만 그 값 사용, 아니면 시나리오 확정값으로 폴백.
    // (오탐으로 "0개인데 막힘" 같은 모순 방지)
    const useLive = s.live && s.count > 0
    const count = useLive ? s.count : o.cause.vehicleCount
    const effWidth = useLive ? s.effWidth : o.cause.effectiveWidthM
    // 시나리오상 통과불가 지점은 항상 막힘 (우회 트리거와 일관).
    const passable = o.passable ? (useLive ? s.passable : true) : false
    return { ...o, passable, count, effWidth, live: useLive }
  })
  const anyBlocked = liveObstacles.some((o) => !o.passable)
  const selected = obstacles.find((o) => o.id === selectedId) ?? null

  const ready = route && path.length
  const dist = Math.min(travelled, total) // 현재까지 이동 거리(m)
  // dist(m) → 경로 위 현재 지점 보간 + 마지막으로 지난 점 인덱스(idx)
  let idx = 0
  let pos = dispatch.currentPos
  if (ready) {
    let hi = cum.findIndex((c) => c >= dist)
    if (hi < 0) hi = path.length - 1
    const lo = Math.max(0, hi - 1)
    idx = lo
    const segLen = cum[hi] - cum[lo] || 1
    const f = Math.min(1, Math.max(0, (dist - cum[lo]) / segLen))
    pos = {
      lat: path[lo].lat + (path[hi].lat - path[lo].lat) * f,
      lng: path[lo].lng + (path[hi].lng - path[lo].lng) * f,
    }
  }
  const remainM = ready ? Math.max(0, total - dist) : 0
  const remainSec = ready && total > 0 ? fireDurationSec * (remainM / total) : 0
  const arrival = new Date(Date.now() + remainSec * 1000)
  const arrived = ready && dist >= total - 0.5

  let activeGuide = -1
  for (let i = 0; i < guideIdx.length; i++) {
    if (guideIdx[i] > idx) {
      activeGuide = i
      break
    }
  }
  const nextGuide = activeGuide >= 0 ? guides[activeGuide] : null
  const turnDist = nextGuide ? Math.max(0, cum[guideIdx[activeGuide]] - dist) : 0
  const turnLabel = arrived ? '목적지 도착' : nextGuide?.guidance || nextGuide?.name || '직진'
  const turnRoad = arrived ? dispatch.destination.name : nextGuide?.name || dispatch.destination.name
  // 소방차 긴급주행 유지 평균 속도(40~70 밴드). 도착 시 0.
  const speed = arrived ? 0 : truckAvgKmh

  // 장애물을 거리(distanceM)만큼 경로 위 지점에 배치 (막힘=빨강 마커)
  const obstacleMarkers = ready
    ? liveObstacles.map((o) => {
        let i = cum.findIndex((c) => c >= o.distanceM)
        if (i < 0) i = path.length - 1
        return { id: o.id, pos: path[i], passable: o.passable }
      })
    : []

  return (
    <div className="tnavi">
      {obstacles.map((o) => (
        <ObstacleCam key={o.id} obstacle={o} onStatus={onStatus} />
      ))}

      {/* 메인 스테이지: 2D 지도 */}
      <div className="tnavi-stage">
        {loading ? (
          <div className="tnavi-msg">지도 불러오는 중…</div>
        ) : (
          // 지도 타일은 경로와 무관하게 항상 표시. 경로가 준비되면 polyline·마커를 얹음.
          <Map
            center={pos}
            level={3}
            style={{ width: '100%', height: '100%' }}
            draggable={false}
            zoomable={false}
            onCreate={(map) => map.relayout()}
          >
            {ready && (
              <>
                {/* 구간별 실시간 교통상태 색칠 (정체=빨강) */}
                {segments.map((seg, i) => (
                  <Polyline key={i} path={seg.path} strokeWeight={11} strokeColor={trafficColor(speedToLevel(seg.speed))} strokeOpacity={0.9} />
                ))}
                {/* 이미 지난 구간은 회색으로 덮음 */}
                <Polyline path={path.slice(0, idx + 1)} strokeWeight={11} strokeColor="#b9bfc7" strokeOpacity={0.9} />
                {obstacleMarkers.map((m) => (
                  <CustomOverlayMap key={m.id} position={m.pos} yAnchor={0.5} xAnchor={0.5}>
                    <div className={`tnavi-obsmk ${m.passable ? '' : 'block'}`} />
                  </CustomOverlayMap>
                ))}
              </>
            )}
            <CustomOverlayMap position={pos} yAnchor={0.5} xAnchor={0.5}>
              <div className="tnavi-carmk" />
            </CustomOverlayMap>
          </Map>
        )}
        {!ready && !loading && <div className="tnavi-loadchip">경로 계산 중…</div>}
      </div>

      {/* 교통상태 범례 (상단 중앙) */}
      {ready && (
        <div className="tnavi-legend">
          {TRAFFIC_LEGEND.map(([s, label]) => (
            <span key={s}>
              <i style={{ background: trafficColor(s) }} />
              {label}
            </span>
          ))}
        </div>
      )}

      {/* CCTV 감지 경고 (상단 중앙, 8초 후 자동 해제) */}
      {warning && (
        <div className="tnavi-warning" role="alert">
          <span className="tnavi-warning-icon">⚠️</span>
          <div className="tnavi-warning-body">
            <b>CCTV 감지 · 진입 불가</b>
            <p>
              {warning.distanceM}m 지점 {warning.cause} · 차량 {warning.count}대 · 유효폭 {warning.effWidth}m &lt; 필요{' '}
              {warning.requiredWidthM}m → 우회 경로로 안내합니다
            </p>
          </div>
        </div>
      )}

      {/* 턴 카드 (좌상단) */}
      <div className="tnavi-turncard">
        <div className="tnavi-turncard-top">
          <span className="tnavi-turncard-arrow">{arrowFor(turnLabel)}</span>
          <span className="tnavi-turncard-dist">{arrived ? '도착' : fmtDist(turnDist)}</span>
        </div>
        <div className="tnavi-turncard-text">{turnRoad}</div>
      </div>

      {/* 속도 (하단 중앙) */}
      <div className="tnavi-speedhud">
        <div className="tnavi-speed">
          <b>{speed}</b>
          <span>km/h</span>
        </div>
        <div className="tnavi-limit">{SPEED_LIMIT}</div>
      </div>

      {/* CCTV 구간 통과상태 (우상단) */}
      <div className="tnavi-cctv">
        <div className="tnavi-cctv-head">
          구간 통과상태 <span>● CCTV 실시간</span>
        </div>
        {liveObstacles
          .slice()
          .sort((a, b) => a.distanceM - b.distanceM)
          .map((o) => (
            <button
              key={o.id}
              className={`tnavi-cctv-item ${o.passable ? '' : 'block'}`}
              onClick={() => setSelectedId(o.id)}
            >
              <span className="num">{o.distanceM}m</span>
              <span className="tnavi-cctv-info">장애물 {o.count}개 · 유효폭 {o.effWidth}m</span>
              <span className={`tnavi-cctv-badge ${o.passable ? 'pass' : 'block'}`}>{o.passable ? '통과' : '막힘'}</span>
            </button>
          ))}
        {rerouted ? (
          <div className="tnavi-cctv-reroute">↩ 통과 불가 · 우회 경로로 안내 중</div>
        ) : anyBlocked ? (
          <div className="tnavi-cctv-reroute">⚠ 전방 통과 불가 · 우회 경로 대기</div>
        ) : null}
      </div>

      {/* ETA (좌하단) */}
      <div className="tnavi-eta">
        <div><b>{`${arrival.getHours()}:${pad2(arrival.getMinutes())}`}</b><span>도착</span></div>
        <div><b>{Math.round(remainSec / 60)}</b><span>분</span></div>
        <div><b>{(remainM / 1000).toFixed(1)}</b><span>km</span></div>
      </div>

      {/* 관제실 연락 + 종료 (우하단) */}
      <div className="tnavi-controls">
        <div className="tnavi-comm">
          <button className={`tnavi-comm-btn ${comm ? 'on' : ''}`} onClick={() => setComm((v) => !v)}>
            {comm ? '관제실 연결됨 · 무전 CH.3' : '관제실 연락'}
          </button>
          {comm && (
            <div className="tnavi-comm-log">
              <div className="tnavi-comm-status">
                <span className="tnavi-comm-dot" /> 무전 채널 개방 · 상황실과 통신 중
              </div>
              <ul className="tnavi-comm-lines">
                {commMsgs.map((m, i) => (
                  <li key={commMsgs.length - i} className={m.who === '상황실' ? 'from-ops' : 'from-crew'}>
                    <span className="cl-t">{m.t}</span>
                    <span className="cl-who">{m.who}</span>
                    <span className="cl-txt">{m.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <button className="tnavi-exit" onClick={onExit}>종료</button>
      </div>

      {selected && <CctvPanel obstacle={selected} onClose={() => setSelectedId(null)} />}
    </div>
  )
}
