import { useState } from 'react'

const PAGE_SIZE = 25

const categoryColor = {
  'Exact Match': 'bg-green-900 text-green-300',
  'Strong Match': 'bg-blue-900 text-blue-300',
  'Probable Match': 'bg-amber-900 text-amber-300',
  'Manual Review': 'bg-red-900 text-red-300',
  'Missing in Books': 'bg-purple-900 text-purple-300',
}

export default function ResultsTable({ data = [], columns = [], loading = false }) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const filtered = data.filter(row =>
    columns.some(col => String(row[col.key] || '').toLowerCase().includes(search.toLowerCase()))
  )
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const rows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const downloadCsv = () => {
    const header = columns.map(c => c.label).join(',')
    const lines = filtered.map(row => columns.map(c => `"${row[c.key] ?? ''}"`).join(','))
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'results.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="text-center py-12 text-slate-400">Loading...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-3 gap-3">
        <input
          type="text"
          placeholder="Search..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1) }}
          className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 w-64 focus:outline-none focus:border-blue-500"
        />
        <button onClick={downloadCsv} className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded text-slate-300 transition-colors">
          Download CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              {columns.map(col => (
                <th key={col.key} className="text-left py-2 px-3 text-xs text-slate-400 uppercase tracking-wider font-normal">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={columns.length} className="text-center py-8 text-slate-500">No records found</td></tr>
            ) : rows.map((row, i) => (
              <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/50">
                {columns.map(col => (
                  <td key={col.key} className={`py-2 px-3 ${col.mono ? 'font-mono' : ''} ${col.right ? 'text-right' : ''}`}>
                    {col.key === 'match_category' ? (
                      <span className={`text-xs px-2 py-0.5 rounded ${categoryColor[row[col.key]] || ''}`}>{row[col.key]}</span>
                    ) : col.key === 'match_score' ? (
                      <span className="font-mono text-blue-300">{row[col.key]}/5</span>
                    ) : col.format ? col.format(row[col.key]) : (row[col.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 text-xs text-slate-400">
          <span>{filtered.length} records</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-2 py-1 bg-slate-700 rounded disabled:opacity-40">Prev</button>
            <span>Page {page} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-2 py-1 bg-slate-700 rounded disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  )
}
