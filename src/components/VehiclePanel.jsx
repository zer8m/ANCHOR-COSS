import { VEHICLES, ENTRY_CRITERIA, CRITERIA_SOURCE, CLEARANCE_M, requiredWidthM } from '../data/vehicles.js'

// 진입 기준 + 차종별 제원 표. 행을 고르면 출동 차종이 바뀌고 센터 판정이 다시 계산된다.
export default function VehiclePanel({ vehicleId, onSelect, onClose }) {
  return (
    <div className="tnavi-vpanel" role="dialog" aria-label="진입 기준 · 차종별 제원">
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
            <th scope="col">필요 통과폭</th>
          </tr>
        </thead>
        <tbody>
          {VEHICLES.map((v) => (
            <tr key={v.id} className={v.id === vehicleId ? 'on' : ''}>
              <th scope="row">
                <button onClick={() => onSelect(v.id)} aria-pressed={v.id === vehicleId}>
                  {v.name}
                  {!v.verified && <small> 잠정</small>}
                </button>
              </th>
              <td>{v.widthM.toFixed(1)}m</td>
              <td>{v.lengthM.toFixed(1)}m</td>
              <td><b>{requiredWidthM(v).toFixed(1)}m</b></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="tnavi-vnote">필요 통과폭 = 차폭 + 여유 {CLEARANCE_M}m · 잔여 폭이 이보다 좁으면 진입 불가</p>

      <dl className="tnavi-vcriteria">
        {ENTRY_CRITERIA.map((c) => (
          <div key={c.id}>
            <dt>{c.label}</dt>
            <dd>{c.rule}</dd>
          </div>
        ))}
      </dl>
      <p className="tnavi-vnote">{CRITERIA_SOURCE}</p>
    </div>
  )
}
