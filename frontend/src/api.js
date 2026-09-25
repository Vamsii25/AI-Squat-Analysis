const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const API_PREFIX = `${API_BASE_URL}/api`

export const BACKEND_URL = API_BASE_URL || 'http://localhost:8000'

function buildBackendUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  return `${BACKEND_URL}${path.startsWith('/') ? path : `/${path}`}`
}

/**
 * Upload a video to FastAPI.
 * FastAPI endpoint: POST /api/upload
 * Multipart field: "video"
 */
export async function uploadVideo(file, onProgress) {
  if (!file) throw new Error('Please select a video file.')

  const form = new FormData()
  form.append('video', file)

  const res = await fetch(`${API_PREFIX}/upload`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const body = await safeJson(res)
    throw new Error(body?.detail || `Upload failed (${res.status})`)
  }

  const data = await res.json()
  onProgress?.(100)
  return data
}

/**
 * Poll FastAPI for the processing status.
 * GET /api/status/{jobId}
 */
export async function getStatus(jobId) {
  const res = await fetch(`${API_PREFIX}/status/${encodeURIComponent(jobId)}`)
  if (!res.ok) {
    const body = await safeJson(res)
    throw new Error(body?.detail || `Status check failed (${res.status})`)
  }

  const data = await res.json()

  // FastAPI returns video_url as /media/<file>. Make it directly playable
  // from the backend instead of accidentally requesting it from Vite.
  if (data.results?.video_url) {
    data.results.video_url = buildBackendUrl(data.results.video_url)
  }

  return data
}

/**
 * Check FastAPI and MongoDB connectivity.
 * GET /api/health
 */
export async function checkBackendHealth() {
  const res = await fetch(`${API_PREFIX}/health`)
  const data = await safeJson(res)

  if (!res.ok) {
    throw new Error(data?.detail || `Backend health check failed (${res.status})`)
  }

  return data
}

async function safeJson(res) {
  try {
    return await res.json()
  } catch {
    return null
  }
}

/**
 * List saved analyses stored in MongoDB.
 * Primary endpoint: GET /api/results?limit=N
 * (falls back to /api/history and /api/jobs if your backend uses those names)
 */
const HISTORY_ENDPOINTS = ['results', 'history', 'jobs']

export async function getResultsHistory(limit = 50) {
  let lastError = null

  for (const name of HISTORY_ENDPOINTS) {
    try {
      const res = await fetch(`${API_PREFIX}/${name}?limit=${limit}`)

      if (res.status === 404 || res.status === 405) {
        lastError = new Error(
          `Backend has no GET /api/${HISTORY_ENDPOINTS[0]} route yet (see BACKEND_HISTORY_ROUTE.md).`
        )
        continue
      }

      if (!res.ok) {
        const body = await safeJson(res)
        throw new Error(body?.detail || `Could not load results (${res.status})`)
      }

      const data = await res.json()
      const raw = Array.isArray(data)
        ? data
        : data.items || data.results || data.jobs || []

      return raw.map(normalizeJob)
    } catch (err) {
      // Network error / backend down: stop trying other names.
      if (err instanceof TypeError) {
        throw new Error('Cannot reach the backend. Is FastAPI running on port 8000?')
      }
      lastError = err
      if (!/no GET/.test(err.message)) throw err
    }
  }

  throw lastError || new Error('Could not load results.')
}

function normalizeJob(doc) {
  const results = doc.results || {}
  if (results.video_url) results.video_url = buildBackendUrl(results.video_url)

  return {
    id: doc.job_id || doc.id || (typeof doc._id === 'string' ? doc._id : doc._id?.$oid) || '',
    status: doc.status || (doc.results ? 'done' : 'unknown'),
    createdAt: doc.created_at || doc.createdAt || doc.timestamp || null,
    filename: doc.filename || doc.original_filename || doc.video_name || '',
    results,
  }
}
