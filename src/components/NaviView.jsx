import { useEffect, useMemo, useState } from 'react'
import { useKakaoLoader, Map, Polyline, CustomOverlayMap } from 'react-kakao-maps-sdk'
import { dispatch, obstacles } from '../data/scenario.js'
import { VEHICLES, DEFAULT_VEHICLE_ID } from '../data/vehicles.js'
import pushedRoutes from '../data/pushedRoutes.js'
import { buildPush } from '../lib/center.js'
import { haversine } from '../lib/geo.js'
import VehiclePanel from './VehiclePanel.jsx'

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY
const SPEED_LIMIT = 50
const PLAYBACK_RATE = 6 // 데모 배속 (실제 소요시간을 이만큼 압축해 재생). 속도계·ETA는 실제값 유지.

// 소방차 긴급주행 속도 모델 (calibration 노브).
// 설계 최고속도 80~113km/h는 차량 스펙. 도심 실주행 평균은 40~70km/h 유지, 5분 내 도착 목표.
// 경로 평균 속도에 긴급 계수(신호우선·차로양보로 일반 통행보다 빠름)를 곱해 밴드로 clamp.
const TRUCK_AVG_MIN = 40
const TRUCK_AVG_MAX = 70
const EMERGENCY_BOOST = 2.2

const fmtDist = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`)
const pad2 = (n) => String(n).padStart(2, '0')
const arrowFor = (t = '') =>
  t.includes('좌회전') ? '↰' : t.includes('우회전') ? '↱' : t.includes('유턴') ? '⤾' : t.includes('도착') ? '⚑' : '↑'

// 소방 출동 단말 — 센터가 밀어준 판정 결과·경로(push)를 지도 위에 표출만 한다.
// 검출·판정·경로 계산은 하지 않는다(buildPush = 센터 mock). 계산 과정(유효폭 등)도 띄우지 않는다.
export default function NaviView({ onExit }) {
  const [loading] = useKakaoLoader({ appkey: KAKAO_KEY ?? '', url: 'https://dapi.kakao.com/v2/maps/sdk.js' })
  const [vehicleId, setVehicleId] = useState(DEFAULT_VEHICLE_ID)
  const [panelOpen, setPanelOpen] = useState(false)
  // 경로 위 이동 거리(m). 어느 경로의 진행값인지 함께 들고 있어, 경로가 바뀐 첫 렌더에서 옛 값이 새 경로에 대입되지 않는다.
  const [progress, setProgress] = useState({ route: null, m: 0 })

  const vehicle = VEHICLES.find((v) => v.id === vehicleId)
  // 출동 차종이 정해지면 센터가 판정 + 경로를 한 번에 내려준다(지령 시점 1회 push).
  const push = useMemo(() => buildPush(vehicle, obstacles, pushedRoutes), [vehicle])
  const route = push.route
  const travelled = progress.route === route ? progress.m : 0
  const path = route.path
  const guides = route.guides
  const blockedCount = push.segments.filter((s) => !s.passable).length

  const { guideIdx, cum, total, truckAvgKmh, fireDurationSec } = useMemo(() => {
    const p = route.path
    const cum = [0]
    for (let i = 1; i < p.length; i++) cum[i] = cum[i - 1] + haversine(p[i - 1], p[i])
    const guideIdx = route.guides.map((g) => {
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
    const routeAvgKmh = route.durationSec ? (total / route.durationSec) * 3.6 : 0
    const truckAvgKmh = Math.min(TRUCK_AVG_MAX, Math.max(TRUCK_AVG_MIN, Math.round(routeAvgKmh * EMERGENCY_BOOST)))
    const fireDurationSec = total / (truckAvgKmh / 3.6)
    return { guideIdx, cum, total, truckAvgKmh, fireDurationSec }
  }, [route])

  // 긴급주행 소요시간(fireDurationSec)에 맞춰 경과 시간 비례로 경로를 전진.
  // 차종 변경으로 경로가 바뀌면 출발점부터 다시 재생(주행 중 경로 전환은 없음 — 지령 시점 1회 push).
  useEffect(() => {
    if (total <= 0) return
    const dur = (fireDurationSec * 1000) / PLAYBACK_RATE
    const start = performance.now()
    let raf
    const step = (now) => {
      const t = Math.min(1, (now - start) / dur)
      setProgress({ route, m: total * t })
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [route, total, fireDurationSec])

  const dist = Math.min(travelled, total) // 현재까지 이동 거리(m)
  // dist(m) → 경로 위 현재 지점 보간 + 마지막으로 지난 점 인덱스(idx)
  let hi = cum.findIndex((c) => c >= dist)
  if (hi < 0) hi = path.length - 1
  const idx = Math.max(0, hi - 1)
  const segLen = cum[hi] - cum[idx] || 1
  const f = Math.min(1, Math.max(0, (dist - cum[idx]) / segLen))
  const pos = {
    lat: path[idx].lat + (path[hi].lat - path[idx].lat) * f,
    lng: path[idx].lng + (path[hi].lng - path[idx].lng) * f,
  }
  const remainM = Math.max(0, total - dist)
  const remainSec = total > 0 ? fireDurationSec * (remainM / total) : 0
  const arrival = new Date(Date.now() + remainSec * 1000)
  const arrived = dist >= total - 0.5

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

  return (
    <div className="tnavi">
      {/* 메인 스테이지: 2D 지도 */}
      <div className="tnavi-stage">
        {loading ? (
          <div className="tnavi-msg">지도 불러오는 중…</div>
        ) : (
          <Map
            center={pos}
            level={3}
            style={{ width: '100%', height: '100%' }}
            draggable={false}
            zoomable={false}
            onCreate={(map) => map.relayout()}
          >
            {/* 진입 불가로 버려진 원 경로(점선) */}
            {push.abandonedPath.length > 1 && (
              <Polyline path={push.abandonedPath} strokeWeight={7} strokeColor="#9aa3ad" strokeOpacity={0.9} strokeStyle="shortdash" />
            )}
            {/* 안내 경로 */}
            <Polyline path={path} strokeWeight={11} strokeColor="#2f6fed" strokeOpacity={0.9} />
            {/* 이미 지난 구간은 회색으로 덮음 */}
            <Polyline path={path.slice(0, idx + 1)} strokeWeight={11} strokeColor="#b9bfc7" strokeOpacity={0.9} />
            {/* CCTV 판정 구간 (막힘=빨강) */}
            {push.segments.map((s) => (
              <CustomOverlayMap key={s.id} position={s.pos} yAnchor={0.5} xAnchor={0.5}>
                <div className={`tnavi-obsmk ${s.passable ? '' : 'block'}`} />
              </CustomOverlayMap>
            ))}
            <CustomOverlayMap position={pos} yAnchor={0.5} xAnchor={0.5}>
              <div className="tnavi-carmk" />
            </CustomOverlayMap>
          </Map>
        )}
      </div>

      {/* 센터 판정 결과 (상단 중앙). 계산 근거는 표시하지 않는다. */}
      {push.rerouted && (
        <div className="tnavi-warning" role="status">
          <span className="tnavi-warning-icon">⚠️</span>
          <div className="tnavi-warning-body">
            <b>진입 불가 구간 {blockedCount}곳</b>
            <p>관제센터 판정 · 우회 경로로 안내합니다</p>
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

      {/* 출동 차종 칩 (우상단) → 진입 기준·제원 패널 */}
      <button className="tnavi-vchip" onClick={() => setPanelOpen((v) => !v)} aria-expanded={panelOpen}>
        <b>{vehicle.name}</b>
        <span>필요폭 {push.requiredWidthM.toFixed(1)}m</span>
      </button>
      {panelOpen && (
        <VehiclePanel
          vehicleId={vehicleId}
          onSelect={(id) => {
            setVehicleId(id)
            setPanelOpen(false)
          }}
          onClose={() => setPanelOpen(false)}
        />
      )}

      {/* 속도 (하단 중앙) */}
      <div className="tnavi-speedhud">
        <div className="tnavi-speed">
          <b>{speed}</b>
          <span>km/h</span>
        </div>
        <div className="tnavi-limit">{SPEED_LIMIT}</div>
      </div>

      {/* ETA (좌하단) */}
      <div className="tnavi-eta">
        <div><b>{`${arrival.getHours()}:${pad2(arrival.getMinutes())}`}</b><span>도착</span></div>
        <div><b>{Math.round(remainSec / 60)}</b><span>분</span></div>
        <div><b>{(remainM / 1000).toFixed(1)}</b><span>km</span></div>
      </div>

      {/* 종료 (우하단) */}
      <div className="tnavi-controls">
        <button className="tnavi-exit" onClick={onExit}>종료</button>
      </div>
    </div>
  )
}
