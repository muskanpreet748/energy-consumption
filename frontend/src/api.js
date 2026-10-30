// Single place that talks to the backend.
//
// VITE_API_BASE_URL is empty in development (Vite proxies /api) and can be
// set at build time when the API is hosted on a different origin.
const BASE = import.meta.env.VITE_API_BASE_URL || ''

export class ApiError extends Error {
  constructor(path, status, detail) {
    super(`${path} -> ${status}${detail ? `: ${detail}` : ''}`)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function getJSON(path, params = undefined) {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value)
      }
    })
  }

  let response
  try {
    response = await fetch(url.toString())
  } catch (networkError) {
    throw new ApiError(path, 0, 'network unreachable')
  }

  if (!response.ok) {
    let detail = ''
    try {
      detail = (await response.json()).detail || ''
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(path, response.status, detail)
  }

  return response.json()
}
