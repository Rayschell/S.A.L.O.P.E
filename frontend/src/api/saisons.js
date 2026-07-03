import client from './client.js'

export const saisonsApi = {
  list: () => client.get('/saisons').then((r) => r.data),
  create: (payload) => client.post('/saisons', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/saisons/${id}`, payload).then((r) => r.data),
  delete: (id) => client.delete(`/saisons/${id}`),
}
