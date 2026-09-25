import { useRef, useState } from 'react'
import { uploadVideo } from '../api.js'

export default function UploadPanel({ onUploaded }) {
  const fileInput = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  function validateFile(file) {
    if (!file) return false

    const allowedTypes = [
      'video/mp4',
      'video/quicktime',
      'video/webm',
    ]

    const allowedExtensions = [
      '.mp4',
      '.mov',
      '.webm',
    ]

    const fileName = file.name.toLowerCase()

    const validType =
      allowedTypes.includes(file.type) ||
      allowedExtensions.some((ext) =>
        fileName.endsWith(ext)
      )

    if (!validType) {
      setErrorMessage(
        'Please select an MP4, MOV, or WebM video.'
      )
      return false
    }

    // 250 MB frontend safety check
    const maxSize =
      250 * 1024 * 1024

    if (file.size > maxSize) {
      setErrorMessage(
        'Video must be smaller than 250 MB.'
      )
      return false
    }

    setErrorMessage('')
    return true
  }

  function onSelect(e) {
    const file = e.target.files?.[0]

    if (file && validateFile(file)) {
      setSelectedFile(file)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setIsDragging(false)

    const file =
      e.dataTransfer.files?.[0]

    if (file && validateFile(file)) {
      setSelectedFile(file)
    }
  }

  async function submit() {
    if (!selectedFile) {
      setErrorMessage(
        'Please select a video first.'
      )
      return
    }

    setSubmitting(true)
    setErrorMessage('')

    try {
      const response =
        await uploadVideo(selectedFile)

      const jobId =
        response?.job_id

      if (!jobId) {
        throw new Error(
          'Backend did not return a job ID.'
        )
      }

      onUploaded?.(jobId)

    } catch (err) {
      console.error(
        'Video upload failed:',
        err
      )

      setErrorMessage(
        err?.message ||
        'Upload failed. Try again.'
      )

    } finally {
      setSubmitting(false)
    }
  }

  function removeSelectedFile() {
    setSelectedFile(null)
    setErrorMessage('')

    if (fileInput.current) {
      fileInput.current.value = ''
    }
  }

  return (
    <section className="upload-panel reveal is-visible">

      <div className="upload-shell">

        <div className="upload-copy">

          <span className="eyebrow">
            VIDEO INPUT / 01
          </span>

          <h2>
            Drop the set.
            <br />
            <em>We'll read the rep.</em>
          </h2>

          <p>
            One side-view clip is enough to
            start. The cleaner the frame, the
            more confidently the movement can
            be assessed.
          </p>

        </div>

        <div
          className={`dropzone${
            isDragging ? ' over' : ''
          }`}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={(e) => {
            e.preventDefault()
            setIsDragging(false)
          }}
          onDrop={onDrop}
          onClick={() =>
            fileInput.current?.click()
          }
        >

          <input
            ref={fileInput}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
            className="hidden-input"
            onChange={onSelect}
          />

          <div
            className="upload-orbit"
            aria-hidden="true"
          >
            ↑
          </div>

          <strong>
            Drop video here
          </strong>

          <span>
            or click to browse
          </span>

          <small>
            MP4 / MOV / WebM · up to 60 seconds
          </small>

        </div>

      </div>

      {selectedFile && (

        <div className="selected-row">

          <div>

            <span className="eyebrow">
              SELECTED CLIP
            </span>

            <span className="mono file-name">
              {selectedFile.name}
            </span>

            <small>
              {' '}
              ·{' '}
              {(
                selectedFile.size /
                (1024 * 1024)
              ).toFixed(2)} MB
            </small>

          </div>

          <div className="selected-actions">

            <button
              type="button"
              className="btn-secondary"
              onClick={removeSelectedFile}
              disabled={submitting}
            >
              Remove
            </button>

            <button
              type="button"
              className="btn-primary"
              disabled={submitting}
              onClick={submit}
            >
              {submitting
                ? 'Uploading…'
                : 'Analyze squat ↗'}
            </button>

          </div>

        </div>

      )}

      {errorMessage && (
        <p className="error-text">
          {errorMessage}
        </p>
      )}

      <div className="requirements">

        <div>
          <span className="req-number">
            01
          </span>

          <strong>
            True side view
          </strong>

          <p>
            Camera perpendicular to the lifter.
          </p>
        </div>

        <div>
          <span className="req-number">
            02
          </span>

          <strong>
            Full body in frame
          </strong>

          <p>
            Keep the bar, feet and full rep visible.
          </p>
        </div>

        <div>
          <span className="req-number">
            03
          </span>

          <strong>
            Steady lighting
          </strong>

          <p>
            Plain background and a stable camera help.
          </p>
        </div>

      </div>

    </section>
  )
}