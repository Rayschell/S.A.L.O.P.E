import axios from 'axios'

// Client dédié aux routes publiques (page /dispo/:token, sans auth).
// Volontairement SANS les interceptors de client.js : pas de refresh de token,
// pas de redirect /login, pas de toasts globaux.
const publicClient = axios.create({
  baseURL: '/api/public',
})

export const publicApi = {
  getPoll: (token) => publicClient.get(`/polls/${token}`).then((r) => r.data),
  submit: (token, payload) =>
    publicClient.post(`/polls/${token}`, payload).then((r) => r.data),
}
