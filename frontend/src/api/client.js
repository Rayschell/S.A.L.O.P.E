import axios from 'axios'
import { toast } from '../components/ui/Toaster.jsx'

// Auth par cookies httpOnly (posés par le backend) — rien n'est stocké côté JS.
const client = axios.create({
  baseURL: '/api',
})

// Attempt token refresh on 401 (cookie-based), then retry the original request
client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && !original._retry && !isAuthCall) {
      original._retry = true
      try {
        await axios.post('/api/auth/refresh')
        return client(original)
      } catch {
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }
    if (error.response?.status !== 401) {
      const detail = error.response?.data?.detail
      if (typeof detail === 'string') {
        toast.error(detail)
      } else if (error.response?.status) {
        toast.error(`Erreur serveur (${error.response.status})`)
      } else {
        toast.error('Erreur réseau')
      }
    }
    return Promise.reject(error)
  }
)

export default client
