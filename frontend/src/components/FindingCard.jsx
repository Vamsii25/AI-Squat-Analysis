const RESULT_LABELS = {
  meets_standard: 'Meets standard',
  does_not_meet_standard: 'Does not meet',
  cannot_assess: 'Cannot assess'
}

const BADGE_CLASSES = {
  meets_standard: 'badge-meets',
  does_not_meet_standard: 'badge-fails',
  cannot_assess: 'badge-unknown'
}

function formatTime(seconds) {
  const t = seconds || 0
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export default function FindingCard({ finding, onSeek }) {
  const resultLabel = RESULT_LABELS[finding.result] || finding.result
  const badgeClass = BADGE_CLASSES[finding.result] || 'badge-unknown'

  return (
    <article className="finding">
      <div className="finding-head">
        <span className={`badge ${badgeClass}`}>{resultLabel}</span>
        <button type="button" className="btn-ghost mono" onClick={() => onSeek?.(finding.timestamp_seconds)}>
          {formatTime(finding.timestamp_seconds)}
        </button>
      </div>
      <h4 className="criterion">{finding.criterion}</h4>
      {finding.measurement && <p className="measurement mono">{finding.measurement}</p>}
      <p className="explanation">{finding.explanation}</p>
      {finding.feedback && <p className="feedback">{finding.feedback}</p>}
      {finding.uncertainty && <p className="uncertainty">Uncertainty: {finding.uncertainty}</p>}
      <p className="source">Reference p.{finding.source_page}</p>
    </article>
  )
}
