export const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function getToken() {
  return localStorage.getItem('leximind-token')
}

async function request(method, path, body = null, isFormData = false) {
  const headers = isFormData ? {} : { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : null,
  })

  if (!res.ok) {
    // B5: an authenticated request was rejected -> session expired/invalid.
    // Login/register also return 401 (wrong password), so exclude them.
    // getToken() === token guards against a late 401 from an old token
    // logging out someone who has just logged in again.
    if (
      res.status === 401 &&
      token &&
      getToken() === token &&
      path !== '/auth/login' &&
      path !== '/auth/register'
    ) {
      window.dispatchEvent(new Event('auth-expired'))
    }
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    const error = new Error(err.detail || 'Request failed')
    error.status = res.status
    throw error
  }

  return res.json()
}

export const api = {
  get:  path => request('GET', path),
  post: (path, body) => request('POST', path, body),
  postForm: (path, formData) => request('POST', path, formData, true),
  patch: (path, body) => request('PATCH', path, body),
  put: (path, body) => request('PUT', path, body),
  delete: path => request('DELETE', path),
}