import { hazardZones } from '../data/scenario.js'

const HAZARD_LABEL = { market: '전통시장', alley: '좁은 골목', deadend: '막다른 길' }

// 좌측 글래스 카드: 안전 경로 요약 + 구간 통과상태(관제 AI 시뮬레이션) 토글.
// 카드 클릭 → CCTV. 토글 → 통과/막힘 전환(경로 재계산 유발).
export default function ObstacleList({ obstacles, selectedId, onSelect, onToggleBlocked }) {
  const sorted = [...obstacles].sort((a, b) => a.distanceM - b.distanceM)

  return (
    <aside className="side">
      <div className="safe-card glass">
        <div className="safe-head">
          <span className="safe-icon">🛡</span>
          <b>안전 최적 경로</b>
        </div>
        <div className="safe-sub">위험구간 {hazardZones.length}곳 회피</div>
        <div className="safe-tags">
          {hazardZones.map((z) => (
            <span key={z.id} className="safe-tag">{HAZARD_LABEL[z.type]}</span>
          ))}
        </div>
      </div>

      <div className="side-card glass">
        <h3 className="side-title">
          구간 통과상태
          <span className="side-sim">관제 AI 시뮬레이션</span>
        </h3>
        <ul className="obs-list">
          {sorted.map((o) => (
            <li key={o.id}>
              <div
                className={`obs-card ${o.severity} ${selectedId === o.id ? 'sel' : ''}`}
                onClick={() => onSelect(o.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelect(o.id)}
              >
                <div className="obs-row">
                  <span className="obs-dist num">{o.distanceM}m</span>
                  <button
                    className={`obs-toggle ${o.passable ? 'pass' : 'block'}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onToggleBlocked(o.id)
                    }}
                    aria-pressed={!o.passable}
                    title="통과/막힘 전환"
                  >
                    {o.passable ? '통과' : '막힘'}
                  </button>
                </div>
                <div className="obs-cause">
                  {o.cause.type} {o.cause.vehicleCount}대 · 유효폭 {o.cause.effectiveWidthM}m
                  <small> (필요 {o.requiredWidthM}m)</small>
                </div>
                {o.cctvVideo && <div className="obs-cctv">📹 CCTV 분석 보기</div>}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}
