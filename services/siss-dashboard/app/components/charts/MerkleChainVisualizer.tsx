'use client';

import React from 'react';

interface MerkleChainVisualizerProps {
  chain: string[];
}

export function MerkleChainVisualizer({ chain }: MerkleChainVisualizerProps) {
  const displayChain = chain.slice(-10);

  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-semibold text-white mb-4">🔗 Merkle Chain (Last 10 Roots)</h2>
      <div className="space-y-2">
        {displayChain.length === 0 ? (
          <div className="text-gray-400 text-center py-8">
            <p>No merkle roots yet</p>
          </div>
        ) : (
          displayChain.map((root, idx) => (
            <div key={idx} className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
                {displayChain.length - idx}
              </div>
              <div className="flex-1">
                <code className="bg-gray-800 px-3 py-2 rounded text-sm text-gray-200 block font-mono">
                  {root.slice(0, 12)}...{root.slice(-4)}
                </code>
              </div>
              <div className="text-xs text-gray-400">
                {idx === displayChain.length - 1 ? '← Latest' : ''}
              </div>
            </div>
          ))
        )}
      </div>

      {displayChain.length > 0 && (
        <div className="mt-6 pt-4 border-t border-gray-700">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Current Root</p>
              <code className="text-sm font-mono text-blue-400 break-all">
                {displayChain[displayChain.length - 1]}
              </code>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Chain Depth</p>
              <p className="text-lg font-bold text-green-400">{displayChain.length}</p>
            </div>
          </div>
        </div>
      )}

      <div className="mt-4 text-sm text-gray-400">
        <p>Immutable audit trail — each Capsule extends the chain.</p>
      </div>
    </div>
  );
}
