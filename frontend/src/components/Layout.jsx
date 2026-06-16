import { Link, useParams } from 'react-router-dom'

export default function Layout({ children }) {
  const params = useParams()
  const sessionId = params.sessionId
  const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <div className="min-h-screen bg-slate-900 text-slate-200">
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <Link to="/" className="text-blue-400 font-bold text-lg tracking-tight hover:text-blue-300">
              RapidTech
            </Link>
            <span className="text-slate-400 text-sm ml-2">GST Reconciliation System</span>
          </div>
          <div className="flex items-center gap-6">
            {sessionId && (
              <nav className="flex gap-4 text-sm">
                <Link to={`/dashboard/${sessionId}`} className="text-slate-300 hover:text-blue-400 transition-colors">Dashboard</Link>
                <Link to={`/results/${sessionId}`} className="text-slate-300 hover:text-blue-400 transition-colors">Results</Link>
                <Link to={`/tally/${sessionId}`} className="text-slate-300 hover:text-blue-400 transition-colors">Tally Export</Link>
              </nav>
            )}
            <span className="text-slate-500 text-xs font-mono">{today}</span>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  )
}
