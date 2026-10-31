import { VEHICLES, ENTRY_CRITERIA, CRITERIA_SOURCE, LEGAL_BASIS, SOURCES, CLEARANCE_SOURCE, CLEARANCE_SOURCE_URL, requiredWidthM } from '../data/vehicles.js'

// 진입 기준 + 차종별 제원 표. 행을 고르면 출동 차종이 바뀌고 센터 판정이 다시 계산된다.
export default function VehiclePanel({ vehicleId, onSelect, onClose }) {
  return (
    <div className="tnavi-vpanel" aria-label="진입 기준 · 차종별 제원">
      <div className="tnavi-vpanel-head">
        <b>진입 기준 · 차종별 제원</b>
        <button className="tnavi-vpanel-close" onClick={onClose} aria-label="닫기">✕</button>
      </div>

      <table className="tnavi-vtable">
        <thead>
          <tr>
            <th scope="col">차종</th>
            <th scope="col">차폭</th>
            <th scope="col">전장</th>
            <th scope="col">전고</th>
            <th scope="col">여유</th>
            <th scope="col">필요 통과폭</th>
          </tr>
        </thead>
        <tbody>
          {VEHICLES.map((v) => (
            <tr key={v.id} className={v.id === vehicleId ? 'on' : ''}>
              <th scope="row">
                <button onClick={() => onSelect(v.id)} aria-pressed={v.id === vehicleId}>
                  {v.name}
                  {v.kind === 'legal_max' && <small> 잠정</small>}
                </button>
              </th>
              <td>{v.widthM.toFixed(1)}m</td>
              <td>{v.lengthM ? `${v.lengthM.toFixed(1)}m` : '–'}</td>
              <td>{v.heightM ? `${v.heightM.toFixed(1)}m` : '–'}</td>
              <td>{v.clearanceM.toFixed(1)}m</td>
              <td><b>{requiredWidthM(v).toFixed(1)}m</b></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="tnavi-vnote">필요 통과폭 = 차폭 + 차종별 여유폭 · 잔여 폭이 이보다 좁으면 진입 불가</p>
      <p className="tnavi-vnote">
        여유폭: <a href={CLEARANCE_SOURCE_URL} target="_blank" rel="noreferrer">{CLEARANCE_SOURCE}</a>
      </p>
      <p className="tnavi-vnote">
        제원(차폭은 미러 제외 상한값):{' '}
        {Object.entries(SOURCES).map(([k, src], i) => (
          <span key={k}>
            {i > 0 && ' · '}
            <a href={src.url} target="_blank" rel="noreferrer" title={src.label}>{src.short}</a>
          </span>
        ))}
      </p>

      <dl className="tnavi-vcriteria">
        {ENTRY_CRITERIA.map((c) => (
          <div key={c.id}>
            <dt>{c.label}</dt>
            <dd>{c.rule}</dd>
          </div>
        ))}
      </dl>
      <p className="tnavi-vnote">{CRITERIA_SOURCE}</p>

      {/* 주행 단말이라 기본은 접어둔다(native details). */}
      <details className="tnavi-vlegal">
        <summary className="tnavi-vsub">법적 근거</summary>
        <dl className="tnavi-vcriteria">
          {LEGAL_BASIS.map((c) => (
            <div key={c.id}>
              <dt>{c.label}</dt>
              <dd>{c.rule}</dd>
              <dd className="tnavi-vmeaning">→ {c.meaning}</dd>
              <dd className="tnavi-vnote">{c.source}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  )
}
