import client from './client.js'

export const membersApi = {
  list: () => client.get('/members').then((r) => r.data),
  get: (id) => client.get(`/members/${id}`).then((r) => r.data),
  create: (payload) => client.post('/members', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/members/${id}`, payload).then((r) => r.data),
  delete: (id) => client.delete(`/members/${id}`),
  resetCounters: (id) => client.post(`/members/${id}/reset-counters`).then((r) => r.data),
  resetAllCounters: () => client.post('/members/reset-all-counters'),
}
