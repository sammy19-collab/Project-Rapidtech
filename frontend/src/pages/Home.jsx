import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import StepIndicator from '../components/StepIndicator'
import UploadZone from '../components/UploadZone'
import { getBranches, uploadBooks, uploadGSTR2B, runReconciliation, getGstr2bFiles } from '../api'

const STEPS = ['Select Branch & Month', 'Upload Books', 'Upload GSTR-2B', 'Reconcile']

const DEFAULT_BRANCHES = ['AP', 'BLR', 'BBSR', 'HYD', 'MUM', 'DEL', 'CHN', 'KOL', 'PUN', 'Other']

// Generate last 24 months as "YYYY-MM"
function getMonthOptions() {
  const opts = []
  const now = new Date()
  for (let i = 0; i < 24; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleString('en-IN', { month: 'long', year: 'numeric' })
    opts.push({ val, label })
  }
  return opts
}

export default function Home() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [branches, setBranches] = useState(DEFAULT_BRANCHES)
  const [branch, setBranch] = useState('')
  const [reconMonth, setReconMonth] = useState(getMonthOptions()[1].val)
  const [sessionId, setSessionId] = useState(null)
  const [booksStatus, setBooksStatus] = useState('idle')
  const [booksInfo, setBooksInfo] = useState(null)
  const [gstr2bFiles, setGstr2bFiles] = useState([])
  const [totalGstr2bRecords, setTotalGstr2bRecords] = useState(0)
  const [uploadingGstr, setUploadingGstr] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [summary, setSummary] = useState(null)

  const monthOptions = getMonthOptions()

  useEffect(() => {
    getBranches().then(r => setBranches(r.data.branches)).catch(() => setBranches(DEFAULT_BRANCHES))
  }, [])

  const refreshGstr2bFiles = async (sid) => {
    try {
      const res = await getGstr2bFiles(sid || sessionId)
      setGstr2bFiles(res.data.files)
      setTotalGstr2bRecords(res.data.total_records)
    } catch {
      // ignore
    }
  }

  const handleConfirmBranch = () => {
    if (!branch) { toast.error('Please select a branch'); return }
    setStep(1)
  }

  const handleBooksUpload = async (file) => {
    setBooksStatus('loading')
    try {
      const res = await uploadBooks(file, branch, reconMonth)
      setSessionId(res.data.session_id)
      setBooksInfo(res.data)
      setBooksStatus('success')
      setStep(2)
      toast.success(`Books loaded: ${res.data.books_count} records`)
    } catch (e) {
      setBooksStatus('error')
      toast.error(e.response?.data?.detail || 'Failed to upload Books file')
    }
  }

  const handleGstrUpload = async (file) => {
    setUploadingGstr(true)
    try {
      const res = await uploadGSTR2B(sessionId, file)
      toast.success(`GSTR-2B loaded: ${res.data.gstr2b_count} records`)
      await refreshGstr2bFiles(sessionId)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to upload GSTR-2B file')
    } finally {
      setUploadingGstr(false)
    }
  }

  const handleReconcile = async () => {
    setReconciling(true)
    setStep(3)
    try {
      const res = await runReconciliation(sessionId)
      setSummary(res.data.summary)
      toast.success('Reconciliation complete!')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reconciliation failed')
      setStep(2)
    } finally {
      setReconciling(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-100">GST Reconciliation</h1>
        <p className="text-slate-400 text-sm mt-1">Select branch and period, then upload Books & GSTR-2B files</p>
      </div>

      <StepIndicator steps={STEPS} current={step} />

      <div className="space-y-4">

        {/* Step 0: Branch & Month */}
        <div className={`bg-slate-800 border rounded-lg p-6 ${step > 0 ? 'border-green-800' : 'border-slate-700'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 1: Select Branch & Period</h2>
            {step > 0 && (
              <span className="text-green-400 text-sm font-mono">
                {branch} — {monthOptions.find(m => m.val === reconMonth)?.label}
              </span>
            )}
          </div>
          {step === 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-slate-400 uppercase tracking-wider block mb-2">Branch</label>
                  <select
                    value={branch}
                    onChange={e => setBranch(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500"
                  >
                    <option value="">— Select Branch —</option>
                    {branches.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-400 uppercase tracking-wider block mb-2">Reconciliation Month</label>
                  <select
                    value={reconMonth}
                    onChange={e => setReconMonth(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500"
                  >
                    {monthOptions.map(m => <option key={m.val} value={m.val}>{m.label}</option>)}
                  </select>
                </div>
              </div>
              <button
                onClick={handleConfirmBranch}
                disabled={!branch}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded transition-colors"
              >
                Continue
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-sm">
              <span className="bg-blue-900 text-blue-300 px-3 py-1 rounded font-mono font-bold">{branch}</span>
              <span className="text-slate-400">{monthOptions.find(m => m.val === reconMonth)?.label}</span>
              <button onClick={() => { setStep(0); setBooksStatus('idle'); setSessionId(null); setBooksInfo(null); setGstr2bFiles([]); setTotalGstr2bRecords(0); setSummary(null) }}
                className="ml-auto text-xs text-slate-500 hover:text-slate-300 underline">
                Change
              </button>
            </div>
          )}
        </div>

        {/* Step 1: Books */}
        <div className={`bg-slate-800 border border-slate-700 rounded-lg p-6 transition-opacity ${step < 1 ? 'opacity-40 pointer-events-none' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 2: Upload Books Excel</h2>
            {booksInfo && <span className="text-green-400 text-sm font-mono">{booksInfo.books_count} records</span>}
          </div>
          <UploadZone
            onUpload={handleBooksUpload}
            label={booksStatus === 'success' ? `✓ ${booksInfo?.filename}` : 'Drop RapidTech Books Excel here'}
            description="Upload RapidTech Books Excel file (.xlsx / .xls)"
            status={booksStatus}
            disabled={step !== 1}
          />
        </div>

        {/* Step 2: GSTR-2B (multi-file) */}
        <div className={`bg-slate-800 border border-slate-700 rounded-lg p-6 transition-opacity ${step < 2 ? 'opacity-40 pointer-events-none' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 3: Upload GSTR-2B Excel</h2>
            {totalGstr2bRecords > 0 && (
              <span className="text-green-400 text-sm font-mono">{totalGstr2bRecords} total records</span>
            )}
          </div>

          {/* Already uploaded files list */}
          {gstr2bFiles.length > 0 && (
            <div className="mb-4 space-y-2">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Uploaded Files</p>
              {gstr2bFiles.map((f) => (
                <div key={f.id} className="flex items-center justify-between bg-slate-700/50 border border-slate-600 rounded px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-slate-200 font-mono text-xs">{f.filename}</span>
                  </div>
                  <span className="text-slate-400 text-xs font-mono">{f.record_count} records</span>
                </div>
              ))}
              <div className="flex items-center justify-between pt-1 border-t border-slate-700 text-xs text-slate-400">
                <span>{gstr2bFiles.length} file{gstr2bFiles.length !== 1 ? 's' : ''} uploaded</span>
                <span className="font-mono font-semibold text-green-400">{totalGstr2bRecords} total records</span>
              </div>
            </div>
          )}

          {/* Upload zone — always shown when step 2 is active */}
          <div className="relative">
            {uploadingGstr && (
              <div className="absolute inset-0 bg-slate-800/80 flex items-center justify-center rounded z-10">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-slate-300 text-xs">Uploading...</span>
                </div>
              </div>
            )}
            <UploadZone
              onUpload={handleGstrUpload}
              label={gstr2bFiles.length > 0 ? `Upload Another GSTR-2B File` : `Drop ${branch} GSTR-2B Excel here`}
              description="Upload GSTR-2B Excel downloaded from GST portal (.xlsx / .xls)"
              status={uploadingGstr ? 'loading' : 'idle'}
              disabled={step !== 2 || uploadingGstr}
            />
          </div>

          {/* Run Reconciliation button — shown as soon as at least 1 file uploaded */}
          {gstr2bFiles.length > 0 && (
            <button
              onClick={handleReconcile}
              disabled={reconciling || uploadingGstr}
              className="mt-4 w-full bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded transition-colors"
            >
              Run Reconciliation for {branch} — {monthOptions.find(m => m.val === reconMonth)?.label}
            </button>
          )}
        </div>

        {/* Step 3: Result */}
        {step === 3 && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="font-semibold text-slate-200 mb-4">Step 4: Reconciliation Results</h2>
            {reconciling ? (
              <div className="flex flex-col items-center gap-3 py-6">
                <div className="w-10 h-10 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-slate-400 text-sm">
                  Comparing {booksInfo?.books_count} books entries against {totalGstr2bRecords} GSTR-2B entries...
                </span>
              </div>
            ) : summary ? (
              <div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
                  {[
                    { label: 'Total Books', value: summary.total_books, color: 'text-slate-300' },
                    { label: 'Reconciled', value: summary.exact_match + (summary.strong_match || 0), color: 'text-green-400' },
                    { label: 'Probable', value: summary.probable_match, color: 'text-amber-400' },
                    { label: 'Manual Review', value: summary.manual_review, color: 'text-red-400' },
                    { label: 'Missing in Books', value: summary.missing_in_books, color: 'text-purple-400' },
                    { label: 'GSTR-2B Total', value: summary.total_gstr2b, color: 'text-slate-300' },
                  ].map(item => (
                    <div key={item.label} className="bg-slate-700 rounded p-3 text-center">
                      <div className={`text-2xl font-mono font-bold ${item.color}`}>{item.value}</div>
                      <div className="text-xs text-slate-400 mt-1">{item.label}</div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-3">
                  <button onClick={() => navigate(`/dashboard/${sessionId}`)}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded transition-colors text-sm">
                    View Dashboard
                  </button>
                  <button onClick={() => navigate(`/results/${sessionId}`)}
                    className="flex-1 bg-slate-600 hover:bg-slate-500 text-white font-semibold py-2 rounded transition-colors text-sm">
                    View Results
                  </button>
                  <button onClick={() => navigate(`/tally/${sessionId}`)}
                    className="flex-1 bg-slate-600 hover:bg-slate-500 text-white font-semibold py-2 rounded transition-colors text-sm">
                    Tally Export
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
