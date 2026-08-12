import { useRef, useEffect } from 'react'
import { useKakaoLoader } from 'react-kakao-maps-sdk'
import { briefing } from '../data/scenario.js'

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY

// needle을 포함하는 가장 작은 요소의 텍스트를 value로 교체.
function setSmallestIncluding(doc, needle, value) {
  const els = [...doc.querySelectorAll('p, span, div')].filter((e) => (e.textContent || '').includes(needle))
  if (!els.length) return
  els.sort((a, b) => a.textContent.length - b.textContent.length)
  els[0].textContent = value
}

// 출동 브리핑 = 원본 디자인(public/fire-dispatch.html) 그대로 iframe. 디자인 무수정.
// 기능은 로드 후 "값"만 주입:
//   - 신고내용 위젯 가로 확장
//   - 근무 일정: 오늘 날짜 + 현재 시간 라이브
//   - 내 위치: Kakao 역지오코딩으로 현재 위치 주소
//   - '안내 시작' → 경로 화면
export default function Briefing({ onStart }) {
  const ref = useRef(null)
  const els = useRef({})
  const addr = useRef(null)
  const [kLoading] = useKakaoLoader({ appkey: KAKAO_KEY ?? '', libraries: ['services'], url: 'https://dapi.kakao.com/v2/maps/sdk.js' })

  const leaves = (doc) => [...doc.querySelectorAll('*')].filter((el) => el.children.length === 0)
  const findLeaf = (doc, t) => leaves(doc).find((el) => (el.textContent || '').trim() === t) || null
  const findContains = (doc, t) => leaves(doc).find((el) => (el.textContent || '').includes(t)) || null
  function findWidget(doc) {
    let n = findLeaf(doc, '신고 내용')
    while (n && getComputedStyle(n).position !== 'absolute') n = n.parentElement
    return n
  }

  function applyLoc() {
    if (els.current.loc && addr.current) els.current.loc.textContent = addr.current
  }

  // 신고 내용(주소·REPORT DETAILS)을 시나리오 값으로 주입.
  function applyContent(doc) {
    setSmallestIncluding(doc, '세종대로', briefing.address)
    setSmallestIncluding(doc, '세종문화회관', briefing.addressSub)
    briefing.report.forEach((r) => setSmallestIncluding(doc, r.label, `• ${r.label}: ${r.text}`))
  }

  // 신고내용 위젯: 오른쪽 끝(콘텐츠 우측=알림 위젯 라인)까지 꽉 채움 + 글자 키움 + 높이 auto.
  // 고정폭 대신 left 고정 + right:0 → 화면 폭과 무관하게 오른쪽 여백을 항상 채움(왼쪽 유지).
  function styleWidget(w) {
    w.style.left = '678px'
    w.style.right = '0px'
    w.style.width = 'auto'
    w.style.height = 'auto'

    // 내부 박스(LOCATION·REPORT DETAILS)의 고정폭(width:257px 등) 해제 → 위젯 폭 꽉 채움
    ;[...w.children].forEach((c) => {
      if (c.tagName === 'DIV') c.style.width = ''
    })

    // REPORT DETAILS 불릿 4개를 2열 그리드로 펼쳐 오른쪽 여백까지 채움 + 글자 키움
    const rdBox = [...w.children].find((c) => (c.textContent || '').includes('REPORT DETAILS'))
    if (rdBox) {
      const bulletWrap = [...rdBox.children].find((c) => c.querySelectorAll('p').length >= 3)
      if (bulletWrap) {
        bulletWrap.style.display = 'grid'
        bulletWrap.style.gridTemplateColumns = '1fr 1fr'
        bulletWrap.style.gap = '14px 34px'
        bulletWrap.querySelectorAll('p').forEach((p) => {
          p.style.fontSize = '15px'
          p.style.lineHeight = '1.65'
        })
      }
    }

    // 주소 등 본문 글자 키워 가독성 확보
    ;[...w.querySelectorAll('p, span')].forEach((el) => {
      if (el.children.length) return
      const t = (el.textContent || '').trim()
      if (t.includes('대학로') || t.includes('유성구') || t.includes('세종대로')) el.style.fontSize = '15px'
    })
  }

  function paint() {
    const e = els.current
    if (e.widget) styleWidget(e.widget)
    const now = new Date()
    if (e.shift) e.shift.textContent = `${now.getMonth() + 1}월 ${now.getDate()}일 - 주간 교대`
    applyLoc()
    if (!e.day) return
    e.day.textContent = String(now.getDate())
    if (e.month) e.month.textContent = now.toLocaleString('en-US', { month: 'long' }).toUpperCase()
    const h = now.getHours()
    const h12 = ((h + 11) % 12) + 1
    e.time.textContent = `${String(h12).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    if (e.ampm) e.ampm.textContent = h < 12 ? 'A.M.' : 'P.M.'
  }

  // 번들 페이지는 로드 후 늦게 렌더 → 요소가 나타날 때까지 폴링.
  function tryInject(doc, attempt = 0) {
    els.current = {
      day: findLeaf(doc, '20'),
      month: findLeaf(doc, 'JULY'),
      time: findLeaf(doc, '10:25'),
      ampm: findLeaf(doc, 'A.M.'),
      widget: findWidget(doc),
      loc: findContains(doc, '소방센터'),
      shift: findContains(doc, '주간 교대'),
    }
    if (els.current.day && els.current.time) {
      applyContent(doc)
      paint()
      return
    }
    if (attempt < 25) setTimeout(() => tryInject(doc, attempt + 1), 300)
  }

  function onLoad() {
    const doc = ref.current?.contentDocument
    if (!doc) return
    tryInject(doc)
    doc.addEventListener(
      'click',
      (ev) => {
        let n = ev.target
        for (let i = 0; i < 5 && n; i++) {
          const t = (n.textContent || '').trim()
          if (t.includes('안내 시작') && t.length < 30) {
            onStart()
            return
          }
          n = n.parentElement
        }
      },
      true,
    )
  }

  // 현위치 → Kakao 역지오코딩으로 주소 확보.
  useEffect(() => {
    if (kLoading || !navigator.geolocation || !window.kakao?.maps?.services) return
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const geocoder = new window.kakao.maps.services.Geocoder()
        geocoder.coord2Address(p.coords.longitude, p.coords.latitude, (res, status) => {
          if (status === window.kakao.maps.services.Status.OK && res[0]) {
            const a = res[0].road_address?.address_name || res[0].address?.address_name
            if (a) {
              addr.current = a
              applyLoc()
            }
          }
        })
      },
      () => {},
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }, [kLoading])

  useEffect(() => {
    const t = setInterval(() => {
      const doc = ref.current?.contentDocument
      if (doc) applyContent(doc)
      paint()
    }, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="bf-embed">
      <iframe ref={ref} className="bf-frame" src="/fire-dispatch.html" title="출동 브리핑" onLoad={onLoad} />
    </div>
  )
}
