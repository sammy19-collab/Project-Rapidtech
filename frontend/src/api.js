import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getBranches = () => api.get('/branches')

export const uploadBooks = (file, branch, reconMonth) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('branch', branch)
  fd.append('recon_month', reconMonth)
  return api.post('/upload/books', fd)
}

export const uploadGSTR2B = (sessionId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/upload/gstr2b/${sessionId}`, fd)
}

export const runReconciliation = (sessionId) => api.post(`/reconcile/${sessionId}`)

export const getAvailableMonths = (sessionId) => api.get(`/results/${sessionId}/months`)
export const getResults = (sessionId, monthYear) => api.get(`/results/${sessionId}`, { params: monthYear ? { month_year: monthYear } : {} })
export const getReconciled = (sessionId, monthYear) => api.get(`/results/${sessionId}/reconciled`, { params: monthYear ? { month_year: monthYear } : {} })
export const getProbable = (sessionId, monthYear) => api.get(`/results/${sessionId}/probable`, { params: monthYear ? { month_year: monthYear } : {} })
export const getMissingInBooks = (sessionId, monthYear) => api.get(`/results/${sessionId}/missing-in-books`, { params: monthYear ? { month_year: monthYear } : {} })
export const getMissingInGSTR2B = (sessionId, monthYear) => api.get(`/results/${sessionId}/missing-in-gstr2b`, { params: monthYear ? { month_year: monthYear } : {} })

export const getDashboard = (sessionId, monthYear) => api.get(`/dashboard/${sessionId}`, { params: monthYear ? { month_year: monthYear } : {} })

export const getTallyPreview = (sessionId, month, year) => api.get(`/tally/${sessionId}/preview`, { params: { ...(month ? { month } : {}), ...(year ? { year } : {}) } })
export const downloadTallyXml = (sessionId) => api.get(`/tally/${sessionId}/xml`, { responseType: 'blob' })

export const getSessions = (branch, reconMonth) => api.get('/sessions', { params: { ...(branch ? { branch } : {}), ...(reconMonth ? { recon_month: reconMonth } : {}) } })

export const getGstr2bFiles = (sessionId) => api.get(`/sessions/${sessionId}/gstr2b-files`)
export const downloadTallyXmlFiltered = (sessionId, month, year) => api.get(`/tally/${sessionId}/xml`, { responseType: 'blob', params: { ...(month ? { month } : {}), ...(year ? { year } : {}) } })
