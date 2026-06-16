import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ResultsTable from '../components/ResultsTable'
import { getAvailableMonths, getReconciled, getProbable, getMissingInBooks, getMissingInGSTR2B } from '../api'

const COMMON_COLS = [
  { key: 'vendor_name', label: 'Vendor Name' },
  { key: 'gstin', label: 'GSTIN', mono: true },
  { key: 'invoice_number', label: 'Invoice No', mono: true },
  { key: 'invoice_date', label: 'Date', mono: true },
  { key: 'month_year', label: 'Month', mono: true },
  { key: 'taxable_value', label: 'Taxable (₹)', mono: true, right: true, format: v => v != null ? new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(v) : '—' },
  { key: 'total_gst', label: 'GST (₹)', mono: true, right: true, format: v => v != null ? new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(v) : '—' },
]

const TABS = [
  { id: 'reconciled', label: 'Reconciled', fetcher: getReconciled, extra: [{ key: 'match_category', label: 'Status' }, { key: 'match_score', label: 'Score' }] },
  { id: 'probable', label: 'Probable Matches', fetcher: getProbable, extra: [{ key: 'match_score', label: 'Score' }, { key: 'mismatch_reason', label: 'Mismatch Reason' }] },
  { id: 'missing-books', label: 'Missing in Books', fetcher: getMissingInBooks, extra: [] },
  { id: 'missing-gstr2b', label: 'Missing in GSTR-2B', fetcher: getMissingInGSTR2B, extra: [] },
]

export default function Results() {
  const { sessionId } = useParams()
  const [activeTab, setActiveTab] = useState('reconciled')
  const [monthFilter, setMonthFilter] = useState('')
  const [availableMonths, setAvailableMonths] = useState([])
  const [cache, setCache] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getAvailableMonths(sessionId).then(r => setAvailableMonths(r.data.months || [])).catch(() => {})
  }, [sessionId])

  const cacheKey = `${activeTab}__${monthFilter}`
  const tab = TABS.find(t => t.id === activeTab)

  useEffect(() => {
    if (cache[cacheKey]) return
    setLoading(true)
    tab.fetcher(sessionId, monthFilter || undefined)
      .then(r => setCache(c => ({ ...c, [cacheKey]: r.data })))
      .finally(() => setLoading(false))
  }, [activeTab, monthFilter, sessionId])

  const data = cache[cacheKey] || []

  const handleMonthChange = (m) => {
    setMonthFilter(m)
    // pre-clear cache for this combination so it refetches
    const key = `${activeTab}__${m}`
    setCache(c => { const n = { ...c }; delete n[key]; return n })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-bold text-slate-100">Reconciliation Results</h1>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Month:</label>
          <select
            value={monthFilter}
            onChange={e => handleMonthChange(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Months</option>
            {availableMonths.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          {monthFilter && (
            <button onClick={() => handleMonthChange('')} className="text-xs text-slate-400 hover:text-slate-200 underline">Clear</button>
          )}
          <span className="text-slate-500 text-xs font-mono ml-2">Session #{sessionId}</span>
        </div>
      </div>

      <div className="flex border-b border-slate-700 gap-1 overflow-x-auto">
        {TABS.map(t => {
          const k = `${t.id}__${monthFilter}`
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${activeTab === t.id ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-slate-200'}`}
            >
              {t.label}
              {cache[k] && <span className="ml-2 text-xs text-slate-500">({cache[k].length})</span>}
            </button>
          )
        })}
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <ResultsTable
          data={data}
          columns={[...COMMON_COLS, ...(tab?.extra || [])]}
          loading={loading}
        />
      </div>
    </div>
  )
}
