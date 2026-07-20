'use client';

import React from 'react';
import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from 'recharts';

interface AP2DistributionProps {
  data: {
    creator: number;
    data: number;
    planet: number;
    infra: number;
    architect: number;
  };
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const LABELS = [
  { key: 'creator', label: 'Creator (60%)' },
  { key: 'data', label: 'Data (20%)' },
  { key: 'planet', label: 'Planet (10%)' },
  { key: 'infra', label: 'Infra (9%)' },
  { key: 'architect', label: 'Architect (1%)' }
];

export function AP2Distribution({ data }: AP2DistributionProps) {
  const chartData = LABELS.map((item, idx) => ({
    name: item.label,
    value: data[item.key as keyof typeof data],
    fill: COLORS[idx]
  })).filter(item => item.value > 0);

  const total = Object.values(data).reduce((sum, val) => sum + val, 0);

  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-semibold text-white mb-4">💸 AP2 Distribution (Real-time)</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => `$${value.toFixed(4)}`}
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
              labelStyle={{ color: '#e5e7eb' }}
            />
            <Legend wrapperStyle={{ color: '#e5e7eb' }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 text-sm text-gray-400">
        <p className="font-semibold text-gray-200 mb-2">Total Collected: ${total.toFixed(4)}</p>
        <p>Every $0.003 governed action splits automatically — 99% to creators, data, planet, infra; 1% to Architect.</p>
      </div>
    </div>
  );
}
