import client from './client.js'

export const eventsApi = {
  // Events
  list: () => client.get('/events').then((r) => r.data),
  get: (id) => client.get(`/events/${id}`).then((r) => r.data),
  create: (payload) => client.post('/events', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/events/${id}`, payload).then((r) => r.data),
  delete: (id) => client.delete(`/events/${id}`),
  publish: (id) => client.post(`/events/${id}/publish`).then((r) => r.data),

  // CSV
  importCsv: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post(`/events/${id}/import-csv`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  resolvePending: (id, resolutions) =>
    client.post(`/events/${id}/resolve-pending`, { resolutions }).then((r) => r.data),

  // Slots
  listSlots: (id) => client.get(`/events/${id}/slots`).then((r) => r.data),
  updateSlot: (eventId, slotId, payload) =>
    client.put(`/events/${eventId}/slots/${slotId}`, payload).then((r) => r.data),

  // Respos bar
  listResposBar: (id) => client.get(`/events/${id}/respos-bar`).then((r) => r.data),
  setResposBar: (id, respos) =>
    client.put(`/events/${id}/respos-bar`, { respos }).then((r) => r.data),

  // Affinities
  listAffinities: (id) => client.get(`/events/${id}/affinities`).then((r) => r.data),
  addAffinity: (id, payload) =>
    client.post(`/events/${id}/affinities`, payload).then((r) => r.data),
  deleteAffinity: (eventId, affId) =>
    client.delete(`/events/${eventId}/affinities/${affId}`),

  // Assignments
  listAssignments: (id) => client.get(`/events/${id}/assignments`).then((r) => r.data),
  addAssignment: (id, payload) =>
    client.post(`/events/${id}/assignments`, payload).then((r) => r.data),
  updateAssignment: (eventId, asgId, payload) =>
    client.put(`/events/${eventId}/assignments/${asgId}`, payload).then((r) => r.data),
  deleteAssignment: (eventId, asgId) =>
    client.delete(`/events/${eventId}/assignments/${asgId}`),

  // Availabilities
  listAvailabilities: (id) => client.get(`/events/${id}/availabilities`).then((r) => r.data),

  // Generate
  generate: (id, excludedMemberIds = []) =>
    client.post(`/events/${id}/generate`, { excluded_member_ids: excludedMemberIds }).then((r) => r.data),

  // Export
  exportPngUrl: (id) => `/api/events/${id}/export-png`,
}
