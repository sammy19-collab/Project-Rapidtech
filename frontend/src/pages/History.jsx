import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSessions } from '../api'

const BRANCHES = ['AP', 'BLR', 'BBSR', 'HYD', 'MUM', 'DEL', 'CHN', 'KOL', 'PUN', 'Other']

const STATUS_BADGE = {
  completed:           'bg-green-900 text-green-300',
  books_uploaded:      'bg-blue-900 text-blue-300',
  ready_to_reconcile:  'bg-amber-900 text-amber-300',
  processing:          'bg-slate-700 text-slate-300',
  error:               'bg-red-900 text-red-300',
}

const STATUS_LABEL = {
  completed: 'Completed', books_uploaded: 'Books Uploaded',
  ready_to_reconcile: 'Ready', processing: 'Processing', error: 'Error',
}

export default function History() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterBranch, setFilterBranch] = useState('')
  const [filterYear, setFilterYear] = useState('')

  useEffect(() => {
    setLoading(true)
    getSessions(filterBranch || undefined)
      .then(r => setSessions(r.data))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [filterBranch])

  const years = [...new Set(sessions.map(s => s.recon_year).filter(Boolean))].sort().reverse()
  const filtered = filterYear ? sessions.filter(s => s.recon_year === filterYear) : sessions

  const cnt = (s, cat) => {
    if (!s.result_counts) return '—'
    if (cat === 'reconciled') return (s.result_counts['Exact Match'] || 0) + (s.result_counts['Strong Match'] || 0)
    if (cat === 'manual') return s.result_counts['Manual Review'] || 0
    if (cat === 'missing') return s.result_counts['Missing in Books'] || 0
    return 0
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Reconciliation History</h1>
          <p className="text-slate-400 text-sm mt-1">All past reconciliation sessions</p>
        </div>
        <button onClick={() => navigate('/')}
          className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-4 py-2 rounded transition-colors">
          + New Reconciliation
        </button>
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <select value={filterBranch} onChange={e => setFilterBranch(e.target.value)}
          className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500">
          <option value="">All Branches</option>
          {BRANCHES.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <select value={filterYear} onChange={e => setFilterYear(e.target.value)}
          className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500">
          <option value="">All Years</option>
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        {(filterBranch || filterYear) && (
          <button onClick={() => { setFilterBranch(''); setFilterYear('') }}
            className="text-xs text-slate-400 hover:text-slate-200 underline">Clear</button>
        )}
        <span className="ml-auto text-xs text-slate-500">{filtered.length} session{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-slate-500 text-lg mb-2">No reconciliation sessions yet</div>
          <button onClick={() => navigate('/')} className="text-blue-400 hover:text-blue-300 text-sm underline">
            Start your first reconciliation
          </button>
        </div>
      ) : (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase">
                <th className="text-left py-3 px-4">Branch</th>
                <th className="text-left py-3 px-4">Period</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-right py-3 px-4">Books</th>
                <th className="text-right py-3 px-4">GSTR-2B</th>
                <th className="text-right py-3 px-4">Reconciled</th>
                <th className="text-right py-3 px-4">Manual</th>
                <th className="text-right py-3 px-4">Missing</th>
                <th className="text-center py-3 px-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id}
                  onClick={() => s.status === 'completed' && navigate(`/dashboard/${s.id}`)}
                  className={`border-b border-slate-700/50 hover:bg-slate-700/40 transition-colors ${s.status === 'completed' ? 'cursor-pointer' : ''}`}>
                  <td className="py-3 px-4">
                    <span className="bg-blue-900 text-blue-300 text-xs px-2 py-0.5 rounded font-mono font-bold">{s.branch || '—'}</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-300">{s.recon_month || '—'}</td>
                  <td className="py-3 px-4">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_BADGE[s.status] || 'bg-slate-700 text-slate-300'}`}>
                      {STATUS_LABEL[s.status] || s.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-slate-300">{s.books_count ?? '—'}</td>
                  <td className="py-3 px-4 text-right font-mono text-slate-300">
                    {s.gstr2b_file_count != null ? `${s.gstr2b_file_count} file${s.gstr2b_file_count !== 1 ? 's' : ''}` : '—'}
                    {s.gstr2b_count != null ? <span className="text-slate-500 text-xs ml-1">({s.gstr2b_count} rec)</span> : null}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-green-400">{cnt(s, 'reconciled')}</td>
                  <td className="py-3 px-4 text-right font-mono text-red-400">{cnt(s, 'manual')}</td>
                  <td className="py-3 px-4 text-right font-mono text-purple-400">{cnt(s, 'missing')}</td>
                  <td className="py-3 px-4" onClick={e => e.stopPropagation()}>
                    {s.status === 'completed' ? (
                      <div className="flex justify-center gap-1.5">
                        <button onClick={() => navigate(`/dashboard/${s.id}`)}
                          className="text-xs bg-blue-900 hover:bg-blue-800 text-blue-300 px-2 py-1 rounded">Dashboard</button>
                        <button onClick={() => navigate(`/results/${s.id}`)}
                          className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded">Results</button>
                        <button onClick={() => navigate(`/tally/${s.id}`)}
                          className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded">Tally</button>
                      </div>
                    ) : <span className="text-slate-500 text-xs text-center block">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
