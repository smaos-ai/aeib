import Link from 'next/link';

export default function Landing() {
  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 border-b border-gray-800 pb-4">
          <h1 className="text-4xl font-bold tracking-tight text-white">🌍 SISS Dashboard</h1>
          <p className="text-gray-400 mt-2">Sovereign Intelligence Sovereign Systems — Governance, Compliance, and Real-Time Monitoring.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Link href="/governance-dashboard" className="bg-gray-900 border border-gray-800 rounded-xl p-8 shadow-sm hover:border-blue-500 transition-colors block">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-2xl font-semibold text-blue-400">Governance Dashboard</h2>
              <span className="bg-blue-900 text-xs px-3 py-1 rounded text-blue-200">Production</span>
            </div>
            <div className="space-y-3 text-sm text-gray-400">
              <p>Real-time governance membrane for AI action oversight.</p>
              <ul className="list-disc list-inside space-y-1">
                <li>AP2 Distribution (Pie Chart)</li>
                <li>Decision Ownership (Ed25519 Table)</li>
                <li>Merkle Chain Visualizer</li>
                <li>PSI Drift Gauge Monitor</li>
                <li>Governance ROI Metrics</li>
                <li>Compliance Export (JSON/CSV)</li>
              </ul>
            </div>
          </Link>

          <Link href="/creator-platform" className="bg-gray-900 border border-gray-800 rounded-xl p-8 shadow-sm hover:border-green-500 transition-colors block">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-2xl font-semibold text-green-400">Creator Platform</h2>
              <span className="bg-green-900 text-xs px-3 py-1 rounded text-green-200">MVP</span>
            </div>
            <div className="space-y-3 text-sm text-gray-400">
              <p>Real-time royalty tracking and payments for content creators.</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Creator Profiles & Onboarding</li>
                <li>Real-Time MRR Dashboard</li>
                <li>Royalty Settlement Ledger</li>
                <li>Stripe Payment Integration</li>
                <li>WebSocket Live Updates</li>
                <li>Monthly Breakdown Analytics</li>
              </ul>
            </div>
          </Link>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-2xl font-semibold text-green-400">System Status</h2>
              <span className="bg-green-900 text-xs px-3 py-1 rounded text-green-200">Connected</span>
            </div>
            <div className="space-y-3 text-sm text-gray-400">
              <div className="flex justify-between">
                <span>Vision API Endpoint:</span>
                <code className="text-gray-300">http://localhost:8000/v1</code>
              </div>
              <div className="flex justify-between">
                <span>WebSocket Support:</span>
                <code className="text-gray-300">ws://localhost:8000/ws</code>
              </div>
              <div className="flex justify-between">
                <span>Dashboard Version:</span>
                <code className="text-gray-300">2.0.0 (React/Next.js)</code>
              </div>
              <div className="flex justify-between">
                <span>Compliance Standard:</span>
                <code className="text-gray-300">EU AI Act Article 12</code>
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-12 pt-6 border-t border-gray-800 text-xs text-gray-500 text-center">
          <p>Production Ready • ISO 42001 Compliant • Ed25519 Non-Repudiation</p>
        </footer>
      </div>
    </main>
  );
}
