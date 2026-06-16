import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

export default function UploadZone({ onUpload, label, description, status, disabled }) {
  const onDrop = useCallback((files) => {
    if (files[0]) onUpload(files[0])
  }, [onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] },
    disabled: disabled || status === 'loading' || status === 'success',
    multiple: false,
  })

  const borderColor = isDragActive ? 'border-blue-400 bg-blue-950' :
    status === 'success' ? 'border-green-500 bg-green-950' :
    status === 'error' ? 'border-red-500 bg-red-950' :
    'border-slate-600 bg-slate-800/50 hover:border-slate-400'

  return (
    <div {...getRootProps()} className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${borderColor} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}>
      <input {...getInputProps()} />
      {status === 'loading' ? (
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Processing...</span>
        </div>
      ) : status === 'success' ? (
        <div className="flex flex-col items-center gap-2">
          <div className="text-green-400 text-3xl">✓</div>
          <span className="text-green-400 font-medium">{label}</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <div className="text-4xl text-slate-500">📂</div>
          <div className="text-slate-300 font-medium">{label}</div>
          <div className="text-slate-500 text-sm">{description || 'Drop .xlsx or .xls file here, or click to browse'}</div>
        </div>
      )}
    </div>
  )
}
