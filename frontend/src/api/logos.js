import client from './client.js'

export const logosApi = {
  list: () => client.get('/logos').then((r) => r.data),
  upload: (nom, fichier) => {
    const form = new FormData()
    form.append('nom', nom)
    form.append('fichier', fichier)
    return client.post('/logos', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  setUtiliserCouleurs: (id, value) =>
    client.patch(`/logos/${id}`, { utiliser_couleurs: value }).then((r) => r.data),
  delete: (id) => client.delete(`/logos/${id}`),
  imageUrl: (id) => (id ? `/api/logos/${id}/image` : '/lateb_logo.svg'),
}
