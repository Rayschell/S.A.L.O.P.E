import axios from 'axios'
import client from './client.js'

// Les tokens vivent dans des cookies httpOnly ; login/refresh renvoient le membre.
export const authApi = {
  login: async (email, password) => {
    const { data } = await axios.post('/api/auth/login', { email, password })
    return data
  },
  logout: async () => {
    await axios.post('/api/auth/logout')
  },
  me: async () => {
    const { data } = await client.get('/auth/me')
    return data
  },
}
