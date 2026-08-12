import { dispatch } from '../data/scenario.js'

// 상단 글래스 헤더: 출동 정체성(화재유형·목적지) + 가장 임박한 장애물 경보.
// 거리·ETA 숫자는 하단 계기판 바가 담당(중복 제거).
export default function DispatchHeader({ nextObstacle }) {
  return (
    <header className="top-hud">
      <div className="hud-dispatch glass">
        <span className="hud-tag">출동</span>
        <div>
          <div className="hud-incident">{dispatch.incident}</div>
          <div className="hud-dest">{dispatch.destination.name}</div>
        </div>
      </div>

      {nextObstacle && (
        <div className={`hud-alert glass ${nextObstacle.severity}`}>
          <div className="hud-alert-dist"><span className="num">{nextObstacle.distanceM}</span>m 앞</div>
          <div className="hud-alert-body">
            {nextObstacle.severity === 'blocked' ? '⛔ 진입 불가' : '⚠ 진입로 협소'}
            <small>
              {nextObstacle.cause.type} {nextObstacle.cause.vehicleCount}대 · 유효폭{' '}
              {nextObstacle.cause.effectiveWidthM}m
            </small>
          </div>
        </div>
      )}
    </header>
  )
}
