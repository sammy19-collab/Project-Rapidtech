const colorMap = {
  green: 'border-green-500 text-green-400',
  blue: 'border-blue-500 text-blue-400',
  amber: 'border-amber-500 text-amber-400',
  red: 'border-red-500 text-red-400',
  slate: 'border-slate-500 text-slate-400',
}

export default function StatCard({ title, value, subtitle, color = 'slate' }) {
  const cls = colorMap[color] || colorMap.slate
  return (
    <div className={`bg-slate-800 border border-slate-700 border-t-2 ${cls.split(' ')[0]} rounded p-4`}>
      <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">{title}</div>
      <div className={`text-2xl font-mono font-bold ${cls.split(' ')[1]}`}>{value}</div>
      {subtitle && <div className="text-xs text-slate-500 mt-1">{subtitle}</div>}
    </div>
  )
}
