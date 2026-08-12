import { dispatch } from '../data/scenario.js'

// 하단 중앙 상태바 (레퍼런스의 미디어플레이어 자리): 속도 · 다음 안내 · 도착.
// distanceM/etaMin은 현재 활성 경로(기본/우회)의 실제 Kakao 값. etaMin은 우회 소요를 이미 포함.
export default function BottomBar({ nextObstacle, blocked, distanceM, etaMin, extraMin, live }) {
  const eta = etaMin // 활성 경로 실측(우회 시 이미 우회 소요 포함)
  const guideDist = blocked ? blocked.distanceM : nextObstacle ? nextObstacle.distanceM : distanceM

  return (
    <div className="bottombar glass">
      <div className="bb-gauge">
        <b className="num">{dispatch.speedKmh}</b>
        <span>km/h</span>
      </div>

      <div className="bb-divider" />

      <div className={`bb-guide ${blocked ? 'reroute' : ''}`}>
        <div className="bb-guide-icon">{blocked ? '↩' : '↑'}</div>
        <div className="bb-guide-text">
          <div className="bb-guide-main">
            {blocked ? '우회 경로 진행' : '직진'}
            <span className="bb-guide-dist num">{guideDist}m</span>
          </div>
          <div className="bb-guide-sub">
            {blocked
              ? `${blocked.distanceM}m 앞 ${blocked.cause.type} ${blocked.cause.vehicleCount}대 · 통과 불가${extraMin > 0 ? ` · 우회 +${extraMin}분` : ' · 우회'}`
              : dispatch.destination.name}
          </div>
        </div>
      </div>

      <div className="bb-divider" />

      <div className="bb-gauge">
        <b className="num">{eta}</b>
        <span>
          분 · <span className="num">{distanceM}</span>m
        </span>
        {live && <span className="bb-live" title="Kakao 실시간 경로">● 실측</span>}
      </div>
    </div>
  )
}
