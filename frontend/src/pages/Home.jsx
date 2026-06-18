import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import StepIndicator from '../components/StepIndicator'
import UploadZone from '../components/UploadZone'
import { uploadBooks, uploadGSTR2B, runReconciliation, getGstr2bFiles } from '../api'

const STEPS = ['Select Branch', 'Upload Books', 'Upload GSTR-2B', 'Reconcile']
const BRANCHES = ['AP', 'BLR', 'BBSR', 'HYD', 'MUM', 'DEL', 'CHN', 'KOL', 'PUN', 'Other']

export default function Home() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [branch, setBranch] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [booksStatus, setBooksStatus] = useState('idle')
  const [booksInfo, setBooksInfo] = useState(null)
  const [gstrUploading, setGstrUploading] = useState(false)
  const [gstrQueue, setGstrQueue] = useState([])   // files being uploaded
  const [gstrFiles, setGstrFiles] = useState([])
  const [gstrTotal, setGstrTotal] = useState(0)
  const [reconciling, setReconciling] = useState(false)
  const [summary, setSummary] = useState(null)

  const handleBooksUpload = async (file) => {
    setBooksStatus('loading')
    try {
      const res = await uploadBooks(file, branch)
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

  // Called once per file — files are uploaded sequentially
  const handleGstrUpload = async (file) => {
    setGstrUploading(true)
    setGstrQueue(q => [...q, file.name])
    try {
      const res = await uploadGSTR2B(sessionId, file)
      const filesRes = await getGstr2bFiles(sessionId)
      setGstrFiles(filesRes.data.files)
      setGstrTotal(filesRes.data.total_records)
      const period = res.data.detected_month ? ` (${res.data.detected_month})` : ''
      toast.success(`Loaded: ${file.name}${period}`)
    } catch (e) {
      toast.error(`${file.name}: ${e.response?.data?.detail || 'Upload failed'}`)
    } finally {
      setGstrQueue(q => q.filter(n => n !== file.name))
      setGstrUploading(false)
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
      setReconciling(false)
    } finally {
      setReconciling(false)
    }
  }

  const handleReset = () => {
    setStep(0)
    setBranch('')
    setSessionId(null)
    setBooksStatus('idle')
    setBooksInfo(null)
    setGstrFiles([])
    setGstrTotal(0)
    setGstrQueue([])
    setSummary(null)
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-100">GST Reconciliation</h1>
        <p className="text-slate-400 text-sm mt-1">Select branch, upload Books &amp; GSTR-2B files, then reconcile</p>
      </div>

      <StepIndicator steps={STEPS} current={step} />

      <div className="space-y-4">

        {/* Step 0: Branch selection */}
        <div className={`bg-slate-800 border rounded-lg p-6 ${step > 0 ? 'border-green-800' : 'border-slate-700'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 1: Select Branch</h2>
            {step > 0 && (
              <span className="bg-blue-900 text-blue-300 px-3 py-0.5 rounded font-mono font-bold text-sm">{branch}</span>
            )}
          </div>
          {step === 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-5 gap-2">
                {BRANCHES.map(b => (
                  <button
                    key={b}
                    onClick={() => setBranch(b)}
                    className={`py-2 rounded font-mono font-semibold text-sm transition-colors ${
                      branch === b
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {b}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setStep(1)}
                disabled={!branch}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded transition-colors"
              >
                Continue
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-green-400">✓</span>
              <span className="text-slate-300">Branch selected</span>
              <button onClick={handleReset} className="ml-auto text-xs text-slate-500 hover:text-slate-300 underline">
                Start over
              </button>
            </div>
          )}
        </div>

        {/* Step 1: Books */}
        <div className={`bg-slate-800 border rounded-lg p-6 transition-opacity ${step < 1 ? 'opacity-40 pointer-events-none' : ''} ${step > 1 ? 'border-green-800' : 'border-slate-700'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 2: Upload Books Excel</h2>
            {booksInfo && <span className="text-green-400 text-sm font-mono">{booksInfo.books_count} records</span>}
          </div>
          {step === 1 ? (
            <UploadZone
              onUpload={handleBooksUpload}
              label="Drop RapidTech Books Excel here"
              description="Upload the full RapidTech Books Excel (.xlsx / .xls)"
              status={booksStatus}
            />
          ) : step > 1 ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-green-400">✓</span>
              <span className="text-slate-200 font-mono truncate flex-1">{booksInfo?.filename}</span>
              <span className="text-green-400 font-mono text-xs">{booksInfo?.books_count} records</span>
            </div>
          ) : null}
        </div>

        {/* Step 2: GSTR-2B multi-file */}
        <div className={`bg-slate-800 border border-slate-700 rounded-lg p-6 transition-opacity ${step < 2 ? 'opacity-40 pointer-events-none' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 3: Upload GSTR-2B Files</h2>
            {gstrFiles.length > 0 && (
              <span className="text-green-400 text-sm font-mono">
                {gstrTotal} records · {gstrFiles.length} file{gstrFiles.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {gstrFiles.length > 0 && (
            <div className="mb-4 space-y-1.5">
              {gstrFiles.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm bg-slate-700/40 rounded px-3 py-2">
                  <span className="text-green-400">✓</span>
                  <span className="text-slate-200 font-mono flex-1 truncate">{f.filename}</span>
                  <span className="text-slate-400 text-xs font-mono">{f.record_count} records</span>
                </div>
              ))}
            </div>
          )}

          {gstrQueue.length > 0 && (
            <div className="mb-3 space-y-1">
              {gstrQueue.map(name => (
                <div key={name} className="flex items-center gap-2 text-sm bg-blue-900/30 rounded px-3 py-2">
                  <div className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-blue-300 font-mono text-xs truncate">{name}</span>
                </div>
              ))}
            </div>
          )}

          <UploadZone
            onUpload={handleGstrUpload}
            label="Drop GSTR-2B Excel files here"
            description="Select all GSTR-2B files at once — different months and years all welcome"
            status={gstrQueue.length > 0 ? 'loading' : 'idle'}
            disabled={step < 2}
            multiple={true}
          />

          {gstrFiles.length > 0 && gstrQueue.length === 0 && (
            <button
              onClick={handleReconcile}
              disabled={reconciling}
              className="mt-4 w-full bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded transition-colors"
            >
              Run Reconciliation — {branch} · {gstrFiles.length} file{gstrFiles.length !== 1 ? 's' : ''} · {gstrTotal} GSTR-2B entries
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
                  Comparing {booksInfo?.books_count} books entries against {gstrTotal} GSTR-2B entries...
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
