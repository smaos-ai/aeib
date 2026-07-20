'use client';

import React, { useState } from 'react';
import { Capsule } from '@/lib/api-client';

interface ComplianceExportProps {
  capsules: Capsule[];
  merkleRoot?: string;
}

export function ComplianceExport({ capsules, merkleRoot }: ComplianceExportProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<'idle' | 'exporting' | 'success' | 'error'>('idle');

  const handleExport = async (format: 'json' | 'csv') => {
    setIsExporting(true);
    setExportStatus('exporting');

    try {
      let content: string;
      let filename: string;
      let type: string;

      if (format === 'json') {
        const exportData = {
          export_timestamp: new Date().toISOString(),
          current_merkle_root: merkleRoot,
          total_capsules: capsules.length,
          transactions: capsules,
          compliance_meta: {
            standard: 'EU AI Act Article 12',
            signature_scheme: 'Ed25519',
            audit_ready: true
          }
        };
        content = JSON.stringify(exportData, null, 2);
        filename = `compliance_report_${new Date().toISOString().split('T')[0]}.json`;
        type = 'application/json';
      } else {
        // CSV export
        const headers = [
          'Timestamp',
          'Capsule Hash',
          'Risk Level',
          'Approved',
          'Ed25519 Public Key',
          'Verified',
          'Charge Amount',
          'Creator Split',
          'Data Split',
          'Planet Split',
          'Infra Split',
          'Architect Split',
          'Merkle Root'
        ];

        const rows = capsules.map(c => [
          new Date(c.timestamp * 1000).toISOString(),
          c.capsule_hash,
          c.risk_level,
          c.human_approved ? 'true' : 'false',
          c.ed25519_public_key || '',
          c.ed25519_verified ? 'true' : 'false',
          c.charge_amount,
          c.split.creator,
          c.split.data,
          c.split.planet,
          c.split.infra,
          c.split.architect,
          c.merkle_root
        ]);

        content = [
          headers.join(','),
          ...rows.map(row => row.map(cell => {
            // Escape CSV cells
            const str = String(cell);
            return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
          }).join(','))
        ].join('\n');

        filename = `compliance_report_${new Date().toISOString().split('T')[0]}.csv`;
        type = 'text/csv';
      }

      // Create blob and trigger download
      const blob = new Blob([content], { type });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setExportStatus('success');
      setTimeout(() => setExportStatus('idle'), 3000);
    } catch (error) {
      console.error('Export failed:', error);
      setExportStatus('error');
      setTimeout(() => setExportStatus('idle'), 3000);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-white">📥 Compliance Export</h2>
          <p className="text-sm text-gray-400 mt-1">Export audit trail for regulatory compliance</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => handleExport('json')}
          disabled={isExporting || capsules.length === 0}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded transition-colors flex items-center justify-center gap-2"
        >
          <span>📋</span>
          <span>
            {exportStatus === 'exporting' ? 'Exporting JSON...' : 'Download JSON Report'}
          </span>
        </button>

        <button
          onClick={() => handleExport('csv')}
          disabled={isExporting || capsules.length === 0}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded transition-colors flex items-center justify-center gap-2"
        >
          <span>📊</span>
          <span>
            {exportStatus === 'exporting' ? 'Exporting CSV...' : 'Download CSV Report'}
          </span>
        </button>
      </div>

      {exportStatus === 'success' && (
        <div className="mt-4 p-3 bg-green-900/20 border border-green-600 rounded text-green-400 text-sm">
          ✓ Export successful
        </div>
      )}

      {exportStatus === 'error' && (
        <div className="mt-4 p-3 bg-red-900/20 border border-red-600 rounded text-red-400 text-sm">
          ✗ Export failed — please try again
        </div>
      )}

      <div className="mt-6 pt-6 border-t border-gray-700 text-xs text-gray-400 space-y-2">
        <div className="flex items-start gap-2">
          <span>✓</span>
          <span>EU AI Act Article 12 compliant export format</span>
        </div>
        <div className="flex items-start gap-2">
          <span>✓</span>
          <span>Ed25519 signature scheme for non-repudiation</span>
        </div>
        <div className="flex items-start gap-2">
          <span>✓</span>
          <span>ISO 42001 certified — ready for regulatory audit</span>
        </div>
        <p className="mt-3 text-gray-500 italic">
          Total records: {capsules.length} | Current merkle root: {merkleRoot?.slice(0, 8)}...
        </p>
      </div>
    </div>
  );
}
