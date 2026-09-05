'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

interface ReferralEarning {
  id: string;
  referred_creator_id: string;
  commission_tier: string;
  commission_earned: number;
}

interface ReferralEarningsData {
  referrer_id: string;
  total_commissions: number;
  total_referred_creators: number;
  referrals: ReferralEarning[];
}

export default function ReferralEarningsDashboard({
  creatorId
}: {
  creatorId: string;
}) {
  const [earnings, setEarnings] = useState<ReferralEarningsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEarnings = async () => {
      try {
        const response = await axios.get(
          `/api/referrals/earnings?referrer_id=${creatorId}`
        );
        setEarnings(response.data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch referral earnings');
      } finally {
        setLoading(false);
      }
    };

    if (creatorId) {
      fetchEarnings();
    }
  }, [creatorId]);

  if (loading) {
    return <div className="p-4">Loading referral earnings...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-600">Error: {error}</div>;
  }

  if (!earnings) {
    return <div className="p-4">No referral data available</div>;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-6">Referral Earnings</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="bg-blue-50 p-4 rounded">
          <div className="text-sm text-gray-600">Total Commission Earned</div>
          <div className="text-3xl font-bold text-blue-600">
            ${earnings.total_commissions.toFixed(2)}
          </div>
        </div>

        <div className="bg-green-50 p-4 rounded">
          <div className="text-sm text-gray-600">Referred Creators</div>
          <div className="text-3xl font-bold text-green-600">
            {earnings.total_referred_creators}
          </div>
        </div>
      </div>

      {earnings.referrals.length > 0 ? (
        <div>
          <h3 className="text-lg font-semibold mb-4">Your Referrals</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border p-3 text-left">Creator ID</th>
                  <th className="border p-3 text-left">Tier</th>
                  <th className="border p-3 text-right">Commission</th>
                </tr>
              </thead>
              <tbody>
                {earnings.referrals.map((referral) => (
                  <tr key={referral.id} className="hover:bg-gray-50">
                    <td className="border p-3 font-mono text-sm">
                      {referral.referred_creator_id.slice(0, 8)}...
                    </td>
                    <td className="border p-3">
                      <span className={`px-2 py-1 rounded text-sm ${
                        referral.commission_tier === 'tier_1'
                          ? 'bg-blue-100 text-blue-800'
                          : referral.commission_tier === 'tier_2'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {referral.commission_tier}
                      </span>
                    </td>
                    <td className="border p-3 text-right font-semibold">
                      ${referral.commission_earned.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center p-8 bg-gray-50 rounded">
          <p className="text-gray-600">No referrals yet. Share your referral link to earn commissions!</p>
        </div>
      )}
    </div>
  );
}
