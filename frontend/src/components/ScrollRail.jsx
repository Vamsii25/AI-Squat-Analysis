import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

export default function ScrollRail() {
  const railRef = useRef(null)
  const location = useLocation()

  useEffect(() => {
    function update() {
      const el = railRef.current
      if (!el) return
      const doc = document.documentElement
      const scrollable = doc.scrollHeight - doc.clientHeight
      const ratio = scrollable > 0 ? window.scrollY / scrollable : 0
      el.style.width = `${Math.min(1, Math.max(0, ratio)) * 100}%`
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [location.pathname])

  return <div ref={railRef} className="scroll-rail" aria-hidden="true" />
}
