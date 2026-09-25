import { Routes, Route, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import NavBar from './components/NavBar.jsx'
import FooterBar from './components/FooterBar.jsx'
import CursorDot from './components/CursorDot.jsx'
import ScrollRail from './components/ScrollRail.jsx'
import useReveal from './hooks/useReveal.js'
import LandingView from './views/LandingView.jsx'
import AnalyzeView from './views/AnalyzeView.jsx'
import MethodologyView from './views/MethodologyView.jsx'
import ResultsHistoryView from './views/ResultsHistoryView.jsx'
import NotFoundView from './views/NotFoundView.jsx'

export default function App() {
  const location = useLocation()
  useReveal()

  // Scroll to top on every route change, same as the router's scrollBehavior.
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [location.pathname])

  return (
    <div className="app-shell">
      <ScrollRail />
      <CursorDot />
      <NavBar />
      <main className="page-stage">
        <div key={location.pathname} className="page-transition">
          <Routes location={location}>
            <Route path="/" element={<LandingView />} />
            <Route path="/analyze" element={<AnalyzeView />} />
            <Route path="/analyze/:jobId" element={<AnalyzeView />} />
            <Route path="/results" element={<ResultsHistoryView />} />
            <Route path="/results/:jobId" element={<ResultsHistoryView />} />
            <Route path="/methodology" element={<MethodologyView />} />
            <Route path="*" element={<NotFoundView />} />
          </Routes>
        </div>
      </main>
      <FooterBar />
    </div>
  )
}
