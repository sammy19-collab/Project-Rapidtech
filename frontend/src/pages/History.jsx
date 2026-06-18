import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getSessions, getBranches } from '../api'

const STATUS_BADGE = {
  completed: 'bg-green-900 text-green-300',
  ready_to_reconcile: 'bg-blue-900 text-blue-300',
  books_uploaded: 'bg-amber-900 text-amber-300',
  processing: 'bg-slate-700 text-slate-300',
  error: 'bg-red-900 text-red-300',
}

function statusLabel(status) {
  const map = {
    completed: 'Completed',
    ready_to_reconcile: 'Ready',
    books_uploaded: 'Books Only',
    processing: 'Processing',
    error: 'Error',
  }
  return map[status] || status
}

function formatMonth(ym) {
  if (!ym) return '—'
  const [year, month] = ym.split('-')
  if (!year || !month) return ym
  const d = new Date(Number(year), Number(month) - 1, 1)
  return d.toLocaleString('en-IN', { month: 'short', year: 'numeric' })
}

export default function History() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [branches, setBranches] = useState([])
  const [filterBranch, setFilterBranch] = useState('')
  const [filterYear, setFilterYear] = useState('')

  useEffect(() => {
    getBranches().then(r => setBranches(r.data.branches)).catch(() => {})
    loadSessions()
  }, [])

  const loadSessions = async (branch, year) => {
    setLoading(true)
    try {
      const reconMonth = year ? undefined : undefined // year filter done client-side
      const res = await getSessions(branch || undefined, undefined)
      setSessions(res.data)
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  const handleFilterBranch = (val) => {
    setFilterBranch(val)
    loadSessions(val, filterYear)
  }

  const handleFilterYear = (val) => {
    setFilterYear(val)
  }

  // Extract unique years from sessions
  const years = [...new Set(sessions.map(s => s.recon_year).filter(Boolean))].sort((a, b) => b - a)

  // Apply client-side year filter
  const filtered = filterYear
    ? sessions.filter(s => s.recon_year === filterYear)
    : sessions

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Reconciliation History</h1>
        <p className="text-slate-400 text-sm mt-1">All past reconciliation sessions</p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 bg-slate-800 border border-slate-700 rounded-lg p-4">
        <div>
          <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Branch</label>
          <select
            value={filterBranch}
            onChange={e => handleFilterBranch(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-slate-200 text-sm focus:outline-none focus:border-blue-500 min-w-[120px]"
          >
            <option value="">All Branches</option>
            {branches.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Year</label>
          <select
            value={filterYear}
            onChange={e => handleFilterYear(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-slate-200 text-sm focus:outline-none focus:border-blue-500 min-w-[100px]"
          >
            <option value="">All Years</option>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        {(filterBranch || filterYear) && (
          <div className="flex items-end">
            <button
              onClick={() => { setFilterBranch(''); setFilterYear(''); loadSessions('', '') }}
              className="text-xs text-slate-400 hover:text-slate-200 underline py-1.5"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Loading sessions...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-slate-400 text-lg">No reconciliation sessions yet.</p>
          <Link to="/" className="mt-4 inline-block text-blue-400 hover:text-blue-300 text-sm underline">
            Start a new reconciliation
          </Link>
        </div>
      ) : (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Branch</th>
                <th className="text-left py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Period</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Books</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">GSTR-2B</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Reconciled</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Manual</th>
                <th className="text-center py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Status</th>
                <th className="text-right py-3 px-4 text-xs text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => {
                const reconciled = (s.result_counts?.exact || 0) + (s.result_counts?.strong || 0)
                const manual = s.result_counts?.manual || 0
                return (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/dashboard/${s.id}`)}
                    className={`border-b border-slate-700/50 hover:bg-slate-700/40 cursor-pointer transition-colors ${i % 2 === 0 ? '' : 'bg-slate-800/50'}`}
                  >
                    <td className="py-3 px-4">
                      <span className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded font-mono text-xs font-bold">
                        {s.branch || '—'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-mono text-xs">{formatMonth(s.recon_month)}</td>
                    <td className="py-3 px-4 text-right text-slate-300 font-mono">{s.books_count ?? '—'}</td>
                    <td className="py-3 px-4 text-right text-slate-300 font-mono">{s.gstr2b_count ?? '—'}</td>
                    <td className="py-3 px-4 text-right text-green-400 font-mono">{s.status === 'completed' ? reconciled : '—'}</td>
                    <td className="py-3 px-4 text-right text-red-400 font-mono">{s.status === 'completed' ? manual : '—'}</td>
                    <td className="py-3 px-4 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[s.status] || 'bg-slate-700 text-slate-300'}`}>
                        {statusLabel(s.status)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/dashboard/${s.id}`}
                          className="text-blue-400 hover:text-blue-300 text-xs underline"
                        >
                          Dashboard
                        </Link>
                        <Link
                          to={`/results/${s.id}`}
                          className="text-slate-400 hover:text-slate-200 text-xs underline"
                        >
                          Results
                        </Link>
                        {s.status === 'completed' && (
                          <Link
                            to={`/tally/${s.id}`}
                            className="text-amber-400 hover:text-amber-300 text-xs underline"
                          >
                            Tally
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
