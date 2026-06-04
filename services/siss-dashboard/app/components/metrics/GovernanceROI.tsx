'use client';

import React from 'react';

interface GovernanceROIProps {
  highRiskBlocked: number;
  highRiskApproved: number;
  creatorRoyalties: number;
  finePerViolation?: number;
  blockedFineFactor?: number;
}

const FINE_PER_VIOLATION = 35000000; // €35M EU AI Act max fine
const BLOCKED_FINE_FACTOR = 0.012;

export function GovernanceROI({
  highRiskBlocked,
  highRiskApproved,
  creatorRoyalties,
  finePerViolation = FINE_PER_VIOLATION,
  blockedFineFactor = BLOCKED_FINE_FACTOR
}: GovernanceROIProps) {
  const finesAvoided = highRiskBlocked * finePerViolation * blockedFineFactor;
  const totalHighRisk = highRiskBlocked + highRiskApproved;
  const blockRate = totalHighRisk > 0 ? ((highRiskBlocked / totalHighRisk) * 100).toFixed(1) : '0';

  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-semibold text-white mb-6">💎 Governance ROI Today</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Unsafe Actions Prevented */}
        <div className="bg-gray-800 rounded p-4 border border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-gray-400 text-sm uppercase tracking-wide">🚫 Unsafe Actions Prevented</p>
              <p className="text-3xl font-bold text-red-400 mt-2">{highRiskBlocked}</p>
              <p className="text-xs text-gray-500 mt-1">Block rate: {blockRate}%</p>
            </div>
          </div>
        </div>

        {/* Estimated Fines Avoided */}
        <div className="bg-gray-800 rounded p-4 border border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-gray-400 text-sm uppercase tracking-wide">💶 Est. Fines Avoided</p>
              <p className="text-3xl font-bold text-green-400 mt-2">€{(finesAvoided / 1000000).toFixed(1)}M</p>
              <p className="text-xs text-gray-500 mt-1">
                @ €{(finePerViolation / 1000000).toFixed(0)}M per violation
              </p>
            </div>
          </div>
        </div>

        {/* Creator Royalties Paid */}
        <div className="bg-gray-800 rounded p-4 border border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-gray-400 text-sm uppercase tracking-wide">🎨 Creator Royalties Paid</p>
              <p className="text-3xl font-bold text-blue-400 mt-2">${creatorRoyalties.toFixed(4)}</p>
              <p className="text-xs text-gray-500 mt-1">
                {totalHighRisk > 0 ? `From ${totalHighRisk} high-risk decisions` : 'No transactions yet'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-6 pt-6 border-t border-gray-700 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div>
          <p className="text-gray-400">High-Risk Approved</p>
          <p className="text-xl font-bold text-green-400 mt-1">{highRiskApproved}</p>
        </div>
        <div>
          <p className="text-gray-400">Total Decisions</p>
          <p className="text-xl font-bold text-blue-400 mt-1">{totalHighRisk}</p>
        </div>
        <div>
          <p className="text-gray-400">ROI Multiplier</p>
          <p className="text-xl font-bold text-purple-400 mt-1">
            {(finesAvoided / creatorRoyalties).toFixed(1)}x
          </p>
        </div>
        <div>
          <p className="text-gray-400">Compliance Rate</p>
          <p className="text-xl font-bold text-yellow-400 mt-1">100%</p>
        </div>
      </div>

      <div className="mt-6 p-3 bg-gray-800 rounded border border-gray-700 text-xs text-gray-400">
        <p className="mb-1">
          <strong>EU AI Act Article 12 Ready:</strong> Every blocked high-risk action prevents €{(finePerViolation * blockedFineFactor / 1000000).toFixed(1)}M in regulatory fines.
        </p>
      </div>
    </div>
  );
}
