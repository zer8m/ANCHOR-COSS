// 카카오내비 실행 (Kakao JS SDK의 Kakao.Navi.start).
// 지도 SDK(dapi)와 별개. 목적지로 실제 턴바이턴 내비를 띄운다.
const SDK_URL = 'https://t1.kakaocdn.net/kakao_js_sdk/2.7.2/kakao.min.js'
const JS_KEY = import.meta.env.VITE_KAKAO_MAP_KEY

let sdkPromise = null
function loadSdk() {
  if (window.Kakao) return Promise.resolve(window.Kakao)
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = SDK_URL
      s.async = true
      s.onload = () => resolve(window.Kakao)
      s.onerror = () => reject(new Error('Kakao JS SDK 로드 실패'))
      document.head.appendChild(s)
    })
  }
  return sdkPromise
}

// dest: { name, lat, lng }. 성공 시 카카오내비 실행, 실패 시 throw.
export async function startNavi(dest) {
  if (!JS_KEY) throw new Error('VITE_KAKAO_MAP_KEY 없음')
  const Kakao = await loadSdk()
  if (!Kakao.isInitialized()) Kakao.init(JS_KEY)
  Kakao.Navi.start({
    name: dest.name,
    x: dest.lng, // 경도
    y: dest.lat, // 위도
    coordType: 'wgs84',
  })
}
