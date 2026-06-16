import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, ResponsiveContainer, Legend } from 'recharts'
import StatCard from '../components/StatCard'
import { getDashboard } from '../api'

const PIE_COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6']
const fmt = (n) => new Intl.NumberFormat('en-IN').format(Math.round(n || 0))

export default function Dashboard() {
  const { sessionId } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [monthFilter, setMonthFilter] = useState('')

  const fetchDashboard = (mf) => {
    setLoading(true)
    getDashboard(sessionId, mf || undefined)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchDashboard('') }, [sessionId])

  const handleMonthChange = (m) => {
    setMonthFilter(m)
    fetchDashboard(m)
  }

  if (loading) return <div className="text-center py-20 text-slate-400">Loading dashboard...</div>
  if (!data) return <div className="text-center py-20 text-red-400">No data found. Run reconciliation first.</div>

  return (
    <div className="space-y-8">

      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-100">Reconciliation Dashboard</h1>
          {data.branch && (
            <span className="bg-blue-900 text-blue-300 text-sm px-3 py-1 rounded font-mono font-bold">
              {data.branch}
            </span>
          )}
          {data.recon_month && (
            <span className="bg-slate-700 text-slate-300 text-xs px-2 py-1 rounded">
              {data.recon_month}
            </span>
          )}
        </div>

        {/* Month filter */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Filter by month:</label>
          <select
            value={monthFilter}
            onChange={e => handleMonthChange(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Months</option>
            {(data.available_months || []).map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          {monthFilter && (
            <button onClick={() => handleMonthChange('')} className="text-xs text-slate-400 hover:text-slate-200 underline">Clear</button>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard title="Total Invoices" value={data.total_invoices} color="slate" />
        <StatCard title="Reconciled" value={data.total_reconciled} color="green" />
        <StatCard title="Probable" value={data.total_probable} color="amber" />
        <StatCard title="Manual Review" value={data.total_manual_review} color="red" />
        <StatCard title="Recon %" value={`${data.reconciliation_percentage}%`} color="blue" />
        <StatCard title="Total ITC (₹)" value={`₹${fmt(data.total_itc_amount)}`} color="green" />
        <StatCard title="ITC at Risk (₹)" value={`₹${fmt(data.potential_itc_loss)}`} color="red" />
        <StatCard title="Missing in Books" value={data.total_missing_in_books} color="slate" />
      </div>

      {/* Month-wise breakdown table */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Month-wise Breakdown</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase">
                <th className="text-left py-2 px-3">Month</th>
                <th className="text-right py-2 px-3">Reconciled</th>
                <th className="text-right py-2 px-3">Probable</th>
                <th className="text-right py-2 px-3">Manual</th>
                <th className="text-right py-2 px-3">Missing</th>
                <th className="text-right py-2 px-3">ITC (₹)</th>
              </tr>
            </thead>
            <tbody>
              {(data.monthly_trend || []).map((row, i) => (
                <tr key={i} className={`border-b border-slate-800 hover:bg-slate-700/40 cursor-pointer ${monthFilter === row.month ? 'bg-blue-950/40' : ''}`}
                  onClick={() => handleMonthChange(monthFilter === row.month ? '' : row.month)}>
                  <td className="py-2 px-3 font-mono text-slate-300">{row.month}</td>
                  <td className="py-2 px-3 text-right font-mono text-green-400">{row.reconciled}</td>
                  <td className="py-2 px-3 text-right font-mono text-amber-400">{row.probable}</td>
                  <td className="py-2 px-3 text-right font-mono text-red-400">{row.manual}</td>
                  <td className="py-2 px-3 text-right font-mono text-purple-400">{row.missing_books}</td>
                  <td className="py-2 px-3 text-right font-mono text-slate-300">₹{fmt(row.itc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-2">Click a row to filter all stats by that month</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Chart */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Monthly Reconciliation Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.monthly_trend} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
              <Bar dataKey="reconciled" fill="#22c55e" name="Reconciled" radius={[2,2,0,0]} />
              <Bar dataKey="probable" fill="#f59e0b" name="Probable" radius={[2,2,0,0]} />
              <Bar dataKey="manual" fill="#ef4444" name="Manual" radius={[2,2,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Mismatch Reasons Pie */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Mismatch Reasons</h3>
          {!data.mismatch_reasons?.length ? (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No mismatches</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={data.mismatch_reasons} dataKey="count" nameKey="reason" cx="50%" cy="50%" outerRadius={75}>
                  {data.mismatch_reasons.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} formatter={v => v.length > 28 ? v.slice(0,28)+'…' : v} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top Vendors */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Vendors by Taxable Amount</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data.top_vendors} layout="vertical" margin={{ left: 150, right: 30 }}>
            <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${fmt(v)}`} />
            <YAxis type="category" dataKey="vendor" tick={{ fill: '#94a3b8', fontSize: 11 }} width={145} />
            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} formatter={v => [`₹${fmt(v)}`, 'Amount']} />
            <Bar dataKey="amount" fill="#3b82f6" radius={[0,2,2,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Vendor Mismatch */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Vendor-wise Match Rate</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase">
              <th className="text-left py-2 px-3">Vendor</th>
              <th className="text-right py-2 px-3">Total</th>
              <th className="text-right py-2 px-3">Matched</th>
              <th className="text-right py-2 px-3">Match %</th>
            </tr>
          </thead>
          <tbody>
            {data.vendor_mismatch_percentage.slice(0,15).map((v, i) => (
              <tr key={i} className="border-b border-slate-800 hover:bg-slate-700/40">
                <td className="py-2 px-3 text-slate-300">{v.vendor}</td>
                <td className="py-2 px-3 text-right font-mono text-slate-400">{v.total}</td>
                <td className="py-2 px-3 text-right font-mono text-green-400">{v.matched}</td>
                <td className="py-2 px-3 text-right font-mono">
                  <span className={v.match_pct >= 80 ? 'text-green-400' : v.match_pct >= 50 ? 'text-amber-400' : 'text-red-400'}>
                    {v.match_pct}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
