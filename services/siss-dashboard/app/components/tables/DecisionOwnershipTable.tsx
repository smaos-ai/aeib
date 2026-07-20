'use client';

import React from 'react';
import { Capsule } from '@/lib/api-client';

interface DecisionOwnershipTableProps {
  capsules: Capsule[];
}

export function DecisionOwnershipTable({ capsules }: DecisionOwnershipTableProps) {
  const recent = capsules.slice(-15);

  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-semibold text-white mb-4">👤 Decision Ownership Map</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-gray-300">
          <thead className="border-b border-gray-700">
            <tr className="text-left">
              <th className="px-4 py-2 font-semibold text-gray-200">Timestamp</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Capsule Hash</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Risk Level</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Approved</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Ed25519 Public Key</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Verified</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Amount</th>
              <th className="px-4 py-2 font-semibold text-gray-200">Merkle Root</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((capsule) => (
              <tr key={capsule.capsule_hash} className="border-b border-gray-800 hover:bg-gray-800 transition-colors">
                <td className="px-4 py-3 text-gray-400">
                  {new Date(capsule.timestamp * 1000).toLocaleString()}
                </td>
                <td className="px-4 py-3 font-mono text-blue-400">
                  {capsule.capsule_hash.slice(0, 8)}...
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    capsule.risk_level === 'low' ? 'bg-green-900 text-green-200' :
                    capsule.risk_level === 'medium' ? 'bg-yellow-900 text-yellow-200' :
                    'bg-red-900 text-red-200'
                  }`}>
                    {capsule.risk_level}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={capsule.human_approved ? 'text-green-400' : 'text-red-400'}>
                    {capsule.human_approved ? '✓' : '✗'}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {capsule.ed25519_public_key ? (
                    <code className="bg-gray-800 px-2 py-1 rounded">
                      {capsule.ed25519_public_key.slice(0, 10)}...
                    </code>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {capsule.ed25519_verified ? (
                    <span className="text-green-400">✓ Verified</span>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-blue-400">
                  ${capsule.charge_amount.toFixed(4)}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                  {capsule.merkle_root.slice(0, 8)}...
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 text-sm text-gray-400">
        <p>Every high-risk action is tied to a verified Ed25519 public key — cryptographically non-repudiable.</p>
      </div>
    </div>
  );
}
