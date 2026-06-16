import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ResultsTable from '../components/ResultsTable'
import { getReconciled, getProbable, getMissingInBooks, getMissingInGSTR2B } from '../api'

const COMMON_COLS = [
  { key: 'vendor_name', label: 'Vendor Name' },
  { key: 'gstin', label: 'GSTIN', mono: true },
  { key: 'invoice_number', label: 'Invoice No', mono: true },
  { key: 'invoice_date', label: 'Date', mono: true },
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
  const [cache, setCache] = useState({})
  const [loading, setLoading] = useState(false)

  const tab = TABS.find(t => t.id === activeTab)

  useEffect(() => {
    if (cache[activeTab]) return
    setLoading(true)
    tab.fetcher(sessionId)
      .then(r => setCache(c => ({ ...c, [activeTab]: r.data })))
      .finally(() => setLoading(false))
  }, [activeTab, sessionId])

  const data = cache[activeTab] || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Reconciliation Results</h1>
        <span className="text-slate-500 text-xs font-mono">Session #{sessionId}</span>
      </div>

      <div className="flex border-b border-slate-700 gap-1">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === t.id ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-slate-200'}`}
          >
            {t.label}
            {cache[t.id] && <span className="ml-2 text-xs text-slate-500">({cache[t.id].length})</span>}
          </button>
        ))}
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
