import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const restKey = env.KAKAO_REST_KEY || ''
  const geminiKey = env.GEMINI_API_KEY || ''

  return {
    plugins: [react()],
    server: {
      // 외부 API는 브라우저 직접 호출 시 CORS로 막힘 → dev 프록시로 우회, 키는 서버측(여기)에만.
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
        '/gemini': {
          target: 'https://generativelanguage.googleapis.com',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/gemini/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (geminiKey) proxyReq.setHeader('x-goog-api-key', geminiKey)
            })
          },
        },
      },
    },
  }
})
