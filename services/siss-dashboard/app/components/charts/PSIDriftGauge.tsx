'use client';

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface PSIDriftGaugeProps {
  currentPSI: number;
  history?: Array<{ time: string | number; psi: number }>;
}

const PSI_LOW = 0.1;
const PSI_MODERATE = 0.25;

function SimpleGauge({ value, max = 0.5 }: { value: number; max: number }) {
  const percentage = (value / max) * 100;

  let bgColor = 'bg-green-600';
  let textColor = 'text-green-400';
  let statusText = '✅ Model stable';
  let statusClass = 'text-green-400 bg-green-900/20';

  if (value > PSI_MODERATE) {
    bgColor = 'bg-red-600';
    textColor = 'text-red-400';
    statusText = '🚨 Human Gate auto-engaged — no high-risk actions permitted';
    statusClass = 'text-red-400 bg-red-900/20';
  } else if (value > PSI_LOW) {
    bgColor = 'bg-yellow-600';
    textColor = 'text-yellow-400';
    statusText = '⚠️ Flagged for review — monitor closely';
    statusClass = 'text-yellow-400 bg-yellow-900/20';
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <div className="flex justify-between text-xs text-gray-400 mb-2">
          <span>0.0</span>
          <span className="text-gray-300 font-semibold">{PSI_LOW.toFixed(2)}</span>
          <span className="text-gray-300 font-semibold">{PSI_MODERATE.toFixed(2)}</span>
          <span>0.5</span>
        </div>

        <div className="w-full h-6 bg-gray-700 rounded-full overflow-hidden relative">
          <div className="absolute inset-0 flex">
            <div className="flex-1 bg-green-500" style={{ width: `${(PSI_LOW / 0.5) * 100}%` }}></div>
            <div
              className="bg-yellow-500"
              style={{ width: `${((PSI_MODERATE - PSI_LOW) / 0.5) * 100}%` }}
            ></div>
            <div
              className="bg-red-500"
              style={{ width: `${((0.5 - PSI_MODERATE) / 0.5) * 100}%` }}
            ></div>
          </div>
          <div
            className={`absolute top-1/2 transform -translate-y-1/2 w-1 h-8 ${bgColor} rounded transition-all`}
            style={{ left: `${percentage}%` }}
          ></div>
        </div>

        <div className="text-center mt-3">
          <p className={`text-3xl font-bold ${textColor}`}>{value.toFixed(3)}</p>
          <p className="text-xs text-gray-400 uppercase tracking-wide">Population Stability Index</p>
        </div>
      </div>

      <div className={`p-3 rounded border ${statusClass}`}>
        <p className="text-sm font-semibold">{statusText}</p>
      </div>
    </div>
  );
}

export function PSIDriftGauge({ currentPSI, history = [] }: PSIDriftGaugeProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-semibold text-white mb-4">📉 Drift Monitor (Model X)</h2>

      <SimpleGauge value={currentPSI} max={0.5} />

      {history.length > 0 && (
        <div className="mt-8 pt-6 border-t border-gray-700">
          <h3 className="text-sm font-semibold text-gray-200 mb-3">PSI Trend (Last 24h)</h3>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9ca3af" style={{ fontSize: '12px' }} />
                <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} domain={[0, 0.5]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                  labelStyle={{ color: '#e5e7eb' }}
                  formatter={(value: number) => value.toFixed(3)}
                />
                <Line
                  type="monotone"
                  dataKey="psi"
                  stroke="#3b82f6"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-400">
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center">
            <span className="block text-green-400 font-semibold">Stable</span>
            <span className="text-gray-500">PSI &lt; {PSI_LOW.toFixed(2)}</span>
          </div>
          <div className="text-center">
            <span className="block text-yellow-400 font-semibold">Caution</span>
            <span className="text-gray-500">{PSI_LOW.toFixed(2)} – {PSI_MODERATE.toFixed(2)}</span>
          </div>
          <div className="text-center">
            <span className="block text-red-400 font-semibold">Alert</span>
            <span className="text-gray-500">PSI &gt; {PSI_MODERATE.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
