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

  useEffect(() => {
    getDashboard(sessionId).then(r => setData(r.data)).finally(() => setLoading(false))
  }, [sessionId])

  if (loading) return <div className="text-center py-20 text-slate-400">Loading dashboard...</div>
  if (!data) return <div className="text-center py-20 text-red-400">Failed to load dashboard</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Reconciliation Dashboard</h1>
        <span className="text-slate-500 text-xs font-mono">Session #{sessionId}</span>
      </div>

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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Trend */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Monthly Reconciliation Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.monthly_trend} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
              <Bar dataKey="reconciled" fill="#22c55e" name="Reconciled" radius={[2,2,0,0]} />
              <Bar dataKey="mismatched" fill="#ef4444" name="Mismatched" radius={[2,2,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Mismatch Reasons Pie */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Mismatch Reasons</h3>
          {data.mismatch_reasons.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No mismatches</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={data.mismatch_reasons} dataKey="count" nameKey="reason" cx="50%" cy="50%" outerRadius={75} label={false}>
                  {data.mismatch_reasons.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} formatter={(v) => v.length > 30 ? v.slice(0,30)+'...' : v} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top Vendors */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Vendors by Amount</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.top_vendors} layout="vertical" margin={{ left: 140, right: 20 }}>
            <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${fmt(v)}`} />
            <YAxis type="category" dataKey="vendor" tick={{ fill: '#94a3b8', fontSize: 11 }} width={135} />
            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} formatter={v => [`₹${fmt(v)}`, 'Amount']} />
            <Bar dataKey="amount" fill="#3b82f6" radius={[0,2,2,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Vendor Mismatch Table */}
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
            {data.vendor_mismatch_percentage.slice(0, 15).map((v, i) => (
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
