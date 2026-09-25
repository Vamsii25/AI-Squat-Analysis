import { Link } from 'react-router-dom'

const criteria = [
  { name: 'Squat depth', description: 'Hip crease drops below the top of the knee at the bottom of the rep.', assessable: 'yes' },
  { name: 'Back angle', description: 'Torso holds a fairly consistent angle through the bottom rather than collapsing forward.', assessable: 'yes' },
  { name: 'Bar path', description: 'The bar stays close to vertical over the middle of the foot through the lift.', assessable: 'yes' },
  { name: 'Hip drive out of the bottom', description: 'Hips and shoulders rise together on the way up.', assessable: 'yes' },
  { name: 'Knee travel', description: 'Forward knee travel is visible from the side; inward collapse is not.', assessable: 'partial' },
  { name: 'Stance width & toe angle', description: 'Foot placement is best judged from the front or above.', assessable: 'no' }
]

const flow = [
  { title: 'Track every frame', body: 'Body landmarks and the bar are tracked through the full clip.' },
  { title: 'Locate the bottom', body: 'Each repetition is segmented and its bottom position is identified.' },
  { title: 'Compare the measures', body: 'Measured angles and positions are compared with the structured criteria.' },
  { title: 'Return the evidence', body: 'Every finding receives a result, timestamp, measurement and citation.' }
]

const ASSESSABLE_LABEL = { yes: 'SIDE VIEW / YES', partial: 'SIDE VIEW / PARTIAL', no: 'SIDE VIEW / NO' }

export default function MethodologyView() {
  return (
    <div className="method-page">
      <section className="method-hero container">
        <div className="method-title" data-reveal="left">
          <p className="eyebrow">03 / METHODOLOGY</p>
          <h1>What gets checked.<br /><span>What doesn't.</span></h1>
        </div>
        <p className="method-intro" data-reveal="right">
          Squat Check is designed to make the boundary between measurement and
          assumption visible. Criteria come from the reference skill file, and
          findings carry their source and timestamp with them.
        </p>
      </section>

      <section className="criteria container">
        <div className="criteria-head reveal">
          <span className="mono">CRITERIA / 06</span><span>ASSESSABILITY FROM SIDE VIEW</span>
        </div>
        <div className="criteria-list">
          {criteria.map((c, i) => (
            <div key={c.name} className="criterion-row reveal" style={{ '--delay': `${i * 60}ms` }}>
              <span className="criterion-index mono">{String(i + 1).padStart(2, '0')}</span>
              <div className="criterion-main"><h3>{c.name}</h3><p>{c.description}</p></div>
              <span className={`assessable ${c.assessable}`}>{ASSESSABLE_LABEL[c.assessable]}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="blind container">
        <div className="blind-copy" data-reveal="left">
          <p className="eyebrow">THE BLIND SPOTS</p>
          <h2>A camera should<br />be allowed to say<br /><em>&ldquo;I don't know.&rdquo;</em></h2>
        </div>
        <div className="blind-text" data-reveal="right">
          <p>
            A single side-view camera cannot reliably answer every movement question.
            Knee valgus, exact stance width and toe angle need another viewpoint.
          </p>
          <p>
            Instead of filling those gaps with a guess, Squat Check marks the
            criterion <strong>cannot assess</strong> and tells you why.
          </p>
        </div>
      </section>

      <section className="flow container">
        <div className="flow-head"><p className="eyebrow">FROM VIDEO TO FINDING</p><h2>The path of a rep.</h2></div>
        <ol className="flow-list">
          {flow.map((item, i) => (
            <li key={item.title} className="flow-item reveal">
              <span className="flow-num">{String(i + 1).padStart(2, '0')}</span>
              <div><h3>{item.title}</h3><p>{item.body}</p></div>
              <span className="flow-arrow">↗</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="method-cta container reveal">
        <p className="eyebrow">NEXT STEP</p>
        <h2>Put the method<br /><span>to work.</span></h2>
        <Link to="/analyze" className="btn-primary">Analyze your video ↗</Link>
      </section>
    </div>
  )
}
