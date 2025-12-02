import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/router';
import Link from 'next/link';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import {
  getProduct,
  getProductTrend,
  getTrendHistory,
  getProductForecast,
} from '@/services/api';

function ScoreGauge({ score, tier }: { score: number; tier: string }) {
  const tierColors = {
    viral: '#ef4444',
    trending: '#f97316',
    emerging: '#eab308',
    stable: '#22c55e',
    declining: '#6b7280',
  };

  const color = tierColors[tier as keyof typeof tierColors] || '#6b7280';
  const percentage = score / 100;
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference * (1 - percentage);

  return (
    <div className="relative w-32 h-32">
      <svg className="w-full h-full transform -rotate-90">
        <circle
          cx="64"
          cy="64"
          r="45"
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="10"
        />
        <circle
          cx="64"
          cy="64"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-gray-900">
          {score.toFixed(0)}
        </span>
        <span
          className="text-sm font-medium capitalize"
          style={{ color }}
        >
          {tier}
        </span>
      </div>
    </div>
  );
}

function ComponentBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">{value.toFixed(0)}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${value}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function ProductDetail() {
  const router = useRouter();
  const { id } = router.query;

  const productId = id as string;

  const { data: product, isLoading: productLoading } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => getProduct(productId),
    enabled: !!productId,
  });

  const { data: trend, isLoading: trendLoading } = useQuery({
    queryKey: ['productTrend', productId],
    queryFn: () => getProductTrend(productId),
    enabled: !!productId,
  });

  const { data: history } = useQuery({
    queryKey: ['trendHistory', productId],
    queryFn: () => getTrendHistory(productId, 30),
    enabled: !!productId,
  });

  const { data: forecast } = useQuery({
    queryKey: ['forecast', productId],
    queryFn: () => getProductForecast(productId),
    enabled: !!productId,
  });

  if (productLoading || trendLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-600"></div>
      </div>
    );
  }

  if (!product || !trend) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900">
            Product not found
          </h2>
          <Link href="/" className="text-brand-600 hover:underline mt-2 block">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  // Prepare chart data
  const historyData =
    history?.scores?.map((s) => ({
      date: new Date(s.calculated_at).toLocaleDateString(),
      score: s.score,
    })) || [];

  const forecastData =
    forecast?.forecasts?.map((f) => ({
      date: new Date(f.forecast_date).toLocaleDateString(),
      predicted: f.predicted_score,
      lower: f.confidence_lower_80,
      upper: f.confidence_upper_80,
    })) || [];

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
                  {product.name}
                </h1>
                {product.brand && (
                  <p className="text-gray-500">{product.brand}</p>
                )}
              </div>
            </div>
            <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm capitalize">
              {product.category}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Score Card */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Current Trend Score
            </h2>
            <div className="flex flex-col items-center">
              <ScoreGauge score={trend.score} tier={trend.trend_tier} />
              <p className="text-sm text-gray-500 mt-4">
                Based on {trend.signal_count} signals
              </p>
            </div>
          </div>

          {/* Component Breakdown */}
          <div className="card p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Score Components
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <ComponentBar
                  label="Media Mentions"
                  value={trend.media_score}
                  color="#3b82f6"
                />
                <ComponentBar
                  label="Social Velocity"
                  value={trend.social_score}
                  color="#8b5cf6"
                />
                <ComponentBar
                  label="Retailer Presence"
                  value={trend.retailer_score}
                  color="#10b981"
                />
              </div>
              <div>
                <ComponentBar
                  label="Price Movement"
                  value={trend.price_score}
                  color="#f59e0b"
                />
                <ComponentBar
                  label="Search Interest"
                  value={trend.search_score}
                  color="#ef4444"
                />
                <ComponentBar
                  label="Seasonal Alignment"
                  value={trend.seasonal_score}
                  color="#06b6d4"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
          {/* History Chart */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Score History (30 Days)
            </h2>
            {historyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={historyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#de5a4a"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500 italic">No history data available</p>
            )}
          </div>

          {/* Forecast Chart */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              7-Day Forecast
            </h2>
            {forecastData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="lower"
                    stackId="1"
                    stroke="none"
                    fill="#fef3c7"
                  />
                  <Area
                    type="monotone"
                    dataKey="upper"
                    stackId="2"
                    stroke="none"
                    fill="#fef3c7"
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={true}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500 italic">No forecast available</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
