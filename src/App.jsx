import { useState } from 'react'
import Briefing from './components/Briefing.jsx'
import NaviView from './components/NaviView.jsx'
import Report from './components/Report.jsx'
import './App.css'

// 3화면: 브리핑 → 내비(좌 턴바이턴 / 우 전술지도) / 통계.
export default function App() {
  const [screen, setScreen] = useState('briefing')

  if (screen === 'navi') {
    return <NaviView onExit={() => setScreen('briefing')} />
  }
  if (screen === 'report') {
    return <Report onBack={() => setScreen('briefing')} onNav={() => setScreen('navi')} />
  }
  return <Briefing onStart={() => setScreen('navi')} onReport={() => setScreen('report')} />
}
