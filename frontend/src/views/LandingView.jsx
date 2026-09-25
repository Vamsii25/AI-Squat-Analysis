import { Link } from 'react-router-dom'
import SquatDiagram from '../components/SquatDiagram.jsx'

const steps = [
  { number: '01', kicker: 'INPUT', title: 'Upload the set', body: 'Drop in one side-view clip. MP4, MOV or WebM, up to 60 seconds.' },
  { number: '02', kicker: 'TRACKING', title: 'Follow the movement', body: 'Hips, knees, ankles and the bar are tracked through the clip.' },
  { number: '03', kicker: 'ANALYSIS', title: 'Measure the rep', body: 'The bottom position is located and relevant movement measures are evaluated.' },
  { number: '04', kicker: 'OUTPUT', title: 'Read the evidence', body: 'Findings arrive with a result, timestamp, measurement and source.' }
]

const limits = [
  { code: '01', title: 'Knee valgus', body: 'A side view cannot reliably establish inward knee collapse.' },
  { code: '02', title: 'Stance width', body: 'Foot placement is better judged from a front or overhead view.' },
  { code: '03', title: 'Toe angle', body: 'The camera angle limits how confidently toe rotation can be assessed.' }
]

export default function LandingView() {
  return (
    <div className="landing">
      <section className="hero container">
        <div className="hero-copy" data-reveal="left">
          <div className="eyebrow-line">
            <span className="eyebrow">Movement intelligence / 01</span>
            <span className="live-dot"></span>
            <span className="eyebrow">Evidence first</span>
          </div>
          <h1>Turn every<br /><em>rep</em> into data.</h1>
          <p className="hero-lede">
            Squat Check turns a side-view video into a rep-by-rep movement report.
            Track the body. Measure the bottom position. See exactly what the camera can prove.
          </p>
          <div className="hero-actions">
            <Link to="/analyze" className="btn-primary">Analyze a video <span>↗</span></Link>
            <Link to="/methodology" className="text-link">Explore the method <span>→</span></Link>
          </div>
        </div>

        <div className="hero-visual" data-reveal="right">
          <div className="visual-card">
            <div className="visual-top">
              <span className="mono">SIDE VIEW / LIVE FRAME</span>
              <span className="mono">01:24:08</span>
            </div>
            <div className="scan-line"></div>
            <SquatDiagram />
            <div className="metric metric-depth">
              <span className="metric-label">DEPTH</span>
              <strong>—</strong>
              <small>awaiting clip</small>
            </div>
            <div className="metric metric-path">
              <span className="metric-label">BAR PATH</span>
              <strong>TRACK</strong>
              <small>frame by frame</small>
            </div>
            <div className="visual-stamp">SC</div>
          </div>
        </div>
      </section>

      <section className="marquee-wrap">
        <div className="marquee">
          <span>UPLOAD</span><b>✦</b><span>TRACK</span><b>✦</b><span>MEASURE</span><b>✦</b><span>ASSESS</span><b>✦</b>
          <span>UPLOAD</span><b>✦</b><span>TRACK</span><b>✦</b><span>MEASURE</span><b>✦</b><span>ASSESS</span><b>✦</b>
        </div>
      </section>

      <section className="intro container reveal">
        <div className="section-number mono">01 / THE IDEA</div>
        <div>
          <h2>Less guesswork.<br /><span>More observable movement.</span></h2>
          <p>
            The interface is built around the same principle as the analysis engine:
            make the important thing unmistakable. Your clip becomes a visual,
            timestamped story of what happened in each rep.
          </p>
        </div>
      </section>

      <section className="process container">
        {steps.map((step, i) => (
          <article key={step.number} className="process-card reveal" style={{ '--delay': `${i * 90}ms` }}>
            <div className="card-number">{step.number}</div>
            <div className={`card-icon icon-${i}`}>
              {[1, 2, 3].map((n) => <span key={n}></span>)}
            </div>
            <div className="card-content">
              <p className="eyebrow">{step.kicker}</p>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </div>
            <span className="card-arrow">↗</span>
          </article>
        ))}
      </section>

      <section className="feature container">
        <div className="feature-copy" data-reveal="left">
          <p className="eyebrow">02 / REP BY REP</p>
          <h2>Every timestamp<br />has a reason.</h2>
          <p>
            Find the bottom position, inspect the measured angles and jump directly
            from a finding to the exact moment in the video. Nothing is hidden behind
            a single overall score.
          </p>
          <Link to="/analyze" className="text-link">Open the analysis flow <span>→</span></Link>
        </div>
        <div className="feature-panel" data-reveal="right">
          <div className="panel-head"><span>REP 03</span><span>00:08</span></div>
          <div className="fake-graph">
            <div className="graph-grid"></div>
            <svg viewBox="0 0 500 190" preserveAspectRatio="none" aria-hidden="true">
              <path d="M0 142 C45 142 60 100 105 98 S160 160 205 155 S255 54 305 55 S360 142 405 137 S455 76 500 68" />
            </svg>
            <span className="graph-dot dot-a"></span><span className="graph-dot dot-b"></span>
          </div>
          <div className="panel-stats">
            <div><small>DEPTH</small><strong>MEASURED</strong></div>
            <div><small>BACK ANGLE</small><strong>TRACKED</strong></div>
            <div><small>BAR PATH</small><strong>VISIBLE</strong></div>
          </div>
        </div>
      </section>

      <section className="limits">
        <div className="container limits-inner">
          <div className="limits-copy" data-reveal="left">
            <p className="eyebrow">03 / HONEST BY DESIGN</p>
            <h2>The camera has<br /><em>blind spots.</em></h2>
          </div>
          <div className="limits-list">
            {limits.map((item) => (
              <div key={item.title} className="limit-row reveal">
                <span className="mono">{item.code}</span>
                <div><h3>{item.title}</h3><p>{item.body}</p></div>
                <span className="limit-mark">—</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="closing container reveal">
        <p className="eyebrow">READY WHEN YOU ARE</p>
        <h2>Give your next set<br /><span>something to say.</span></h2>
        <Link to="/analyze" className="round-cta">
          <span>Analyze<br />a video</span><b>↗</b>
        </Link>
      </section>
    </div>
  )
}
