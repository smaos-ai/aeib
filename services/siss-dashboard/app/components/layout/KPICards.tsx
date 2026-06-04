'use client';

import React from 'react';

interface KPICardsProps {
  totalCapsules: number;
  totalAP2: number;
  highRiskBlocked: number;
  highRiskApproved: number;
  approvalRate: number;
}

export function KPICards({
  totalCapsules,
  totalAP2,
  highRiskBlocked,
  highRiskApproved,
  approvalRate
}: KPICardsProps) {
  const highRiskTotal = highRiskBlocked + highRiskApproved;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      {/* Total Capsules */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-gray-400 text-sm uppercase tracking-wide">📦 Today's Capsules</p>
        <p className="text-3xl font-bold text-blue-400 mt-2">{totalCapsules}</p>
        <p className="text-xs text-gray-500 mt-2">Governed transactions</p>
      </div>

      {/* AP2 Collected */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-gray-400 text-sm uppercase tracking-wide">💰 AP2 Collected</p>
        <p className="text-3xl font-bold text-green-400 mt-2">${totalAP2.toFixed(4)}</p>
        <p className="text-xs text-gray-500 mt-2">Total settled</p>
      </div>

      {/* High-Risk Actions */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-gray-400 text-sm uppercase tracking-wide">🛡️ High-Risk Actions</p>
        <p className="text-3xl font-bold text-yellow-400 mt-2">{highRiskTotal}</p>
        <p className="text-xs text-gray-500 mt-2">
          {highRiskBlocked} blocked, {highRiskApproved} approved
        </p>
      </div>

      {/* Approval Rate */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-gray-400 text-sm uppercase tracking-wide">✅ Approval Rate</p>
        <p className="text-3xl font-bold text-purple-400 mt-2">{approvalRate.toFixed(0)}%</p>
        <p className="text-xs text-gray-500 mt-2">For high-risk decisions</p>
      </div>
    </div>
  );
}
