import { useEffect, useState } from 'react'
import { crew as initialCrew } from '../data/scenario.js'

const STATUS_LABEL = { ok: '정상', warn: '경고', danger: '위험' }

// 대원 실시간 관제 패널. 공기호흡기 잔량·심박을 주기적으로 갱신해 라이브 느낌(mock).
// 통신 두절 대원도 마지막 위치·상태를 계속 추적 표시.
export default function CrewPanel({ onClose }) {
  const [crew, setCrew] = useState(initialCrew)

  useEffect(() => {
    const t = setInterval(() => {
      setCrew((prev) =>
        prev.map((c) => {
          // 통신 두절 대원은 갱신 없음(마지막 값 유지).
          if (c.comm === 'lost') return c
          const airPct = Math.max(0, c.airPct - (c.status === 'warn' ? 1 : 0.4))
          const hr = Math.min(190, Math.max(70, c.hr + Math.round((airPct % 3) - 1)))
          const status = airPct < 20 ? 'danger' : airPct < 40 ? 'warn' : c.status === 'danger' ? 'danger' : 'ok'
          return { ...c, airPct: Math.round(airPct * 10) / 10, hr, status }
        }),
      )
    }, 2000)
    return () => clearInterval(t)
  }, [])

  const danger = crew.filter((c) => c.status === 'danger' || c.comm === 'lost').length

  return (
    <aside className="crew-panel glass">
      <div className="crew-head">
        <div>
          <b>대원 실시간 관제</b>
          <small> · {crew.length}명 출동</small>
        </div>
        <button className="crew-close" onClick={onClose} aria-label="닫기">
          ✕
        </button>
      </div>

      {danger > 0 && <div className="crew-alarm">⚠ 위험/두절 {danger}명 — 즉시 확인 필요</div>}

      <ul className="crew-list">
        {crew.map((c) => (
          <li key={c.id} className={`crew-card ${c.status} ${c.comm === 'lost' ? 'lost' : ''}`}>
            <div className="crew-top">
              <span className="crew-name">
                {c.name} <small>{c.role}</small>
              </span>
              <span className={`crew-status ${c.status}`}>{STATUS_LABEL[c.status]}</span>
            </div>

            <div className="crew-vitals">
              <div className="vital">
                <span className="vital-label">공기</span>
                <div className="air-bar">
                  <div className={`air-fill ${c.airPct < 20 ? 'low' : c.airPct < 40 ? 'mid' : ''}`} style={{ width: `${c.airPct}%` }} />
                </div>
                <span className="vital-num num">{c.airPct}%</span>
              </div>
              <div className="vital">
                <span className="vital-label">심박</span>
                <span className="vital-num num">{c.hr}</span>
                <span className="vital-unit">bpm</span>
              </div>
            </div>

            <div className={`crew-comm ${c.comm}`}>
              {c.comm === 'lost' ? `📡 통신 두절 · 마지막 ${c.lastSeen} — 위치 추적 유지` : '📡 통신 정상'}
            </div>
          </li>
        ))}
      </ul>

      <div className="crew-note">전력·통신이 끊겨도 비컨으로 마지막 위치·상태를 추적합니다.</div>
    </aside>
  )
}
