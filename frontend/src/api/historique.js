import client from './client.js'

export const historiqueApi = {
  preview: (file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post('/import-historique/preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  commit: (payload) =>
    client.post('/import-historique/commit', payload).then((r) => r.data),
}
