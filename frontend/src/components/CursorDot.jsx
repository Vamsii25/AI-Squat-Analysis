import { useEffect, useRef, useState } from 'react'

export default function CursorDot() {
  const dotRef = useRef(null)
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    const fine = window.matchMedia('(pointer: fine)').matches
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    setEnabled(fine && !reduced)
  }, [])

  useEffect(() => {
    if (!enabled) return
    const el = dotRef.current
    if (!el) return

    function move(e) {
      el.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0)`
    }
    function activateOn(target) {
      return target.closest('a, button, .reveal, .process-card, .finding, .dropzone')
    }
    function over(e) { if (activateOn(e.target)) el.classList.add('is-active') }
    function out(e) { if (activateOn(e.target)) el.classList.remove('is-active') }

    window.addEventListener('mousemove', move)
    window.addEventListener('mouseover', over)
    window.addEventListener('mouseout', out)
    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseover', over)
      window.removeEventListener('mouseout', out)
    }
  }, [enabled])

  if (!enabled) return null
  return <div ref={dotRef} className="cursor-dot" aria-hidden="true" />
}
