import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { getTallyPreview, downloadTallyXml, downloadTallyXmlFiltered } from '../api'

const FIELD_MAPPING = [
  { rapidtech: 'Vendor Name', tally: 'Party Ledger Name' },
  { rapidtech: 'Invoice Number', tally: 'Voucher Number' },
  { rapidtech: 'Invoice Date', tally: 'Date' },
  { rapidtech: 'GSTIN', tally: 'Party GSTIN' },
  { rapidtech: 'Taxable Value', tally: 'Taxable Amount' },
  { rapidtech: 'CGST', tally: 'CGST Ledger Amount' },
  { rapidtech: 'SGST', tally: 'SGST Ledger Amount' },
  { rapidtech: 'IGST', tally: 'IGST Ledger Amount' },
  { rapidtech: 'Expense Type', tally: 'Purchase/Expense Ledger' },
  { rapidtech: 'Narration', tally: 'Voucher Narration' },
]

const fmt = (n) => n != null ? new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(n) : '—'

export default function Tally() {
  const { sessionId } = useParams()
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  // Period filter state
  const [filterMonth, setFilterMonth] = useState('')
  const [filterYear, setFilterYear] = useState('')
  const [filteredCount, setFilteredCount] = useState(null)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    getTallyPreview(sessionId).then(r => setPreview(r.data)).finally(() => setLoading(false))
  }, [sessionId])

  // Update filtered count when filter changes
  useEffect(() => {
    if (!sessionId) return
    if (!filterMonth && !filterYear) {
      setFilteredCount(preview?.total_reconciled ?? null)
      return
    }
    setFilterLoading(true)
    getTallyPreview(sessionId, filterMonth || undefined, filterYear || undefined)
      .then(r => setFilteredCount(r.data.filtered_count))
      .catch(() => setFilteredCount(null))
      .finally(() => setFilterLoading(false))
  }, [filterMonth, filterYear, preview])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await downloadTallyXml(sessionId)
      triggerDownload(res.data, `tally_import_${sessionId}.xml`)
      toast.success('Tally XML downloaded')
    } catch {
      toast.error('Download failed')
    } finally {
      setDownloading(false)
    }
  }

  const handleFilteredDownload = async () => {
    setDownloading(true)
    try {
      const res = await downloadTallyXmlFiltered(
        sessionId,
        filterMonth || undefined,
        filterYear || undefined,
      )
      const suffix = filterMonth ? `_${filterMonth}` : filterYear ? `_${filterYear}` : ''
      triggerDownload(res.data, `tally_import_${sessionId}${suffix}.xml`)
      toast.success('Tally XML downloaded')
    } catch {
      toast.error('Download failed')
    } finally {
      setDownloading(false)
    }
  }

  const triggerDownload = (data, filename) => {
    const url = URL.createObjectURL(new Blob([data], { type: 'application/xml' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  // Derive available years from available_months
  const availableMonths = preview?.available_months || []
  const availableYears = [...new Set(availableMonths.map(m => m.split('-')[1]).filter(Boolean))].sort((a, b) => b - a)

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Tally Export</h1>
          <p className="text-slate-400 text-sm mt-1">Export reconciled vouchers as Tally-compatible XML</p>
        </div>
        {preview && (
          <div className="flex items-center gap-4">
            <span className="text-slate-400 text-sm font-mono">{preview.total_reconciled} vouchers total</span>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold px-5 py-2 rounded transition-colors text-sm"
            >
              {downloading ? 'Downloading...' : 'Download All'}
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Loading preview...</div>
      ) : (
        <>
          {/* Download by Period */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Download by Period</h3>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Month</label>
                <select
                  value={filterMonth}
                  onChange={e => { setFilterMonth(e.target.value); if (e.target.value) setFilterYear('') }}
                  className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500 min-w-[160px]"
                >
                  <option value="">All Months</option>
                  {availableMonths.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Year</label>
                <select
                  value={filterYear}
                  onChange={e => { setFilterYear(e.target.value); if (e.target.value) setFilterMonth('') }}
                  className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500 min-w-[120px]"
                >
                  <option value="">All Years</option>
                  {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <div className="flex items-end gap-3">
                <div className="text-xs text-slate-400 pb-2.5">
                  {filterLoading ? (
                    <span className="text-slate-500">Calculating...</span>
                  ) : (
                    <span>
                      <span className="text-slate-200 font-mono font-semibold">
                        {filteredCount ?? preview?.total_reconciled ?? 0}
                      </span>
                      {' '}voucher{(filteredCount ?? preview?.total_reconciled ?? 0) !== 1 ? 's' : ''} in download
                    </span>
                  )}
                </div>
                <button
                  onClick={handleFilteredDownload}
                  disabled={downloading || filterLoading}
                  className="bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white font-semibold px-5 py-2 rounded transition-colors text-sm"
                >
                  {downloading ? 'Downloading...' : 'Download XML'}
                </button>
              </div>
            </div>
          </div>

          {/* Preview Vouchers */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">
              Preview (first {preview?.preview?.length || 0} vouchers of {preview?.total_reconciled})
            </h3>
            {preview?.preview?.length === 0 ? (
              <p className="text-slate-500 text-sm py-4">No reconciled entries to export. Run reconciliation first.</p>
            ) : (
              <div className="space-y-3">
                {preview?.preview?.map((v, i) => (
                  <div key={i} className="bg-slate-700/50 border border-slate-600 rounded p-4 text-sm">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                      <div><span className="text-slate-500 text-xs">Voucher Type</span><div className="text-slate-200 font-mono">{v.voucher_type}</div></div>
                      <div><span className="text-slate-500 text-xs">Date</span><div className="text-slate-200 font-mono">{v.date}</div></div>
                      <div><span className="text-slate-500 text-xs">Voucher No</span><div className="text-slate-200 font-mono">{v.voucher_number}</div></div>
                      <div><span className="text-slate-500 text-xs">Party GSTIN</span><div className="text-slate-200 font-mono text-xs">{v.gstin}</div></div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                      <div className="col-span-2"><span className="text-slate-500 text-xs">Party Ledger</span><div className="text-slate-200">{v.party_ledger}</div></div>
                      <div><span className="text-slate-500 text-xs">Expense Ledger</span><div className="text-slate-200">{v.expense_ledger}</div></div>
                    </div>
                    <div className="grid grid-cols-4 gap-3 pt-3 border-t border-slate-600">
                      <div className="text-right"><span className="text-slate-500 text-xs block">Taxable</span><span className="font-mono text-slate-200">₹{fmt(v.taxable_amount)}</span></div>
                      <div className="text-right"><span className="text-slate-500 text-xs block">CGST</span><span className="font-mono text-slate-200">₹{fmt(v.cgst)}</span></div>
                      <div className="text-right"><span className="text-slate-500 text-xs block">SGST</span><span className="font-mono text-slate-200">₹{fmt(v.sgst)}</span></div>
                      <div className="text-right"><span className="text-slate-500 text-xs block">IGST</span><span className="font-mono text-slate-200">₹{fmt(v.igst)}</span></div>
                    </div>
                    {v.narration && <div className="mt-2 text-xs text-slate-400 italic">Narration: {v.narration}</div>}
                  </div>
                ))}
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
