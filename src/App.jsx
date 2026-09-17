import { useState } from 'react'
import Briefing from './components/Briefing.jsx'
import NaviView from './components/NaviView.jsx'
import './App.css'

// 2화면: 출동 브리핑 → 내비(센터 판정·경로 표출).
export default function App() {
  const [screen, setScreen] = useState('briefing')

  if (screen === 'navi') {
    return <NaviView onExit={() => setScreen('briefing')} />
  }
  return <Briefing onStart={() => setScreen('navi')} />
}
