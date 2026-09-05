'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

interface EmailCampaign {
  id: string;
  sequence_day: number;
  email_type: string;
  status: string;
  sent_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
}

interface CampaignMetrics {
  creator_id: string;
  total_sent: number;
  total_opened: number;
  total_clicked: number;
  open_rate: number;
  click_rate: number;
}

export default function EmailCampaignDashboard({
  creatorId
}: {
  creatorId: string;
}) {
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [metrics, setMetrics] = useState<CampaignMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [campaignStarted, setCampaignStarted] = useState(false);

  useEffect(() => {
    const fetchCampaignData = async () => {
      try {
        const response = await axios.get(
          `/api/email-campaigns/history?creator_id=${creatorId}`
        );
        setCampaigns(response.data.history || []);
        setMetrics(response.data.metrics || null);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch campaign data');
      } finally {
        setLoading(false);
      }
    };

    if (creatorId) {
      fetchCampaignData();
    }
  }, [creatorId, campaignStarted]);

  const handleStartCampaign = async () => {
    try {
      await axios.post('/api/email-campaigns/start', {
        creator_id: creatorId
      });
      setCampaignStarted(true);
      setTimeout(() => setCampaignStarted(false), 500);
    } catch (err: any) {
      setError(err.message || 'Failed to start campaign');
    }
  };

  const getEmailTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      welcome: 'Welcome Email',
      getting_started: 'Getting Started',
      feature_highlight: 'Feature Highlight',
      success_story: 'Success Story',
      monetization_tips: 'Monetization Tips',
      community_feature: 'Community Feature',
      upgrade_offer: 'Upgrade Offer',
      retention: 'Retention Email'
    };
    return labels[type] || type;
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'sent':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'scheduled':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return <div className="p-4">Loading email campaign data...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-600">Error: {error}</div>;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">Email Campaign</h2>
        {campaigns.length === 0 && (
          <button
            onClick={handleStartCampaign}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Start Campaign
          </button>
        )}
      </div>

      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 p-4 rounded">
            <div className="text-sm text-gray-600">Emails Sent</div>
            <div className="text-2xl font-bold text-blue-600">
              {metrics.total_sent}
            </div>
          </div>

          <div className="bg-green-50 p-4 rounded">
            <div className="text-sm text-gray-600">Opened</div>
            <div className="text-2xl font-bold text-green-600">
              {metrics.total_opened}
            </div>
          </div>

          <div className="bg-purple-50 p-4 rounded">
            <div className="text-sm text-gray-600">Open Rate</div>
            <div className="text-2xl font-bold text-purple-600">
              {metrics.open_rate.toFixed(1)}%
            </div>
          </div>

          <div className="bg-orange-50 p-4 rounded">
            <div className="text-sm text-gray-600">Click Rate</div>
            <div className="text-2xl font-bold text-orange-600">
              {metrics.click_rate.toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      {campaigns.length > 0 ? (
        <div>
          <h3 className="text-lg font-semibold mb-4">Campaign Sequence</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border p-3 text-left">Day</th>
                  <th className="border p-3 text-left">Email Type</th>
                  <th className="border p-3 text-left">Status</th>
                  <th className="border p-3 text-left">Sent</th>
                  <th className="border p-3 text-left">Opened</th>
                  <th className="border p-3 text-left">Clicked</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => (
                  <tr key={campaign.id} className="hover:bg-gray-50">
                    <td className="border p-3 font-semibold">
                      Day {campaign.sequence_day}
                    </td>
                    <td className="border p-3">
                      {getEmailTypeLabel(campaign.email_type)}
                    </td>
                    <td className="border p-3">
                      <span className={`px-2 py-1 rounded text-sm ${getStatusColor(campaign.status)}`}>
                        {campaign.status}
                      </span>
                    </td>
                    <td className="border p-3">
                      {campaign.sent_at ? new Date(campaign.sent_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="border p-3">
                      {campaign.opened_at ? '✓' : '-'}
                    </td>
                    <td className="border p-3">
                      {campaign.clicked_at ? '✓' : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center p-8 bg-gray-50 rounded">
          <p className="text-gray-600">No email campaigns scheduled yet.</p>
        </div>
      )}
    </div>
  );
}
