import client from './client.js'

export const membersApi = {
  list: () => client.get('/members').then((r) => r.data),
  get: (id) => client.get(`/members/${id}`).then((r) => r.data),
  create: (payload) => client.post('/members', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/members/${id}`, payload).then((r) => r.data),
  delete: (id) => client.delete(`/members/${id}`),
  resetCounters: (id) => client.post(`/members/${id}/reset-counters`).then((r) => r.data),
  resetAllCounters: () => client.post('/members/reset-all-counters'),
  getStats: (id, saisonId = null) =>
    client.get(`/members/${id}/stats`, { params: saisonId ? { saison_id: saisonId } : {} }).then((r) => r.data),
  getTimeline: (id, saisonId = null) =>
    client.get(`/members/${id}/timeline`, { params: saisonId ? { saison_id: saisonId } : {} }).then((r) => r.data),
  statsOverview: (saisonId = null) =>
    client.get('/members/stats-overview', { params: saisonId ? { saison_id: saisonId } : {} }).then((r) => r.data),
  addAlias: (id, valeur) => client.post(`/members/${id}/aliases`, { valeur }).then((r) => r.data),
  deleteAlias: (id, aliasId) => client.delete(`/members/${id}/aliases/${aliasId}`),
  merge: (id, sourceMemberId) => client.post(`/members/${id}/merge`, { source_member_id: sourceMemberId }).then((r) => r.data),
}
