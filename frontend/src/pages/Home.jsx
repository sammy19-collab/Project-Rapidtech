import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import StepIndicator from '../components/StepIndicator'
import UploadZone from '../components/UploadZone'
import { uploadBooks, uploadGSTR2B, runReconciliation } from '../api'

const STEPS = ['Upload Books', 'Upload GSTR-2B', 'Reconcile']

export default function Home() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [sessionId, setSessionId] = useState(null)
  const [booksStatus, setBooksStatus] = useState('idle')
  const [gstrStatus, setGstrStatus] = useState('idle')
  const [booksInfo, setBooksInfo] = useState(null)
  const [gstrInfo, setGstrInfo] = useState(null)
  const [reconciling, setReconciling] = useState(false)
  const [summary, setSummary] = useState(null)

  const handleBooksUpload = async (file) => {
    setBooksStatus('loading')
    try {
      const res = await uploadBooks(file)
      setSessionId(res.data.session_id)
      setBooksInfo(res.data)
      setBooksStatus('success')
      setStep(1)
      toast.success(`Books loaded: ${res.data.books_count} records`)
    } catch (e) {
      setBooksStatus('error')
      toast.error(e.response?.data?.detail || 'Failed to upload Books file')
    }
  }

  const handleGstrUpload = async (file) => {
    setGstrStatus('loading')
    try {
      const res = await uploadGSTR2B(sessionId, file)
      setGstrInfo(res.data)
      setGstrStatus('success')
      toast.success(`GSTR-2B loaded: ${res.data.gstr2b_count} records`)
    } catch (e) {
      setGstrStatus('error')
      toast.error(e.response?.data?.detail || 'Failed to upload GSTR-2B file')
    }
  }

  const handleReconcile = async () => {
    setReconciling(true)
    setStep(2)
    try {
      const res = await runReconciliation(sessionId)
      setSummary(res.data.summary)
      toast.success('Reconciliation complete!')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reconciliation failed')
      setStep(1)
    } finally {
      setReconciling(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-100">GST Reconciliation</h1>
        <p className="text-slate-400 text-sm mt-1">Upload Books & GSTR-2B to run automated reconciliation</p>
      </div>

      <StepIndicator steps={STEPS} current={step} />

      <div className="space-y-6">
        {/* Step 1: Books */}
        <div className={`bg-slate-800 border border-slate-700 rounded-lg p-6 ${step !== 0 && booksStatus !== 'success' ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 1: Upload Books Excel</h2>
            {booksInfo && <span className="text-green-400 text-sm font-mono">{booksInfo.books_count} records</span>}
          </div>
          <UploadZone
            onUpload={handleBooksUpload}
            label={booksStatus === 'success' ? `✓ ${booksInfo?.filename}` : 'Drop RapidTech Books Excel here'}
            description="Sheet must be named 'Books'"
            status={booksStatus}
            disabled={step !== 0}
          />
        </div>

        {/* Step 2: GSTR-2B */}
        <div className={`bg-slate-800 border border-slate-700 rounded-lg p-6 ${step < 1 ? 'opacity-40 pointer-events-none' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-200">Step 2: Upload GSTR-2B Excel</h2>
            {gstrInfo && <span className="text-green-400 text-sm font-mono">{gstrInfo.gstr2b_count} records</span>}
          </div>
          <UploadZone
            onUpload={handleGstrUpload}
            label={gstrStatus === 'success' ? `✓ ${gstrInfo?.filename}` : 'Drop GSTR-2B Excel here'}
            description="Sheet must be named '2B' (downloaded from GST portal)"
            status={gstrStatus}
            disabled={step < 1 || gstrStatus === 'success'}
          />
          {gstrStatus === 'success' && (
            <button
              onClick={handleReconcile}
              className="mt-4 w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2.5 rounded transition-colors"
            >
              Run Reconciliation
            </button>
          )}
        </div>

        {/* Step 3: Result */}
        {step === 2 && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="font-semibold text-slate-200 mb-4">Step 3: Reconciliation</h2>
            {reconciling ? (
              <div className="flex flex-col items-center gap-3 py-6">
                <div className="w-10 h-10 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-slate-400">Comparing {booksInfo?.books_count} books entries against {gstrInfo?.gstr2b_count} GSTR-2B entries...</span>
              </div>
            ) : summary ? (
              <div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
                  {[
                    { label: 'Total Books', value: summary.total_books, color: 'text-slate-300' },
                    { label: 'Reconciled', value: summary.reconciled, color: 'text-green-400' },
                    { label: 'Probable Matches', value: summary.probable, color: 'text-amber-400' },
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
                  <button onClick={() => navigate(`/dashboard/${sessionId}`)} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded transition-colors text-sm">
                    View Dashboard
                  </button>
                  <button onClick={() => navigate(`/results/${sessionId}`)} className="flex-1 bg-slate-600 hover:bg-slate-500 text-white font-semibold py-2 rounded transition-colors text-sm">
                    View Results
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
