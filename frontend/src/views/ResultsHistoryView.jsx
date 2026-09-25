import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ResultsView from '../components/ResultsView.jsx'
import { getResultsHistory, getStatus } from '../api.js'

function formatDate(value) {
  if (!value) return 'Unknown date'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString()
}

export default function ResultsHistoryView() {
  const { jobId } = useParams()
  return jobId ? <ResultDetail jobId={jobId} /> : <ResultsList />
}

/* ---------- list of every saved analysis (from MongoDB) ---------- */

function ResultsList() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    getResultsHistory()
      .then(setItems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div className="analyze-page">
      <div className="container analyze-head">
        <div>
          <p className="eyebrow">RESULTS ARCHIVE / 04</p>
          <h1>Past analyses.</h1>
          <p>Every squat analysis saved in the database.</p>
        </div>
        <span className="mono head-index">{items.length} SAVED</span>
      </div>

      <div className="container">
        {loading && <p className="hint">Loading results…</p>}

        {!loading && error && (
          <div className="error-block">
            <span className="eyebrow">COULD NOT LOAD RESULTS</span>
            <p className="error-text">{error}</p>
            <button type="button" className="btn-ghost" onClick={load}>Retry</button>
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="error-block">
            <span className="eyebrow">NOTHING SAVED YET</span>
            <p>Run an analysis and it will show up here.</p>
            <Link to="/analyze" className="btn-ghost">Start analysis ↗</Link>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="history-grid">
            {items.map((item) => {
              const reps = item.results?.video_data?.reps?.length
              const findings = item.results?.findings?.length
              const summary = item.results?.overall_summary

              return (
                <button
                  key={item.id}
                  type="button"
                  className="result-card history-card"
                  onClick={() => navigate(`/results/${item.id}`)}
                >
                  <div className="result-card-header">
                    <div>
                      <span className="eyebrow">{item.status.toUpperCase()}</span>
                      <h3>{item.filename || `Job ${item.id.slice(0, 8)}`}</h3>
                    </div>
                    <span className="mono">{formatDate(item.createdAt)}</span>
                  </div>

                  {summary && <p className="history-summary">{summary}</p>}

                  <div className="history-meta mono">
                    <span>{reps ?? '--'} reps</span>
                    <span>{findings ?? '--'} findings</span>
                    <span>Open ↗</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------- one saved analysis, read straight from MongoDB ---------- */

function ResultDetail({ jobId }) {
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setResults(null)
    setError('')

    getStatus(jobId)
      .then((data) => {
        if (cancelled) return
        if (data.status === 'error') {
          setError(data.error || 'This analysis failed.')
        } else if (!data.results) {
          setError(`This analysis is still "${data.stage_label || data.status}". Check back shortly.`)
        } else {
          setResults(data.results)
        }
      })
      .catch((err) => !cancelled && setError(err.message))

    return () => { cancelled = true }
  }, [jobId])

  return (
    <div className="analyze-page">
      <div className="container">
        <Link to="/results" className="btn-ghost restart">← All results</Link>

        {!results && !error && <p className="hint">Loading analysis…</p>}

        {error && (
          <div className="error-block">
            <span className="eyebrow">COULD NOT LOAD ANALYSIS</span>
            <p className="error-text">{error}</p>
          </div>
        )}

        {results && <ResultsView results={results} />}
      </div>
    </div>
  )
}
