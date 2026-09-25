import { Link } from 'react-router-dom'

export default function FooterBar() {
  return (
    <footer className="footer">
      <div className="container footer-top">
        <div>
          <p className="eyebrow">Squat Check / movement intelligence</p>
          <h2>Measure the movement.<br /><em>Understand the rep.</em></h2>
        </div>
        <Link to="/analyze" className="footer-button">Analyze a video <span>↗</span></Link>
      </div>
      <div className="container footer-bottom">
        <p>Side-view assessment built around measurable evidence, timestamps and transparent criteria.</p>
        <div className="footer-links">
          <Link to="/">Overview</Link>
          <Link to="/methodology">Methodology</Link>
          <Link to="/analyze">Analyze</Link>
        </div>
      </div>
    </footer>
  )
}
