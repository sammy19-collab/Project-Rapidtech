import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { getTallyPreview, downloadTallyXmlFiltered } from '../api'

const FIELD_MAPPING = [
  { rapidtech: 'Vendor Name', tally: 'Party Ledger Name' },
  { rapidtech: 'Invoice Number', tally: 'Voucher Number' },
  { rapidtech: 'Invoice Date', tally: 'Date' },
  { rapidtech: 'GSTIN', tally: 'Party GSTIN' },
  { rapidtech: 'Taxable Value', tally: 'Taxable Amount' },
  { rapidtech: 'CGST', tally: 'CGST Input Ledger' },
  { rapidtech: 'SGST', tally: 'SGST Input Ledger' },
  { rapidtech: 'IGST', tally: 'IGST Input Ledger' },
  { rapidtech: 'Expense Type', tally: 'Purchase/Expense Ledger' },
  { rapidtech: 'Narration', tally: 'Voucher Narration' },
]

const fmt = (n) => n != null ? new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(n) : '—'

export default function Tally() {
  const { sessionId } = useParams()
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [filterMonth, setFilterMonth] = useState('')
  const [filterYear, setFilterYear] = useState('')

  useEffect(() => {
    getTallyPreview(sessionId).then(r => setPreview(r.data)).finally(() => setLoading(false))
  }, [sessionId])

  const filteredCount = (() => {
    if (!preview) return 0
    if (!filterMonth && !filterYear) return preview.total_reconciled
    return preview.filtered_count ?? preview.total_reconciled
  })()

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const params = {}
      if (filterMonth) params.month = filterMonth
      else if (filterYear) params.year = filterYear
      const res = await downloadTallyXmlFiltered(sessionId, params)
      const suffix = filterMonth ? `_${filterMonth}` : filterYear ? `_${filterYear}` : ''
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/xml' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `tally_import_session${sessionId}${suffix}.xml`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Tally XML downloaded')
    } catch {
      toast.error('Download failed')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Tally Export</h1>
          <p className="text-slate-400 text-sm mt-1">Export reconciled vouchers as Tally-compatible XML</p>
        </div>
        {preview && (
          <span className="text-slate-400 text-sm font-mono">{preview.total_reconciled} total reconciled vouchers</span>
        )}
      </div>

      {/* Download by Period */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Download Tally XML</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1.5">Filter by Month</label>
            <select value={filterMonth} onChange={e => { setFilterMonth(e.target.value); setFilterYear('') }}
              className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 min-w-[160px]">
              <option value="">All Months</option>
              {(preview?.available_months || []).map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1.5">Filter by Year</label>
            <select value={filterYear} onChange={e => { setFilterYear(e.target.value); setFilterMonth('') }}
              className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 min-w-[120px]">
              <option value="">All Years</option>
              {(preview?.available_years || []).map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-400">
              {filterMonth || filterYear
                ? <><span className="text-slate-200 font-mono">{filteredCount}</span> vouchers match</>
                : <><span className="text-slate-200 font-mono">{preview?.total_reconciled ?? 0}</span> vouchers (all)</>}
            </span>
            <button onClick={handleDownload} disabled={downloading || !preview}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-5 py-2 rounded transition-colors text-sm">
              {downloading ? 'Downloading...' : 'Download XML'}
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Select a month or year to download only that period's vouchers, or leave blank to download all.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Loading preview...</div>
      ) : (
        <>
          {/* Preview Vouchers */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">
              Preview (first 5 vouchers of {preview?.total_reconciled})
            </h3>
            {!preview?.xml_preview || preview.total_reconciled === 0 ? (
              <p className="text-slate-500 text-sm py-4">No reconciled entries to export.</p>
            ) : (
              <div className="bg-slate-900 rounded p-4 overflow-x-auto">
                <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap">{preview.xml_preview?.slice(0, 1500)}{preview.xml_preview?.length > 1500 ? '\n...' : ''}</pre>
              </div>
            )}
          </div>

          {/* Ledger Mapping */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Ledger Field Mapping</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-2 px-3 text-xs text-slate-400 uppercase">RapidTech Field</th>
                  <th className="text-left py-2 px-3 text-xs text-slate-400 uppercase">Tally Field</th>
                </tr>
              </thead>
              <tbody>
                {FIELD_MAPPING.map((m, i) => (
                  <tr key={i} className="border-b border-slate-800">
                    <td className="py-2 px-3 text-slate-300 font-mono text-xs">{m.rapidtech}</td>
                    <td className="py-2 px-3 text-blue-400 font-mono text-xs">{m.tally}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
