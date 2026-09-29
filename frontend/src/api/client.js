/**
 * Thin wrapper around the ArchiGen REST API.
 *
 * In development Vite proxies `/api/*` to the FastAPI server on
 * `http://localhost:8000` and strips the prefix (see `vite.config.js`), so
 * the defaults below work with no extra configuration.
 */
import { MOCK_HEALTH, MOCK_HISTORY, mockGenerate } from './mock'

const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** @type {boolean} */
export const usingMock = String(import.meta.env.VITE_USE_MOCK ?? '').toLowerCase() === 'true'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    // Network-level failure: the backend is probably not running.
    throw new Error(
      'Could not reach the API. Start the backend (uvicorn src.api.main:app) or enable mock mode.',
    )
  }

  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      detail = body?.detail || body?.error || ''
    } catch {
      // Response was not JSON; fall back to the status line.
    }
    throw new Error(detail || `Request failed: ${response.status} ${response.statusText}`)
  }

  const contentType = response.headers.get('content-type') || ''
  return contentType.includes('application/json') ? response.json() : response.text()
}

export const api = {
  /** @returns {Promise<import('./types').HealthResponse>} */
  async health() {
    if (usingMock) {
      return { ...MOCK_HEALTH }
    }
    return request('/health')
  },

  /**
   * @param {import('./types').GenerateRequest} payload
   * @returns {Promise<import('./types').GenerateResponse>}
   */
  async generate(payload) {
    if (usingMock) {
      return mockGenerate(payload)
    }
    return request('/generate', { method: 'POST', body: JSON.stringify(payload) })
  },

  /**
   * @param {number} [limit]
   * @returns {Promise<import('./types').HistoryEntry[]>}
   */
  async history(limit = 10) {
    if (usingMock) {
      return MOCK_HISTORY.slice(0, limit)
    }
    const data = await request(`/history?limit=${encodeURIComponent(limit)}`)
    return Array.isArray(data) ? data : (data?.entries ?? [])
  },
}
