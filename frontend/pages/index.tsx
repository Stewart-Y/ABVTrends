import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { getTopTrends, TrendingProduct } from '@/services/api';

function TrendCard({ product }: { product: TrendingProduct }) {
  const tierColors = {
    viral: 'border-red-500 bg-red-50',
    trending: 'border-orange-500 bg-orange-50',
    emerging: 'border-yellow-500 bg-yellow-50',
    stable: 'border-green-500 bg-green-50',
    declining: 'border-gray-400 bg-gray-50',
  };

  const tierBadgeColors = {
    viral: 'bg-red-100 text-red-800',
    trending: 'bg-orange-100 text-orange-800',
    emerging: 'bg-yellow-100 text-yellow-800',
    stable: 'bg-green-100 text-green-800',
    declining: 'bg-gray-100 text-gray-800',
  };

  return (
    <Link href={`/product/${product.id}`}>
      <div
        className={`card p-4 hover:shadow-md transition-shadow cursor-pointer border-l-4 ${
          tierColors[product.trend_tier]
        }`}
      >
        <div className="flex justify-between items-start mb-2">
          <div>
            <h3 className="font-semibold text-gray-900 line-clamp-1">
              {product.name}
            </h3>
            {product.brand && (
              <p className="text-sm text-gray-500">{product.brand}</p>
            )}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">
              {product.trend_score.toFixed(0)}
            </div>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                tierBadgeColors[product.trend_tier]
              }`}
            >
              {product.trend_tier}
            </span>
          </div>
        </div>
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Component Breakdown</div>
          <div className="grid grid-cols-3 gap-1 text-xs">
            <div>
              <span className="text-gray-400">Media:</span>{' '}
              <span className="font-medium">
                {product.component_breakdown.media.toFixed(0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Retail:</span>{' '}
              <span className="font-medium">
                {product.component_breakdown.retailer.toFixed(0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Price:</span>{' '}
              <span className="font-medium">
                {product.component_breakdown.price.toFixed(0)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

function TrendSection({
  title,
  products,
  emptyMessage,
}: {
  title: string;
  products: TrendingProduct[];
  emptyMessage: string;
}) {
  return (
    <div className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-4">{title}</h2>
      {products.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product) => (
            <TrendCard key={product.id} product={product} />
          ))}
        </div>
      ) : (
        <p className="text-gray-500 italic">{emptyMessage}</p>
      )}
    </div>
  );
}

export default function Home() {
  const { data: topTrends, isLoading, error } = useQuery({
    queryKey: ['topTrends'],
    queryFn: getTopTrends,
    refetchInterval: 60000, // Refetch every minute
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-brand-600">ABVTrends</h1>
              <p className="text-sm text-gray-500">
                The Bloomberg Terminal for Alcohol Trends
              </p>
            </div>
            <nav className="flex space-x-4">
              <Link
                href="/"
                className="text-gray-900 font-medium hover:text-brand-600"
              >
                Dashboard
              </Link>
              <Link
                href="/trends"
                className="text-gray-500 hover:text-brand-600"
              >
                All Trends
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-600"></div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
            Error loading trends. Please try again later.
          </div>
        ) : (
          <>
            {/* Viral Section */}
            <TrendSection
              title="Viral Products (90+ Score)"
              products={topTrends?.viral || []}
              emptyMessage="No viral products at the moment"
            />

            {/* Trending Section */}
            <TrendSection
              title="Trending Products (70-89 Score)"
              products={topTrends?.trending || []}
              emptyMessage="No trending products at the moment"
            />

            {/* Emerging Section */}
            <TrendSection
              title="Emerging Products (50-69 Score)"
              products={topTrends?.emerging || []}
              emptyMessage="No emerging products at the moment"
            />
          </>
        )}

        {/* Last Updated */}
        {topTrends?.generated_at && (
          <p className="text-sm text-gray-400 text-center mt-8">
            Last updated:{' '}
            {new Date(topTrends.generated_at).toLocaleString()}
          </p>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-500 text-sm">
            ABVTrends - Alcohol Trend Intelligence Platform
          </p>
        </div>
      </footer>
    </div>
  );
}
