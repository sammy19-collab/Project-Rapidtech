import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const uploadBooks = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload/books', fd)
}

export const uploadGSTR2B = (sessionId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/upload/gstr2b/${sessionId}`, fd)
}

export const runReconciliation = (sessionId) => api.post(`/reconcile/${sessionId}`)

export const getResults = (sessionId) => api.get(`/results/${sessionId}`)
export const getReconciled = (sessionId) => api.get(`/results/${sessionId}/reconciled`)
export const getProbable = (sessionId) => api.get(`/results/${sessionId}/probable`)
export const getMissingInBooks = (sessionId) => api.get(`/results/${sessionId}/missing-in-books`)
export const getMissingInGSTR2B = (sessionId) => api.get(`/results/${sessionId}/missing-in-gstr2b`)

export const getDashboard = (sessionId) => api.get(`/dashboard/${sessionId}`)

export const getTallyPreview = (sessionId) => api.get(`/tally/${sessionId}/preview`)
export const downloadTallyXml = (sessionId) => api.get(`/tally/${sessionId}/xml`, { responseType: 'blob' })

export const getSessions = () => api.get('/sessions')
