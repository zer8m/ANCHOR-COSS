import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const restKey = env.KAKAO_REST_KEY || ''

  return {
    plugins: [react()],
    server: {
      // 경로 fixture 캡처(scripts/capture-routes.mjs) 전용 프록시. REST 키는 서버측(여기)에만.
      // 앱 런타임은 이 프록시를 호출하지 않는다.
      proxy: {
        '/kakao-navi': {
          target: 'https://apis-navi.kakaomobility.com',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/kakao-navi/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (restKey) proxyReq.setHeader('Authorization', `KakaoAK ${restKey}`)
            })
          },
        },
      },
    },
  }
})
