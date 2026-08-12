import { useKakaoLoader, Map, Circle, CustomOverlayMap } from 'react-kakao-maps-sdk'
import { chronicSegments, reportPeriod, dispatch } from '../data/scenario.js'

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY
const TYPE_LABEL = { market: '상가밀집', alley: '좁은 골목', backroad: '이면도로', deadend: '막다른 길' }
const TREND = { up: { s: '▲', c: 'up' }, down: { s: '▼', c: 'down' }, flat: { s: '―', c: 'flat' } }

// 상습 진입곤란 구간 통계 대시보드(Report). 라이트 톤(관제/행정 화면).
export default function Report({ onBack, onNav }) {
  const sorted = [...chronicSegments].sort((a, b) => b.count - a.count)
  const total = sorted.length
  const monthly = sorted.reduce((s, x) => s + x.count, 0)
  const avgDelay = (sorted.reduce((s, x) => s + x.avgDelayMin, 0) / total).toFixed(1)
  const maxCount = sorted[0]?.count || 1

  return (
    <div className="report">
      <header className="brief-top">
        <div className="brief-logo">
          <span className="brief-mark num">119</span>
          <span className="brief-word">출동 지령 시스템</span>
        </div>
        <nav className="brief-pills">
          <button className="pill" onClick={onBack}>브리핑</button>
          <button className="pill" onClick={onNav}>경로</button>
          <button className="pill on">통계</button>
        </nav>
        <div className="brief-station">
          <span>🚩 {dispatch.station}</span>
        </div>
      </header>

      <div className="rp-titlebar">
        <div>
          <h1 className="rp-title">상습 진입곤란 구간 통계</h1>
          <p className="rp-sub">{dispatch.station} 관할 · {reportPeriod}</p>
        </div>
        <span className="rp-note">경로 구간 상태값 이벤트 축적 기반</span>
      </div>

      <div className="rp-kpis">
        <Kpi label="상습 구간" value={total} unit="곳" />
        <Kpi label="월 진입지연" value={monthly} unit="건" />
        <Kpi label="평균 지연" value={avgDelay} unit="분" />
        <Kpi label="최다 발생" value={sorted[0]?.count} unit="건" sub={sorted[0]?.name} />
      </div>

      <div className="rp-body">
        <div className="rp-table glass">
          <div className="rp-table-head">
            <span>#</span>
            <span>구간</span>
            <span>유형</span>
            <span className="rp-num-col">발생</span>
            <span className="rp-num-col">평균지연</span>
            <span className="rp-num-col">추세</span>
          </div>
          {sorted.map((s, i) => (
            <div className="rp-row" key={s.id}>
              <span className="rp-rank num">{i + 1}</span>
              <span className="rp-name">{s.name}</span>
              <span className="rp-type">{TYPE_LABEL[s.type]}</span>
              <span className="rp-num-col">
                <span className="rp-bar-wrap">
                  <span className="rp-bar" style={{ width: `${(s.count / maxCount) * 100}%` }} />
                </span>
                <b className="num">{s.count}</b>
              </span>
              <span className="rp-num-col num">{s.avgDelayMin}분</span>
              <span className={`rp-num-col rp-trend ${TREND[s.trend].c}`}>{TREND[s.trend].s}</span>
            </div>
          ))}
        </div>

        <div className="rp-map glass">
          <div className="rp-map-label">발생 히트맵</div>
          <Heatmap maxCount={maxCount} />
        </div>
      </div>
    </div>
  )
}

function Kpi({ label, value, unit, sub }) {
  return (
    <div className="rp-kpi glass">
      <div className="rp-kpi-label">{label}</div>
      <div className="rp-kpi-value">
        <b className="num">{value}</b>
        <span>{unit}</span>
      </div>
      {sub && <div className="rp-kpi-sub">{sub}</div>}
    </div>
  )
}

function Heatmap({ maxCount }) {
  const [loading, error] = useKakaoLoader({ appkey: KAKAO_KEY ?? '', url: 'https://dapi.kakao.com/v2/maps/sdk.js' })
  const center = { lat: 37.5634, lng: 126.9255 }

  if (!KAKAO_KEY || error) {
    return <div className="rp-map-fallback">지도 키를 확인하세요</div>
  }

  return (
    <Map center={center} level={5} style={{ width: '100%', height: '100%', borderRadius: '14px' }} draggable>
      {loading && null}
      {chronicSegments.map((s) => {
        const intensity = s.count / maxCount
        return (
          <Circle
            key={s.id}
            center={s.pos}
            radius={40 + intensity * 130}
            strokeWeight={1}
            strokeColor="#e5484d"
            strokeOpacity={0.5}
            fillColor="#e5484d"
            fillOpacity={0.15 + intensity * 0.4}
          />
        )
      })}
      {chronicSegments.slice(0, 3).map((s) => (
        <CustomOverlayMap key={`${s.id}-l`} position={s.pos} yAnchor={0.5} xAnchor={0.5}>
          <div className="rp-hot num">{s.count}</div>
        </CustomOverlayMap>
      ))}
    </Map>
  )
}
