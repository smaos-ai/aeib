'use client';

import React, { useState, useEffect } from 'react';
import { useLedger, useCapsuleMetrics, generatePSIDrift, generatePSIHistory } from '@/lib/hooks';
import { KPICards } from '@/app/components/layout/KPICards';
import { AP2Distribution } from '@/app/components/charts/AP2Distribution';
import { PSIDriftGauge } from '@/app/components/charts/PSIDriftGauge';
import { MerkleChainVisualizer } from '@/app/components/charts/MerkleChainVisualizer';
import { DecisionOwnershipTable } from '@/app/components/tables/DecisionOwnershipTable';
import { GovernanceROI } from '@/app/components/metrics/GovernanceROI';
import { ComplianceExport } from '@/app/components/layout/ComplianceExport';

export default function GovernanceDashboard() {
  const { ledger, isLoading } = useLedger(5000);
  const [currentPSI, setCurrentPSI] = useState(0.05);
  const [psiHistory, setPsiHistory] = useState(generatePSIHistory());

  const capsules = ledger?.transactions || [];
  const metrics = useCapsuleMetrics(capsules);
  const currentMerkleRoot = ledger?.current_merkle_root || (metrics.merkleChain[metrics.merkleChain.length - 1] || '');

  // Update PSI drift periodically
  useEffect(() => {
    const interval = setInterval(() => {
      const newPSI = generatePSIDrift();
      setCurrentPSI(newPSI);
      setPsiHistory(prev => {
        const updated = [...prev.slice(1)];
        const hour = new Date().getHours();
        updated.push({
          time: `${(hour < 10 ? '0' : '') + hour}:00`,
          psi: newPSI
        });
        return updated;
      });
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (isLoading && capsules.length === 0) {
    return (
      <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-96">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border border-blue-500 border-t-transparent mx-auto mb-4"></div>
              <p className="text-gray-400">Loading governance dashboard...</p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8 border-b border-gray-800 pb-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold tracking-tight text-white">🌍 Axiom Planet Dashboard</h1>
              <p className="text-gray-400 mt-2">
                Real-time governance membrane — every AI action governed, provenanced, and fairly compensated.
              </p>
            </div>
            <div className="text-right text-sm text-gray-400">
              <p>Status: <span className="text-green-400 font-semibold">Connected</span></p>
              <p className="mt-1">Updated: {new Date().toLocaleTimeString()}</p>
            </div>
          </div>
        </header>

        {/* KPI Cards */}
        <KPICards
          totalCapsules={metrics.totalCapsules}
          totalAP2={metrics.totalAP2}
          highRiskBlocked={metrics.highRiskBlocked}
          highRiskApproved={metrics.highRiskApproved}
          approvalRate={metrics.approvalRate}
        />

        {/* Row 2: AP2 Distribution + PSI Drift */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <AP2Distribution data={metrics.ap2Split} />
          <PSIDriftGauge currentPSI={currentPSI} history={psiHistory} />
        </div>

        {/* Row 3: Merkle Chain + Decision Table */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <MerkleChainVisualizer chain={metrics.merkleChain} />
          <DecisionOwnershipTable capsules={capsules} />
        </div>

        {/* Row 4: Governance ROI */}
        <div className="mb-8">
          <GovernanceROI
            highRiskBlocked={metrics.highRiskBlocked}
            highRiskApproved={metrics.highRiskApproved}
            creatorRoyalties={metrics.ap2Split.creator}
          />
        </div>

        {/* Row 5: Compliance Export */}
        <div className="mb-8">
          <ComplianceExport capsules={capsules} merkleRoot={currentMerkleRoot} />
        </div>

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-gray-800 text-xs text-gray-500 text-center">
          <p>EU AI Act Article 12 Ready | ISO 42001 Compliant | Ed25519 + Secure Enclave</p>
          <p className="mt-2">
            Vision API Endpoint: {process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/v1'}
          </p>
        </footer>
      </div>
    </main>
  );
}
