import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSessions } from '../api'

const BRANCHES = ['AP', 'BLR', 'BBSR', 'HYD', 'MUM', 'DEL', 'CHN', 'KOL', 'PUN', 'Other']

const STATUS_BADGE = {
  completed: 'bg-green-900 text-green-300',
  ready_to_reconcile: 'bg-amber-900 text-amber-300',
  processing: 'bg-amber-900 text-amber-300',
  books_uploaded: 'bg-blue-900 text-blue-300',
  error: 'bg-red-900 text-red-300',
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'bg-slate-700 text-slate-300'
  const label = status?.replace(/_/g, ' ') || 'unknown'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

function formatPeriod(s) {
  if (!s.recon_month) return s.recon_year || '—'
  const [year, month] = s.recon_month.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, 1)
  return date.toLocaleString('en-IN', { month: 'short', year: 'numeric' })
}

export default function History() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterBranch, setFilterBranch] = useState('')
  const [filterYear, setFilterYear] = useState('')

  useEffect(() => {
    setLoading(true)
    getSessions(filterBranch || undefined, undefined)
      .then(r => setSessions(r.data))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [filterBranch])

  const years = [...new Set(sessions.map(s => s.recon_year).filter(Boolean))].sort().reverse()
  const filtered = filterYear ? sessions.filter(s => s.recon_year === filterYear) : sessions

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Reconciliation History</h1>
          <p className="text-slate-400 text-sm mt-1">All past GST reconciliation sessions</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-4 py-2 rounded text-sm transition-colors"
        >
          + New Reconciliation
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div>
          <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Branch</label>
          <select
            value={filterBranch}
            onChange={e => setFilterBranch(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-slate-200 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="">All Branches</option>
            {BRANCHES.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Year</label>
          <select
            value={filterYear}
            onChange={e => setFilterYear(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-slate-200 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="">All Years</option>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400">
          <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mr-3" />
          Loading sessions...
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-12 text-center">
          <div className="text-slate-500 text-4xl mb-3">📂</div>
          <div className="text-slate-400">No reconciliation sessions found.</div>
          <button onClick={() => navigate('/')} className="mt-4 text-blue-400 hover:text-blue-300 text-sm underline">
            Start a new reconciliation
          </button>
        </div>
      ) : (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800">
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Branch</th>
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Period</th>
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Status</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Books</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">GSTR-2B Files</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Reconciled</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Manual</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Created</th>
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => {
                const reconciled = (s.result_counts?.['Exact Match'] || 0) + (s.result_counts?.['Strong Match'] || 0)
                const manual = s.result_counts?.['Manual Review'] || 0
                const createdAt = s.created_at ? new Date(s.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
                return (
                  <tr key={s.id} className={`border-b border-slate-700/50 hover:bg-slate-700/40 transition-colors ${i % 2 === 0 ? '' : 'bg-slate-800/50'}`}>
                    <td className="py-3 px-4">
                      <span className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded font-mono font-bold text-xs">{s.branch || '—'}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-200">{formatPeriod(s)}</td>
                    <td className="py-3 px-4"><StatusBadge status={s.status} /></td>
                    <td className="py-3 px-4 text-right text-slate-300 font-mono">{s.books_count ?? '—'}</td>
                    <td className="py-3 px-4 text-right text-slate-300 font-mono">{s.gstr2b_file_count ?? '—'}</td>
                    <td className="py-3 px-4 text-right">
                      {s.status === 'completed' ? (
                        <span className="text-green-400 font-mono">{reconciled}</span>
                      ) : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {s.status === 'completed' ? (
                        <span className="text-red-400 font-mono">{manual}</span>
                      ) : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-400 text-xs">{createdAt}</td>
                    <td className="py-3 px-4">
                      {s.status === 'completed' ? (
                        <div className="flex gap-2">
                          <button onClick={() => navigate(`/dashboard/${s.id}`)}
                            className="text-xs bg-blue-800 hover:bg-blue-700 text-blue-200 px-2 py-1 rounded transition-colors">
                            Dashboard
                          </button>
                          <button onClick={() => navigate(`/results/${s.id}`)}
                            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2 py-1 rounded transition-colors">
                            Results
                          </button>
                          <button onClick={() => navigate(`/tally/${s.id}`)}
                            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2 py-1 rounded transition-colors">
                            Tally
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="px-4 py-3 border-t border-slate-700 text-xs text-slate-500">
            Showing {filtered.length} session{filtered.length !== 1 ? 's' : ''}
          </div>
        </div>
      )}
    </div>
  )
}
