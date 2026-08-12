import { useState } from 'react'
import Icon from './Icon.jsx'

const WD = ['일', '월', '화', '수', '목', '금', '토']

// 근무 일정 캘린더 팝오버. value/onSelect: { y, m(0-based), d }.
export default function BriefCalendar({ value, onSelect, onClose }) {
  const [view, setView] = useState({ y: value.y, m: value.m })

  const first = new Date(view.y, view.m, 1).getDay()
  const days = new Date(view.y, view.m + 1, 0).getDate()
  const cells = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]

  const shift = (delta) => {
    const d = new Date(view.y, view.m + delta, 1)
    setView({ y: d.getFullYear(), m: d.getMonth() })
  }

  return (
    <div className="cal-pop glass" onClick={(e) => e.stopPropagation()}>
      <div className="cal-head">
        <button className="cal-nav" onClick={() => shift(-1)} aria-label="이전 달"><Icon name="chevron-left" size={16} /></button>
        <b>{view.y}. {String(view.m + 1).padStart(2, '0')}</b>
        <button className="cal-nav" onClick={() => shift(1)} aria-label="다음 달"><Icon name="chevron-right" size={16} /></button>
      </div>
      <div className="cal-grid">
        {WD.map((w) => (
          <span key={w} className="cal-wd">{w}</span>
        ))}
        {cells.map((d, i) =>
          d === null ? (
            <span key={`e${i}`} />
          ) : (
            <button
              key={d}
              className={`cal-day ${value.y === view.y && value.m === view.m && value.d === d ? 'sel' : ''}`}
              onClick={() => {
                onSelect({ y: view.y, m: view.m, d })
                onClose()
              }}
            >
              {d}
            </button>
          ),
        )}
      </div>
    </div>
  )
}
