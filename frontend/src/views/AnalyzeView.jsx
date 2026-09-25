import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import UploadPanel from '../components/UploadPanel.jsx'
import ProcessingStatus from '../components/ProcessingStatus.jsx'
import ResultsView from '../components/ResultsView.jsx'
import { checkBackendHealth } from '../api.js'

export default function AnalyzeView() {
  const { jobId: routeJobId } = useParams()
  const navigate = useNavigate()

  const [stage, setStage] = useState(routeJobId ? 'processing' : 'upload')
  const [currentJobId, setCurrentJobId] = useState(routeJobId || '')
  const [results, setResults] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [backendState, setBackendState] = useState('checking')

  useEffect(() => {
    checkBackendHealth()
      .then((data) => {
        setBackendState(data?.mongodb === 'connected' ? 'connected' : 'backend-only')
      })
      .catch(() => setBackendState('offline'))
  }, [])

  useEffect(() => {
    if (routeJobId) {
      setCurrentJobId(routeJobId)
      setStage('processing')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function onUploaded(id) {
    setCurrentJobId(id)
    setStage('processing')
    navigate(`/analyze/${id}`, { replace: true })
  }

  function onComplete(data) {
    setResults(data)
    setStage('results')
  }

  function onFailed(msg) {
    setErrorMessage(msg)
    setStage('error')
  }

  function reset() {
    setCurrentJobId('')
    setResults(null)
    setErrorMessage('')
    setStage('upload')
    navigate('/analyze', { replace: true })
  }

  return (
    <div className="analyze-page">
      {stage !== 'results' && (
        <div className="container analyze-head">
          <div>
            <p className="eyebrow">ANALYSIS STUDIO / 02</p>
            <h1>Read the movement.</h1>
            <p>Upload a side-view video and we'll walk through it rep by rep.</p>
          </div>
          <span className="mono head-index">
            01 — INPUT · {backendState === 'connected' ? 'API / DB CONNECTED' : backendState === 'offline' ? 'API OFFLINE' : 'CHECKING API / DB'}
          </span>
        </div>
      )}

      <div className="container">
        {stage === 'upload' && <UploadPanel onUploaded={onUploaded} />}
        {stage === 'processing' && (
          <ProcessingStatus
            jobId={currentJobId}
            onComplete={onComplete}
            onFailed={onFailed}
          />
        )}
        {stage === 'error' && (
          <div className="error-block">
            <span className="eyebrow">ANALYSIS ERROR</span>
            <p className="error-text">{errorMessage}</p>
            <button type="button" className="btn-ghost" onClick={reset}>Try another video</button>
          </div>
        )}
        {stage === 'results' && results && (
          <>
            <ResultsView results={results} />
            <button type="button" className="btn-ghost restart" onClick={reset}>← Analyze another video</button>
            <Link to="/results" className="btn-ghost restart">View all saved results →</Link>
          </>
        )}
      </div>
    </div>
  )
}
