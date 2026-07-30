/// Phase 34: Security View Page (Next.js Server Component)
/// Renders the security dashboard with real-time AoE event streaming

import React from 'react';
import SecurityViewClient from './SecurityViewClient';

/// Server component that sets up initial layout
export default async function SecurityViewPage() {
  return (
    <div className="w-full min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold text-white mb-2">
            Security Dashboard
          </h1>
          <p className="text-gray-400">
            Real-time monitoring of agent operations, anomalies, and security events
          </p>
        </div>
      </div>

      {/* Main content area */}
      <main className="max-w-7xl mx-auto p-6">
        {/* Client component handles streaming and state */}
        <SecurityViewClient />
      </main>
    </div>
  );
}
