import { useEffect, useState } from 'react'
import { useKakaoLoader, Map, CustomOverlayMap } from 'react-kakao-maps-sdk'

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY
// 기본 위치(종로구 소방센터 기지) — 위치 권한 거부/미지원 시 폴백.
const BASE = { lat: 37.5729, lng: 126.9793 }

// 현위치 미니 지도. navigator.geolocation으로 실제 위치 표시, 실패 시 기지 좌표.
export default function LocationCard({ stationBase }) {
  const [pos, setPos] = useState(BASE)
  const [status, setStatus] = useState('locating') // locating | live | fallback

  useEffect(() => {
    if (!navigator.geolocation) {
      setStatus('fallback')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setPos({ lat: p.coords.latitude, lng: p.coords.longitude })
        setStatus('live')
      },
      () => setStatus('fallback'),
      { enableHighAccuracy: true, timeout: 6000 },
    )
  }, [])

  return (
    <div className="bf-card bf-loc">
      <div className="bf-card-head">
        <div>
          <b>내 위치</b>
          <small>{status === 'live' ? '실시간 GPS' : stationBase}</small>
        </div>
        <span className={`bf-loc-badge ${status}`}>
          {status === 'live' ? '● LIVE' : status === 'locating' ? '측위중…' : '기지 좌표'}
        </span>
      </div>

      <div className="bf-loc-map">
        {KAKAO_KEY ? (
          <MiniMap pos={pos} />
        ) : (
          <div className="bf-loc-pin">
            <span className="bf-pin-dot" />
          </div>
        )}
      </div>
    </div>
  )
}

function MiniMap({ pos }) {
  const [loading, error] = useKakaoLoader({ appkey: KAKAO_KEY, url: 'https://dapi.kakao.com/v2/maps/sdk.js' })
  if (error) {
    return (
      <div className="bf-loc-pin">
        <span className="bf-pin-dot" />
      </div>
    )
  }
  return (
    <Map center={pos} level={4} style={{ width: '100%', height: '100%', borderRadius: '14px' }} draggable={false} zoomable={false}>
      {loading && null}
      <CustomOverlayMap position={pos} yAnchor={0.5} xAnchor={0.5}>
        <span className="bf-live-dot" />
      </CustomOverlayMap>
    </Map>
  )
}
