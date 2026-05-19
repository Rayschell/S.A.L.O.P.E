import axios from 'axios'
import client from './client.js'

export const authApi = {
  login: async (email, password) => {
    const { data } = await axios.post('/api/auth/login', { email, password })
    return data
  },
  refresh: async (refreshToken) => {
    const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
    return data
  },
  me: async () => {
    const { data } = await client.get('/auth/me')
    return data
  },
}
