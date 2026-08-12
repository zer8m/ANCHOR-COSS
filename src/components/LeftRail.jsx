// 좌측 아이콘 레일 (레퍼런스의 엣지 아이콘). 장식이 아니라 전부 실제 동작.
export default function LeftRail({
  showFacilities,
  onToggleFacilities,
  onOpenCctv,
  cctvCount,
  onBack,
  showCrew,
  onToggleCrew,
  crewAlert,
}) {
  return (
    <nav className="rail glass" aria-label="빠른 작업">
      <button className="rail-badge num" onClick={onBack} title="출동 브리핑으로">
        119
      </button>

      <div className="rail-sep" />

      <button
        className={`rail-btn ${showCrew ? 'on' : ''}`}
        onClick={onToggleCrew}
        aria-pressed={showCrew}
        title="대원 실시간 관제"
      >
        👥
        {crewAlert > 0 && <span className="rail-dot alarm">{crewAlert}</span>}
      </button>

      <button
        className={`rail-btn ${showFacilities ? 'on' : ''}`}
        onClick={onToggleFacilities}
        aria-pressed={showFacilities}
        title="소화전·소방통로 표시"
      >
        🚒
      </button>

      <button
        className="rail-btn"
        onClick={onOpenCctv}
        disabled={!cctvCount}
        title="진입로 CCTV 분석"
      >
        📹
        {cctvCount > 0 && <span className="rail-dot">{cctvCount}</span>}
      </button>
    </nav>
  )
}
