import { useState } from 'react'

const RESULT_LABELS = {
  meets_standard: 'Meets standard',
  does_not_meet_standard: 'Does not meet',
  cannot_assess: 'Cannot assess',
}

const RESULT_CLASSES = {
  meets_standard: 'pg-badge pg-meets',
  does_not_meet_standard: 'pg-badge pg-fails',
  cannot_assess: 'pg-badge pg-unknown',
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'does_not_meet_standard', label: 'Does not meet' },
  { key: 'meets_standard', label: 'Meets standard' },
  { key: 'cannot_assess', label: 'Cannot assess' },
]

const MEASURE_ROWS = [
  { key: 'hip_angle_deg', label: 'Hip angle', suffix: '°' },
  { key: 'knee_angle_deg', label: 'Knee angle', suffix: '°' },
  { key: 'back_angle_deg', label: 'Back angle', suffix: '°' },
  { key: 'head_neck_angle_deg', label: 'Head / neck', suffix: '°' },
  { key: 'knee_forward_of_toe_px', label: 'Knee forward', suffix: ' px' },
  { key: 'bar_x_offset_from_midfoot_px', label: 'Bar / midfoot', suffix: ' px' },
  { key: 'hip_joint_y_norm', label: 'Hip Y', suffix: '' },
  { key: 'top_of_patella_y_norm', label: 'Patella Y', suffix: '' },
]

const CONFIDENCE_ROWS = [
  { key: 'hip', label: 'Hip' },
  { key: 'knee', label: 'Knee' },
  { key: 'ankle', label: 'Ankle' },
  { key: 'shoulder', label: 'Shoulder' },
  { key: 'bar', label: 'Bar' },
]

const NOTE_LABELS = {
  hip_low_confidence: 'Hip unclear',
  knee_low_confidence: 'Knee unclear',
  ankle_low_confidence: 'Ankle unclear',
  shoulder_low_confidence: 'Shoulder unclear',
  bar_low_confidence: 'Bar unclear',
  bar_not_detected_at_bottom_frame: 'Bar not found at bottom',
}

function fmt(value, suffix = '') {
  if (value === null || value === undefined) return '--'
  return `${value}${suffix}`
}

function fmtTime(seconds) {
  if (seconds === null || seconds === undefined) return '--'
  const t = Number(seconds)
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
}

const PG_CSS = `
.pg-root { display: flex; flex-direction: column; gap: 24px; width: 100%; }
.pg-root, .pg-root * { box-sizing: border-box; }

.pg-header { display: flex; flex-direction: column; gap: 10px; }
.pg-header h2 { margin: 0; font-size: clamp(28px, 4vw, 44px); line-height: 1.05; text-transform: uppercase; }
.pg-header p { margin: 0; max-width: 720px; color: var(--muted, #8c92a0); font-size: 15px; line-height: 1.6; }
.pg-eyebrow { font: 11px var(--font-mono, ui-monospace, monospace); letter-spacing: .12em; text-transform: uppercase; color: var(--muted-dim, #5b616e); }

.pg-card { background: var(--paper, #11141b); border: 1px solid var(--line, #20242e); border-radius: 22px; padding: 26px; width: 100%; }
.pg-card-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 20px; color: var(--muted, #8c92a0); font-size: 13px; }
.pg-card-head h3 { margin: 6px 0 0; font-size: 22px; color: var(--ink, #f4f6f9); text-transform: uppercase; letter-spacing: -.01em; }
.pg-model-badge { padding: 6px 12px; border-radius: 999px; background: var(--accent-soft, rgba(46,166,255,.14)); color: var(--accent, #2ea6ff); font: 11px var(--font-mono, ui-monospace, monospace); text-transform: uppercase; }
.pg-summary { margin: 0; font-size: 15px; line-height: 1.75; color: var(--muted, #8c92a0); }
.pg-warning { margin: 16px 0 0; font-size: 13px; color: var(--warning, #f5b942); }

.pg-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 22px; }
.pg-stat { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; padding: 18px 10px; text-align: center; background: var(--bg-soft, #0d1016); border: 1px solid var(--line, #20242e); border-radius: 14px; }
.pg-stat strong { font-size: 30px; line-height: 1; color: var(--ink, #f4f6f9); }
.pg-stat span { font: 10px var(--font-mono, ui-monospace, monospace); letter-spacing: .06em; text-transform: uppercase; color: var(--muted, #8c92a0); }
.pg-stat-meets strong { color: var(--success, #35d68e); }
.pg-stat-fails strong { color: var(--danger, #ff6a63); }
.pg-stat-unknown strong { color: var(--muted, #8c92a0); }

/* ---------- plan-style comparison grid: label column + one equal column per rep ---------- */
.pg-grid { display: grid; grid-template-columns: minmax(96px, .9fr) repeat(var(--reps, 2), minmax(0, 1fr)); width: 100%; gap: 0 12px; }
.pg-cell { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; padding: 14px 12px; min-width: 0; text-align: center; font-size: 14px; color: var(--ink, #f4f6f9); border-bottom: 1px solid var(--line, #20242e); overflow-wrap: anywhere; }
.pg-label { align-items: flex-start; text-align: left; justify-content: center; color: var(--muted, #8c92a0); font-size: 13px; font-weight: 600; }
.pg-data { background: var(--bg-soft, #0d1016); border-left: 1px solid var(--line, #20242e); border-right: 1px solid var(--line, #20242e); }
.pg-data.pg-first { border-top: 0; }
.pg-data.pg-last, .pg-label.pg-last { border-bottom: 0; }

.pg-col-head { padding: 18px 12px; background: linear-gradient(180deg, var(--accent-soft, rgba(46,166,255,.14)), var(--bg-soft, #0d1016)); border: 1px solid var(--accent, #2ea6ff); border-bottom: 1px solid var(--line, #20242e); border-radius: 16px 16px 0 0; gap: 4px; }
.pg-col-head strong { font-size: 20px; text-transform: uppercase; }
.pg-col-head small { font: 11px var(--font-mono, ui-monospace, monospace); color: var(--muted, #8c92a0); }
.pg-corner { align-items: flex-start; text-align: left; justify-content: flex-end; border-bottom: 1px solid var(--line, #20242e); font: 10px var(--font-mono, ui-monospace, monospace); letter-spacing: .08em; text-transform: uppercase; color: var(--muted-dim, #5b616e); }
.pg-data:last-child { border-bottom: 1px solid var(--line, #20242e); border-radius: 0 0 16px 16px; }

.pg-val { font-size: 18px; font-weight: 700; }
.pg-muted { color: var(--muted-dim, #5b616e); }
.pg-mono { font-family: var(--font-mono, ui-monospace, monospace); }

.pg-conf { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.pg-conf strong { font-size: 16px; }
.pg-bar { width: 70%; max-width: 120px; height: 5px; border-radius: 99px; background: rgba(255,255,255,.1); overflow: hidden; }
.pg-bar-fill { height: 100%; border-radius: 99px; background: var(--accent, #2ea6ff); }
.pg-tags { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; }
.pg-tag { padding: 4px 9px; border-radius: 999px; background: rgba(245,185,66,.14); color: var(--warning, #f5b942); font-size: 11px; }

.pg-badge { display: inline-block; padding: 6px 12px; border-radius: 999px; font: 11px var(--font-mono, ui-monospace, monospace); letter-spacing: .04em; text-transform: uppercase; }
.pg-meets { background: rgba(53,214,142,.14); color: var(--success, #35d68e); }
.pg-fails { background: rgba(255,106,99,.14); color: var(--danger, #ff6a63); }
.pg-unknown { background: rgba(140,146,160,.16); color: var(--muted, #8c92a0); }

.pg-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.pg-filter { display: inline-flex; align-items: center; gap: 8px; padding: 9px 16px; border-radius: 999px; border: 1px solid var(--line, #20242e); background: transparent; color: var(--muted, #8c92a0); font: 13px var(--font-ui, system-ui, sans-serif); cursor: pointer; transition: all .2s ease; }
.pg-filter span { padding: 1px 7px; border-radius: 999px; background: rgba(255,255,255,.07); font: 11px var(--font-mono, ui-monospace, monospace); }
.pg-filter:hover { color: var(--ink, #f4f6f9); border-color: var(--muted-dim, #5b616e); }
.pg-filter.active { background: var(--accent-soft, rgba(46,166,255,.14)); border-color: var(--accent, #2ea6ff); color: var(--accent-ink, #eaf6ff); }

/* findings cell: stacked, left-aligned detail blocks */
.pg-finding { align-items: stretch; justify-content: flex-start; text-align: left; gap: 10px; padding: 16px 14px; }
.pg-finding.pg-dim { opacity: .28; }
.pg-finding .pg-badge { align-self: flex-start; }
.pg-block { display: flex; flex-direction: column; gap: 3px; font-size: 12.5px; line-height: 1.5; color: var(--muted, #8c92a0); }
.pg-block em { font: normal 10px var(--font-mono, ui-monospace, monospace); letter-spacing: .06em; text-transform: uppercase; color: var(--muted-dim, #5b616e); }
.pg-block.pg-measure { color: var(--accent, #2ea6ff); font-family: var(--font-mono, ui-monospace, monospace); font-size: 12px; }
.pg-block.pg-uncertain { color: var(--warning, #f5b942); }
.pg-empty { padding: 26px; text-align: center; color: var(--muted-dim, #5b616e); }

@media (max-width: 720px) {
  .pg-card { padding: 16px; }
  .pg-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pg-grid { grid-template-columns: minmax(70px, .8fr) repeat(var(--reps, 2), minmax(0, 1fr)); gap: 0 6px; }
  .pg-cell { padding: 10px 6px; font-size: 12px; }
  .pg-label { font-size: 11px; }
  .pg-val { font-size: 15px; }
  .pg-col-head strong { font-size: 15px; }
  .pg-block { font-size: 11px; }
}
`

export default function ResultsView({ results = {} }) {
  const [filter, setFilter] = useState('all')

  const reps = (results.video_data || {}).reps || []
  const findings = results.findings || []
  const overallSummary = results.overall_summary || 'No overall summary was returned.'
  const modelUsed = results.model_used || 'Model 2'

  const counts = {
    meets_standard: findings.filter((f) => f.result === 'meets_standard').length,
    does_not_meet_standard: findings.filter((f) => f.result === 'does_not_meet_standard').length,
    cannot_assess: findings.filter((f) => f.result === 'cannot_assess').length,
  }

  // Rep columns: every rep from the measurements plus any rep only seen in findings.
  const repNumbers = Array.from(
    new Set([...reps.map((r) => r.rep_number), ...findings.map((f) => f.rep_number)].filter((n) => n !== undefined && n !== null))
  ).sort((a, b) => a - b)
  const repByNumber = Object.fromEntries(reps.map((r) => [r.rep_number, r]))
  const gridStyle = { '--reps': Math.max(1, repNumbers.length) }

  // Findings pivot: one row per criterion, one column per rep.
  const criteria = []
  const criterionSeen = {}
  findings.forEach((f) => {
    const id = f.criterion_id || f.criterion
    if (!criterionSeen[id]) {
      criterionSeen[id] = { id, name: f.criterion || id, cells: {} }
      criteria.push(criterionSeen[id])
    }
    criterionSeen[id].cells[f.rep_number] = f
  })
  const visibleCriteria = criteria.filter(
    (c) => filter === 'all' || Object.values(c.cells).some((f) => f.result === filter)
  )

  return (
    <section className="pg-root">
      <style>{PG_CSS}</style>

      {/* HEADER */}
      <div className="pg-header">
        <span className="pg-eyebrow">ANALYSIS COMPLETE / 03</span>
        <h2>Squat assessment</h2>
        <p>
          Model 1 extracted the movement measurements and Model 2 evaluated
          those measurements against the configured squat standard.
        </p>
      </div>

      {/* OVERALL MODEL 2 RESULT */}
      <section className="pg-card">
        <div className="pg-card-head">
          <div>
            <span className="pg-eyebrow">MODEL 2 / OVERALL</span>
            <h3>Overall assessment</h3>
          </div>
          <span className="pg-model-badge">{modelUsed}</span>
        </div>

        <p className="pg-summary">{overallSummary}</p>

        <div className="pg-stats">
          <Stat label="Reps detected" value={reps.length} />
          <Stat label="Meets standard" value={counts.meets_standard} tone="meets" />
          <Stat label="Does not meet" value={counts.does_not_meet_standard} tone="fails" />
          <Stat label="Cannot assess" value={counts.cannot_assess} tone="unknown" />
        </div>

        {results.low_quality_warning && <p className="pg-warning">{results.low_quality_warning}</p>}
      </section>

      {/* MODEL 1 REP MEASUREMENTS */}
      <section className="pg-card">
        <div className="pg-card-head">
          <div>
            <span className="pg-eyebrow">MODEL 1 / MEASUREMENTS</span>
            <h3>Rep-by-rep movement data</h3>
          </div>
          <span>{reps.length} reps</span>
        </div>

        {reps.length === 0 ? (
          <p className="pg-empty">No rep measurements were returned.</p>
        ) : (
          <div className="pg-grid" style={gridStyle}>
            <div className="pg-cell pg-corner">Measurement</div>
            {reps.map((rep) => (
              <div key={rep.rep_number} className="pg-cell pg-col-head">
                <strong>Rep {rep.rep_number}</strong>
                <small>Bottom at {fmtTime(rep.bottom_timestamp_s)}</small>
              </div>
            ))}

            {MEASURE_ROWS.map((row, i) => {
              const last = i === MEASURE_ROWS.length - 1 ? ' pg-last' : ''
              return (
                <RowFragment key={row.key}>
                  <div className={`pg-cell pg-label${last}`}>{row.label}</div>
                  {reps.map((rep) => (
                    <div key={rep.rep_number} className={`pg-cell pg-data${last}`}>
                      <span className="pg-val">{fmt((rep.measurements || {})[row.key], row.suffix)}</span>
                    </div>
                  ))}
                </RowFragment>
              )
            })}
          </div>
        )}
      </section>

      {/* TRACKING CONFIDENCE */}
      {reps.length > 0 && (
        <section className="pg-card">
          <div className="pg-card-head">
            <div>
              <span className="pg-eyebrow">MODEL 1 / TRACKING</span>
              <h3>Tracking confidence</h3>
            </div>
          </div>

          <div className="pg-grid" style={gridStyle}>
            <div className="pg-cell pg-corner">Body point</div>
            {reps.map((rep) => (
              <div key={rep.rep_number} className="pg-cell pg-col-head">
                <strong>Rep {rep.rep_number}</strong>
              </div>
            ))}

            {CONFIDENCE_ROWS.map((row) => (
              <RowFragment key={row.key}>
                <div className="pg-cell pg-label">{row.label}</div>
                {reps.map((rep) => (
                  <div key={rep.rep_number} className="pg-cell pg-data">
                    <Confidence value={(rep.tracking_confidence || {})[row.key]} />
                  </div>
                ))}
              </RowFragment>
            ))}

            <div className="pg-cell pg-label pg-last">Tracking notes</div>
            {reps.map((rep) => {
              const notes = rep.occlusion_flags || []
              return (
                <div key={rep.rep_number} className="pg-cell pg-data pg-last">
                  {notes.length === 0 ? (
                    <span className="pg-muted">None</span>
                  ) : (
                    <div className="pg-tags">
                      {notes.map((n) => (
                        <span key={n} className="pg-tag">{NOTE_LABELS[n] || n}</span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* MODEL 2 FINDINGS */}
      <section className="pg-card">
        <div className="pg-card-head">
          <div>
            <span className="pg-eyebrow">MODEL 2 / FINDINGS</span>
            <h3>Detailed AI findings</h3>
          </div>
          <span>{findings.length} findings</span>
        </div>

        {findings.length === 0 ? (
          <p className="pg-empty">No specific findings were returned by Model 2.</p>
        ) : (
          <>
            <div className="pg-filters" role="tablist" aria-label="Filter findings">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={`pg-filter${filter === f.key ? ' active' : ''}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                  <span>{f.key === 'all' ? findings.length : counts[f.key]}</span>
                </button>
              ))}
            </div>

            <div className="pg-grid" style={gridStyle}>
              <div className="pg-cell pg-corner">Criterion</div>
              {repNumbers.map((n) => (
                <div key={n} className="pg-cell pg-col-head">
                  <strong>Rep {n}</strong>
                  {repByNumber[n] && <small>Bottom at {fmtTime(repByNumber[n].bottom_timestamp_s)}</small>}
                </div>
              ))}

              {visibleCriteria.length === 0 && (
                <div className="pg-empty" style={{ gridColumn: '1 / -1' }}>No findings in this category.</div>
              )}

              {visibleCriteria.map((c, i) => {
                const last = i === visibleCriteria.length - 1 ? ' pg-last' : ''
                return (
                  <RowFragment key={c.id}>
                    <div className={`pg-cell pg-label${last}`}>{c.name}</div>
                    {repNumbers.map((n) => (
                      <FindingCell
                        key={n}
                        finding={c.cells[n]}
                        last={last}
                        dim={filter !== 'all' && c.cells[n] && c.cells[n].result !== filter}
                      />
                    ))}
                  </RowFragment>
                )
              })}
            </div>
          </>
        )}
      </section>
    </section>
  )
}

/* display: contents keeps every cell a direct grid item so rows line up */
function RowFragment({ children }) {
  return <div style={{ display: 'contents' }}>{children}</div>
}

function FindingCell({ finding, last, dim }) {
  if (!finding) {
    return (
      <div className={`pg-cell pg-data${last}`}>
        <span className="pg-muted">--</span>
      </div>
    )
  }
  const pages = finding.source_pages || (finding.source_page ? [finding.source_page] : [])
  const measurement = finding.observed_measurement || finding.measurement

  return (
    <div className={`pg-cell pg-data pg-finding${dim ? ' pg-dim' : ''}${last}`}>
      <span className={RESULT_CLASSES[finding.result] || 'pg-badge pg-unknown'}>
        {RESULT_LABELS[finding.result] || finding.result}
      </span>
      {measurement && (
        <div className="pg-block pg-measure">{measurement}</div>
      )}
      {finding.explanation && (
        <div className="pg-block"><em>Why</em>{finding.explanation}</div>
      )}
      {finding.feedback && (
        <div className="pg-block"><em>Feedback</em>{finding.feedback}</div>
      )}
      {finding.uncertainty && (
        <div className="pg-block pg-uncertain"><em>Uncertainty</em>{finding.uncertainty}</div>
      )}
      {pages.length > 0 && (
        <div className="pg-block"><em>Ref. pages</em>{pages.join(', ')}</div>
      )}
    </div>
  )
}

function Stat({ label, value, tone }) {
  return (
    <div className={`pg-stat${tone ? ` pg-stat-${tone}` : ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function Confidence({ value }) {
  const pct = typeof value === 'number' ? Math.round(value * 100) : null
  return (
    <div className="pg-conf">
      <strong>{pct !== null ? `${pct}%` : '--'}</strong>
      <div className="pg-bar">
        <div className="pg-bar-fill" style={{ width: pct !== null ? `${pct}%` : '0%' }} />
      </div>
    </div>
  )
}
