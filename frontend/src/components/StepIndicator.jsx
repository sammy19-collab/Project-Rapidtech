export default function StepIndicator({ steps, current }) {
  return (
    <div className="flex items-center justify-center mb-8">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center">
          <div className={`flex items-center gap-2 ${i < current ? 'text-green-400' : i === current ? 'text-blue-400' : 'text-slate-600'}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
              i < current ? 'border-green-400 bg-green-900' :
              i === current ? 'border-blue-400 bg-blue-900' :
              'border-slate-600 bg-slate-800'}`}>
              {i < current ? '✓' : i + 1}
            </div>
            <span className="text-sm font-medium hidden sm:block">{step}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`h-px w-8 sm:w-16 mx-2 ${i < current ? 'bg-green-600' : 'bg-slate-700'}`} />
          )}
        </div>
      ))}
    </div>
  )
}
