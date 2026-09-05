'use client';

import { useEffect, useState } from 'react';
import useSWR from 'swr';
import axios from 'axios';
import ReferralEarningsDashboard from '@/lib/components/ReferralEarningsDashboard';
import EmailCampaignDashboard from '@/lib/components/EmailCampaignDashboard';

interface Creator {
  id: string;
  name: string;
  email: string;
  wallet: string;
  stripe_customer_id: string;
  created_at: string;
}

interface RoyaltySummary {
  creator_id: string;
  total_amount: number;
  total_gross: number;
  total_fees: number;
  total_net: number;
  entries: any[];
  monthly_breakdown: Record<string, number>;
}

const fetcher = (url: string) => axios.get(url).then(res => res.data);

export default function CreatorDashboard() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [selectedCreator, setSelectedCreator] = useState<Creator | null>(null);
  const [royalties, setRoyalties] = useState<RoyaltySummary | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch all creators
  const { data: creatorsData } = useSWR('/api/creators', fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false
  });

  useEffect(() => {
    if (creatorsData) {
      setCreators(creatorsData);
      if (!selectedCreator && creatorsData.length > 0) {
        setSelectedCreator(creatorsData[0]);
      }
    }
  }, [creatorsData]);

  // Fetch royalties for selected creator
  useEffect(() => {
    if (selectedCreator) {
      const fetchRoyalties = async () => {
        try {
          setLoading(true);
          const response = await axios.get(
            `/api/creators/${selectedCreator.id}/royalties`
          );
          setRoyalties(response.data);
        } catch (error) {
          console.error('Failed to fetch royalties:', error);
        } finally {
          setLoading(false);
        }
      };

      fetchRoyalties();

      // Refresh every 5 seconds
      const interval = setInterval(fetchRoyalties, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedCreator]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Creator Platform</h1>
          <p className="text-lg text-gray-600">Real-time royalty tracking and settlements</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Creators List */}
          <div className="lg:col-span-1 bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Creators</h2>

            <div className="space-y-2">
              {creators.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No creators yet</p>
              ) : (
                creators.map(creator => (
                  <button
                    key={creator.id}
                    onClick={() => setSelectedCreator(creator)}
                    className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
                      selectedCreator?.id === creator.id
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                    }`}
                  >
                    <div className="font-semibold text-sm">{creator.name}</div>
                    <div className="text-xs opacity-75">{creator.email}</div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3 space-y-6">
            {selectedCreator && royalties ? (
              <>
                {/* Creator Profile Card */}
                <div className="bg-white rounded-lg shadow-lg p-8">
                  <h2 className="text-3xl font-bold text-gray-900 mb-6">
                    {selectedCreator.name}
                  </h2>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div>
                      <label className="text-gray-600 text-sm">Email</label>
                      <p className="text-gray-900 font-medium">{selectedCreator.email}</p>
                    </div>
                    <div>
                      <label className="text-gray-600 text-sm">Wallet</label>
                      <p className="text-gray-900 font-medium font-mono text-sm">
                        {selectedCreator.wallet.slice(0, 6)}...{selectedCreator.wallet.slice(-4)}
                      </p>
                    </div>
                  </div>

                  <hr className="my-6" />

                  {/* Royalty Stats */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-lg">
                      <p className="text-gray-600 text-sm font-semibold">Total MRR</p>
                      <p className="text-3xl font-bold text-blue-600 mt-2">
                        €{royalties.total_amount.toFixed(2)}
                      </p>
                    </div>

                    <div className="bg-gradient-to-br from-green-50 to-green-100 p-6 rounded-lg">
                      <p className="text-gray-600 text-sm font-semibold">Gross Revenue</p>
                      <p className="text-3xl font-bold text-green-600 mt-2">
                        €{royalties.total_gross.toFixed(2)}
                      </p>
                    </div>

                    <div className="bg-gradient-to-br from-red-50 to-red-100 p-6 rounded-lg">
                      <p className="text-gray-600 text-sm font-semibold">Platform Fees</p>
                      <p className="text-3xl font-bold text-red-600 mt-2">
                        €{royalties.total_fees.toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Recent Royalties */}
                <div className="bg-white rounded-lg shadow-lg p-8">
                  <h3 className="text-2xl font-bold text-gray-900 mb-6">
                    Recent Royalties {loading && '(updating)'}
                  </h3>

                  {royalties.entries.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No royalties recorded</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-3 px-4 text-gray-600 font-semibold">
                              Date
                            </th>
                            <th className="text-left py-3 px-4 text-gray-600 font-semibold">
                              Net Amount
                            </th>
                            <th className="text-left py-3 px-4 text-gray-600 font-semibold">
                              Gross Amount
                            </th>
                            <th className="text-left py-3 px-4 text-gray-600 font-semibold">
                              Status
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {royalties.entries.slice(0, 10).map(entry => (
                            <tr key={entry.id} className="border-b hover:bg-gray-50">
                              <td className="py-3 px-4">
                                {new Date(entry.timestamp).toLocaleDateString()}
                              </td>
                              <td className="py-3 px-4 font-semibold">
                                €{entry.amount.toFixed(2)}
                              </td>
                              <td className="py-3 px-4 text-gray-600">
                                €{entry.gross_amount.toFixed(2)}
                              </td>
                              <td className="py-3 px-4">
                                <span
                                  className={`px-3 py-1 rounded-full text-xs font-semibold ${
                                    entry.status === 'completed'
                                      ? 'bg-green-100 text-green-800'
                                      : 'bg-yellow-100 text-yellow-800'
                                  }`}
                                >
                                  {entry.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Monthly Breakdown */}
                <div className="bg-white rounded-lg shadow-lg p-8">
                  <h3 className="text-2xl font-bold text-gray-900 mb-6">Monthly Breakdown</h3>

                  <div className="grid grid-cols-3 gap-4">
                    {Object.entries(royalties.monthly_breakdown).map(([month, amount]) => (
                      <div key={month} className="bg-indigo-50 p-4 rounded-lg">
                        <p className="text-gray-600 text-sm font-semibold">{month}</p>
                        <p className="text-2xl font-bold text-indigo-600 mt-2">
                          €{(amount as number).toFixed(2)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Referral Earnings Section */}
                <ReferralEarningsDashboard creatorId={selectedCreator.id} />

                {/* Email Campaign Section */}
                <EmailCampaignDashboard creatorId={selectedCreator.id} />
              </>
            ) : (
              <div className="bg-white rounded-lg shadow-lg p-12 text-center">
                <p className="text-gray-500 text-lg">
                  {selectedCreator ? 'Loading royalty data...' : 'Select a creator to view details'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
