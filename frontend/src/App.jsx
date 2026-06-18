import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Results from './pages/Results'
import Tally from './pages/Tally'
import History from './pages/History'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155' } }} />
      <Routes>
        <Route path="/" element={<Layout><Home /></Layout>} />
        <Route path="/history" element={<Layout><History /></Layout>} />
        <Route path="/dashboard/:sessionId" element={<Layout><Dashboard /></Layout>} />
        <Route path="/results/:sessionId" element={<Layout><Results /></Layout>} />
        <Route path="/tally/:sessionId" element={<Layout><Tally /></Layout>} />
      </Routes>
    </BrowserRouter>
  )
}
