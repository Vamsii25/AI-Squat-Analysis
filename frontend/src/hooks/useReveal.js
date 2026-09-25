import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Watches every .reveal / [data-reveal] element on the page and adds
 * .is-visible once it scrolls into view, then stops watching it.
 * Re-runs whenever the route changes so newly-mounted page content
 * gets observed too.
 */
export default function useReveal() {
  const location = useLocation()

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.12 })

    const id = window.requestAnimationFrame(() => {
      document.querySelectorAll('.reveal, [data-reveal]').forEach((el) => observer.observe(el))
    })

    return () => {
      window.cancelAnimationFrame(id)
      observer.disconnect()
    }
  }, [location.pathname])
}
