import {
  useEffect,
  useRef,
  useState,
} from 'react'

import { getStatus } from '../api.js'

const STAGES = [
  {
    key: 'retrieving_video',
    label: 'Retrieving uploaded video',
  },
  {
    key: 'tracking',
    label: 'Tracking body and bar',
  },
  {
    key: 'detecting_reps',
    label: 'Detecting repetitions',
  },
  {
    key: 'building_model_data',
    label: 'Building movement measurements',
  },
  {
    key: 'assessing',
    label: 'AI assessment',
  },
  {
    key: 'annotating',
    label: 'Rendering annotated video',
  },
]

export default function ProcessingStatus({
  jobId,
  onComplete,
  onFailed,
}) {
  const [currentStage, setCurrentStage] =
    useState('retrieving_video')

  const [stageLabel, setStageLabel] =
    useState('Starting up…')

  const [errorMessage, setErrorMessage] =
    useState('')

  const timerRef = useRef(null)

  const onCompleteRef =
    useRef(onComplete)

  const onFailedRef =
    useRef(onFailed)

  onCompleteRef.current =
    onComplete

  onFailedRef.current =
    onFailed

  function getStageIndex(stage) {
    return STAGES.findIndex(
      (item) => item.key === stage
    )
  }

  function isPast(key) {
    const currentIndex =
      getStageIndex(currentStage)

    const stageIndex =
      getStageIndex(key)

    if (currentIndex === -1) {
      return false
    }

    return stageIndex < currentIndex
  }

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const data =
          await getStatus(jobId)

        if (cancelled) return

        if (data.stage) {
          setCurrentStage(
            data.stage
          )
        }

        if (data.stage_label) {
          setStageLabel(
            data.stage_label
          )
        }

        if (data.status === 'done') {

          clearInterval(
            timerRef.current
          )

          onCompleteRef.current?.(
            data.results || {}
          )

        } else if (
          data.status === 'error'
        ) {

          clearInterval(
            timerRef.current
          )

          const msg =
            data.error ||
            'Something went wrong while processing.'

          setErrorMessage(msg)

          onFailedRef.current?.(msg)
        }

      } catch (err) {

        console.error(
          'Status polling error:',
          err
        )
      }
    }

    poll()

    timerRef.current =
      setInterval(
        poll,
        2000
      )

    return () => {
      cancelled = true

      clearInterval(
        timerRef.current
      )
    }

  }, [jobId])

  return (
    <section className="status-panel">

      <div
        className="spinner"
        aria-hidden="true"
      />

      <p className="stage-label">
        {stageLabel}
      </p>

      <ol className="stage-list">

        {STAGES.map((stage) => (

          <li
            key={stage.key}
            className={[
              stage.key === currentStage
                ? 'active'
                : '',
              isPast(stage.key)
                ? 'done'
                : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >

            <span className="dot" />

            {stage.label}

          </li>

        ))}

      </ol>

      {errorMessage && (
        <p className="error-text">
          {errorMessage}
        </p>
      )}

    </section>
  )
}