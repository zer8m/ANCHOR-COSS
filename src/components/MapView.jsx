import { useKakaoLoader, Map, Polyline, Circle, CustomOverlayMap } from 'react-kakao-maps-sdk'
import { dispatch, routes, facilities, hazardZones, crew } from '../data/scenario.js'

const HAZARD_LABEL = { market: '전통시장', alley: '좁은 골목', deadend: '막다른 길' }

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY

// 지도 중심: 현재위치와 목적지의 중간.
const CENTER = {
  lat: (dispatch.currentPos.lat + dispatch.destination.lat) / 2,
  lng: (dispatch.currentPos.lng + dispatch.destination.lng) / 2,
}

function toPath(coords) {
  return coords.map(([lat, lng]) => ({ lat, lng }))
}

export default function MapView(props) {
  // 키가 없으면 로더 훅을 아예 호출하지 않는다(무한 재시도 방지).
  if (!KAKAO_KEY) {
    return (
      <MapFallback title="Kakao 지도 키가 필요합니다">
        <code>.env</code> 파일에 <code>VITE_KAKAO_MAP_KEY</code> 를 설정하세요.
        <br />
        Kakao Developers → 앱 생성 → JavaScript 키 발급, 플랫폼에{' '}
        <code>http://localhost:5173</code> 등록.
      </MapFallback>
    )
  }
  return <KakaoMap {...props} />
}

function KakaoMap({ obstacles, primaryPath, originalPath, showFacilities, selectedId, onSelectObstacle }) {
  // url을 https로 고정: http://localhost 에서 protocol-relative(//)가
  // http://dapi.kakao.com 로 요청돼 즉시 실패(onerror)하는 문제 방지.
  const [loading, error] = useKakaoLoader({
    appkey: KAKAO_KEY,
    url: 'https://dapi.kakao.com/v2/maps/sdk.js',
  })

  if (error) {
    return <MapFallback title="지도를 불러오지 못했습니다">키·도메인 등록을 확인하고 새로고침하세요.</MapFallback>
  }

  // 실제 Kakao 경로(있으면) 아니면 mock 폴백.
  const primary = primaryPath ?? toPath(routes.primary)

  return (
    <Map center={CENTER} level={3} style={{ width: '100%', height: '100%' }} draggable>
      {loading && null}

      {/* 원래(막힘) 경로: 우회 중일 때 대비용 빨강 점선 */}
      {originalPath && (
        <Polyline
          path={originalPath}
          strokeWeight={5}
          strokeColor="#ff5d5d"
          strokeOpacity={0.7}
          strokeStyle="shortdash"
        />
      )}

      {/* 현재 안내 경로: teal 발광 3겹 = 굵은 글로우 + 본선 + 밝은 코어 */}
      <Polyline path={primary} strokeWeight={16} strokeColor="#22d3ee" strokeOpacity={0.18} />
      <Polyline path={primary} strokeWeight={8} strokeColor="#2dd4bf" strokeOpacity={0.85} />
      <Polyline path={primary} strokeWeight={3} strokeColor="#d6fff8" strokeOpacity={0.95} />

      {/* 위험구간(전통시장·좁은골목·막다른길): 회피 대상, 빨간 원 + 라벨 */}
      {hazardZones.map((z) => (
        <Circle
          key={z.id}
          center={z.pos}
          radius={z.radius}
          strokeWeight={2}
          strokeColor="#ff5d5d"
          strokeOpacity={0.8}
          strokeStyle="shortdash"
          fillColor="#ff5d5d"
          fillOpacity={0.16}
        />
      ))}
      {hazardZones.map((z) => (
        <CustomOverlayMap key={`${z.id}-l`} position={z.pos} yAnchor={0.5} xAnchor={0.5}>
          <div className="mk-hazard">⚠ {HAZARD_LABEL[z.type]}</div>
        </CustomOverlayMap>
      ))}

      {/* 출동 대원 실시간 위치 */}
      {crew.map((c) => (
        <CustomOverlayMap key={c.id} position={c.pos} yAnchor={1} xAnchor={0.5}>
          <div className={`mk-crew ${c.status} ${c.comm === 'lost' ? 'lost' : ''}`}>
            <span className="mk-crew-dot" />
            {c.name}
          </div>
        </CustomOverlayMap>
      ))}

      {/* 현재 위치: 진행방향 콘 마커 */}
      <CustomOverlayMap position={dispatch.currentPos} yAnchor={0.5} xAnchor={0.5}>
        <div className="mk-self">
          <div className="mk-self-pulse" />
          <div className="mk-self-rot" style={{ transform: `rotate(${dispatch.currentPos.heading}deg)` }}>
            <div className="mk-self-cone" />
          </div>
          <div className="mk-self-dot" />
        </div>
      </CustomOverlayMap>

      {/* 목적지 */}
      <CustomOverlayMap position={dispatch.destination} yAnchor={1} xAnchor={0.5}>
        <div className="mk-dest">🔥 목적지</div>
      </CustomOverlayMap>

      {/* 장애물 마커 */}
      {obstacles.map((o) => (
        <CustomOverlayMap key={o.id} position={o.pos} yAnchor={1} xAnchor={0.5}>
          <button
            className={`mk-obs ${o.severity} ${selectedId === o.id ? 'sel' : ''}`}
            onClick={() => onSelectObstacle(o.id)}
          >
            {o.severity === 'blocked' ? '⛔' : '⚠'} {o.cause.effectiveWidthM}m
          </button>
        </CustomOverlayMap>
      ))}

      {/* 소화전·소방통로 (레일 토글) */}
      {showFacilities && facilities.map((f) => (
        <CustomOverlayMap key={f.id} position={f.pos} yAnchor={0.5} xAnchor={0.5}>
          <div className={`mk-fac ${f.type}`} title={f.type === 'hydrant' ? '소화전' : '소방통로'}>
            {f.type === 'hydrant' ? '🚒' : '🅿'}
          </div>
        </CustomOverlayMap>
      ))}
    </Map>
  )
}

function MapFallback({ title, children }) {
  return (
    <div className="map-fallback">
      <div className="map-fallback-card glass">
        <h2>{title}</h2>
        <p>{children}</p>
      </div>
    </div>
  )
}
