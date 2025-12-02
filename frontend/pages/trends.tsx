import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { getTrendingProducts } from '@/services/api';

type CategoryFilter = 'all' | 'spirits' | 'wine' | 'rtd' | 'beer';
type TierFilter = 'all' | 'viral' | 'trending' | 'emerging' | 'stable' | 'declining';

const tierColors: Record<string, string> = {
  viral: 'bg-red-100 text-red-800',
  trending: 'bg-orange-100 text-orange-800',
  emerging: 'bg-yellow-100 text-yellow-800',
  stable: 'bg-green-100 text-green-800',
  declining: 'bg-gray-100 text-gray-800',
};

export default function TrendsExplorer() {
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [tier, setTier] = useState<TierFilter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ['allTrends', category, tier, page],
    queryFn: () =>
      getTrendingProducts({
        category: category === 'all' ? undefined : category,
        tier: tier === 'all' ? undefined : tier,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      }),
  });

  const filteredProducts = data?.items?.filter((item) =>
    search
      ? item.product.name.toLowerCase().includes(search.toLowerCase()) ||
        item.product.brand?.toLowerCase().includes(search.toLowerCase())
      : true
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
              <Link href="/" className="text-gray-500 hover:text-gray-900">
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                  />
                </svg>
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Trends Explorer
                </h1>
                <p className="text-gray-500">
                  Browse and filter all tracked products
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Filters */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="card p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <input
                type="text"
                placeholder="Search products..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              />
            </div>

            {/* Category Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value as CategoryFilter);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              >
                <option value="all">All Categories</option>
                <option value="spirits">Spirits</option>
                <option value="wine">Wine</option>
                <option value="rtd">RTD</option>
                <option value="beer">Beer</option>
              </select>
            </div>

            {/* Tier Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Trend Tier
              </label>
              <select
                value={tier}
                onChange={(e) => {
                  setTier(e.target.value as TierFilter);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              >
                <option value="all">All Tiers</option>
                <option value="viral">Viral (90+)</option>
                <option value="trending">Trending (70-89)</option>
                <option value="emerging">Emerging (50-69)</option>
                <option value="stable">Stable (30-49)</option>
                <option value="declining">Declining (&lt;30)</option>
              </select>
            </div>

            {/* Results count */}
            <div className="flex items-end">
              <p className="text-sm text-gray-500">
                {data?.total || 0} products found
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
        <div className="card overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-600"></div>
            </div>
          ) : (
            <>
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Product
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Category
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Score
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tier
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Signals
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Updated
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredProducts?.map((item) => (
                    <tr
                      key={item.product.id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() =>
                        (window.location.href = `/product/${item.product.id}`)
                      }
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {item.product.name}
                          </div>
                          {item.product.brand && (
                            <div className="text-sm text-gray-500">
                              {item.product.brand}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-gray-500 capitalize">
                          {item.product.category}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                            <div
                              className="h-2 rounded-full bg-brand-500"
                              style={{ width: `${item.score}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium text-gray-900">
                            {item.score.toFixed(0)}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded-full capitalize ${
                            tierColors[item.trend_tier] || tierColors.stable
                          }`}
                        >
                          {item.trend_tier}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item.signal_count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(item.calculated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {data?.total && data.total > pageSize && (
                <div className="bg-white px-4 py-3 border-t border-gray-200 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-700">
                      Showing{' '}
                      <span className="font-medium">
                        {(page - 1) * pageSize + 1}
                      </span>{' '}
                      to{' '}
                      <span className="font-medium">
                        {Math.min(page * pageSize, data.total)}
                      </span>{' '}
                      of <span className="font-medium">{data.total}</span>{' '}
                      results
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-3 py-1 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      >
                        Previous
                      </button>
                      <button
                        onClick={() => setPage((p) => p + 1)}
                        disabled={page * pageSize >= data.total}
                        className="px-3 py-1 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
