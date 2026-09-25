import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Overview', match: (path) => path === '/' },
  { to: '/analyze', label: 'Analyze', match: (path) => path.startsWith('/analyze') },
  { to: '/results', label: 'Results', match: (path) => path.startsWith('/results') },
  { to: '/methodology', label: 'Methodology', match: (path) => path === '/methodology' }
]

export default function NavBar() {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Close the overlay whenever the route changes.
  useEffect(() => { setOpen(false) }, [location.pathname])

  // Lock background scroll while the overlay menu is open.
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  return (
    <header className="nav-wrap">
      <div className="nav container">
        <NavLink to="/" className="brand" aria-label="Squat Check home">
          <span className="brand-symbol"><span></span><span></span><span></span></span>
          <span>Squat Check</span>
        </NavLink>

        <nav className="links" aria-label="Primary">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={() => (l.match(location.pathname) ? 'active' : '')}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <NavLink to="/analyze" className="nav-cta">
          Start analysis <span>↗</span>
        </NavLink>

        <button
          type="button"
          className={`menu-button${open ? ' open' : ''}`}
          aria-label="Toggle navigation"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span></span><span></span>
        </button>
      </div>

      {open && (
        <div className="nav-overlay">
          <div className="nav-overlay-links">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} className={() => (l.match(location.pathname) ? 'active' : '')} onClick={() => setOpen(false)}>
                {l.label}
              </NavLink>
            ))}
          </div>
          <div className="nav-overlay-foot">
            <span>Squat Check / movement intelligence</span>
            <span>Side-view assessment</span>
          </div>
        </div>
      )}
    </header>
  )
}
