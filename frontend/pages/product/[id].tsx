'use client';

import { useEffect, useState } from 'react';
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
  AreaChart,
  Area,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import { Sidebar } from '@/components/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScoreGauge } from '@/components/ui/ScoreGauge';
import {
  getProduct,
  getProductTrend,
  getTrendHistory,
  getProductForecast,
  getProductTrendSummary,
  TrendSummary,
} from '@/services/api';
import { DistributorAvailabilityCard, PriceHistoryChart } from '@/components/distributor';
import { cn, getTierColor } from '@/lib/utils';

function ComponentBar({
  label,
  value,
  color,
  icon,
  delay = 0,
}: {
  label: string;
  value: number;
  color: string;
  icon: string;
  delay?: number;
}) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setWidth(value), delay + 100);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return (
    <div className="group p-4 rounded-xl bg-card/50 border border-border/50 hover:border-primary/30 transition-all duration-300">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <span className="text-sm font-medium text-foreground">{label}</span>
        </div>
        <span className="text-lg font-bold tabular-nums" style={{ color }}>
          {value.toFixed(0)}
        </span>
      </div>
      <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{
            width: `${width}%`,
            backgroundColor: color,
            boxShadow: `0 0 10px ${color}50`,
          }}
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  change,
  icon,
  delay = 0,
}: {
  label: string;
  value: string | number;
  change?: number;
  icon: string;
  delay?: number;
}) {
  return (
    <div
      className="p-4 rounded-xl bg-gradient-to-br from-card to-card/80 border border-border/50 hover:border-primary/30 transition-all duration-300 animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-xs text-muted-foreground uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-foreground">{value}</span>
        {change !== undefined && (
          <span className={cn(
            "text-xs font-medium flex items-center gap-0.5",
            change >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {change >= 0 ? '↑' : '↓'}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card/95 backdrop-blur-xl border border-border rounded-lg p-3 shadow-xl">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
            {entry.name}: {entry.value?.toFixed(1)}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function ProductDetail() {
  const router = useRouter();
  const { id } = router.query;
  const productId = id as string;

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

  const { data: product, isLoading: productLoading } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => getProduct(productId),
    enabled: !!productId,
  });

  const { data: trend, isLoading: trendLoading } = useQuery({
    queryKey: ['productTrend', productId],
    queryFn: () => getProductTrend(productId).catch(() => null),
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

  const { data: trendSummary } = useQuery({
    queryKey: ['trendSummary', productId],
    queryFn: () => getProductTrendSummary(productId),
    enabled: !!productId,
  });

  if (!mounted) return null;

  if (productLoading || trendLoading) {
    return (
      <div className="flex min-h-screen bg-background" data-testid="product-detail-page">
        <Sidebar />
        <main className="flex-1 ml-64 flex items-center justify-center">
          <div className="text-center" data-testid="product-loading">
            <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
            <p className="text-muted-foreground">Loading product data...</p>
          </div>
        </main>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="flex min-h-screen bg-background" data-testid="product-detail-page">
        <Sidebar />
        <main className="flex-1 ml-64 flex items-center justify-center">
          <Card className="p-8 text-center" data-testid="product-not-found">
            <div className="text-5xl mb-4">🔍</div>
            <h2 className="text-xl font-semibold mb-2">Product not found</h2>
            <p className="text-muted-foreground mb-4">
              The product you're looking for doesn't exist or has been removed.
            </p>
            <Link href="/">
              <Button data-testid="return-dashboard-button">Return to Dashboard</Button>
            </Link>
          </Card>
        </main>
      </div>
    );
  }

  // Create a placeholder trend for products without trend scores
  const displayTrend = trend || {
    score: 0,
    trend_tier: 'emerging',
    media_score: 0,
    social_score: 0,
    retailer_score: 0,
    price_score: 0,
    search_score: 0,
    seasonal_score: 0,
    signal_count: 0,
    calculated_at: new Date().toISOString(),
    score_change_24h: null,
  };

  const hasTrendData = !!trend;
  const tierColor = getTierColor(displayTrend.trend_tier);

  // Prepare chart data
  const historyData =
    history?.scores?.map((s: any) => ({
      date: new Date(s.calculated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      score: s.score,
    })) || [];

  const forecastData =
    forecast?.forecasts?.map((f: any) => ({
      date: new Date(f.forecast_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      predicted: f.predicted_score,
      lower: f.confidence_lower_80,
      upper: f.confidence_upper_80,
    })) || [];

  // Radar chart data for component breakdown
  const radarData = [
    { subject: 'Media', value: displayTrend.media_score, fullMark: 100 },
    { subject: 'Social', value: displayTrend.social_score, fullMark: 100 },
    { subject: 'Retail', value: displayTrend.retailer_score, fullMark: 100 },
    { subject: 'Price', value: displayTrend.price_score, fullMark: 100 },
    { subject: 'Search', value: displayTrend.search_score, fullMark: 100 },
    { subject: 'Seasonal', value: displayTrend.seasonal_score, fullMark: 100 },
  ];

  return (
    <div className="flex min-h-screen bg-background" data-testid="product-detail-page">
      <Sidebar />

      <main className="flex-1 ml-64">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl" data-testid="product-header">
          <div className="flex items-center justify-between px-8 py-6">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="ghost" size="icon" className="rounded-full" data-testid="back-button">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                </Button>
              </Link>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold" data-testid="product-name">{product.name}</h1>
                  <Badge variant={displayTrend.trend_tier as any} data-testid="product-tier-badge">
                    {hasTrendData ? displayTrend.trend_tier : 'new'}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mt-1" data-testid="product-meta">
                  {product.brand && (
                    <span className="text-muted-foreground" data-testid="product-brand">{product.brand}</span>
                  )}
                  <span className="text-muted-foreground">•</span>
                  <span className="text-muted-foreground capitalize" data-testid="product-category">{product.category}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" disabled className="opacity-50 cursor-not-allowed" data-testid="export-button" title="Export coming soon">
                <span className="mr-2">📤</span>
                Export
              </Button>
              <Button variant="outline" disabled className="opacity-50 cursor-not-allowed" data-testid="set-alert-button" title="Alerts coming soon">
                <span className="mr-2">🔔</span>
                Set Alert
              </Button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-8">
          {/* Hero Section - Score Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" data-testid="score-overview-section">
            {/* Main Score Card */}
            <Card className="lg:col-span-1 overflow-hidden" data-testid="score-gauge-card">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent" />
              <CardContent className="p-8 relative">
                <div className="flex flex-col items-center" data-testid="score-gauge">
                  <ScoreGauge score={displayTrend.score} tier={displayTrend.trend_tier} size="lg" animated />
                  <div className="mt-6 text-center" data-testid="score-meta">
                    {hasTrendData ? (
                      <>
                        <p className="text-sm text-muted-foreground">
                          Based on <span className="text-foreground font-medium" data-testid="signal-count">{displayTrend.signal_count}</span> signals
                        </p>
                        <p className="text-xs text-muted-foreground mt-1" data-testid="last-updated">
                          Last updated: {new Date(displayTrend.calculated_at).toLocaleString()}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No trend data yet - collecting signals...
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Key Metrics */}
            <Card className="lg:col-span-2" data-testid="key-metrics-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">📊</span>
                  Key Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="metrics-grid">
                  <MetricCard
                    label="Trend Score"
                    value={displayTrend.score.toFixed(0)}
                    change={displayTrend.score_change_24h}
                    icon="📈"
                    delay={0}
                  />
                  <MetricCard
                    label="Signal Count"
                    value={displayTrend.signal_count}
                    icon="📡"
                    delay={100}
                  />
                  <MetricCard
                    label="Media Score"
                    value={displayTrend.media_score.toFixed(0)}
                    icon="📰"
                    delay={200}
                  />
                  <MetricCard
                    label="Social Score"
                    value={displayTrend.social_score.toFixed(0)}
                    icon="💬"
                    delay={300}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* AI Trend Summary */}
          {trendSummary && (
            <Card className="overflow-hidden border-primary/20 animate-fade-in" data-testid="ai-summary-card">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-blue-500/5" />
              <CardHeader className="relative">
                <CardTitle className="flex items-center gap-3">
                  <span className="text-2xl">🧠</span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span>Why This Is Trending</span>
                      <Badge variant="outline" className="text-xs font-normal" data-testid="ai-powered-badge">
                        AI-Powered
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground font-normal mt-1">
                      Intelligent summary based on {trendSummary.signal_count} trend signals
                    </p>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="relative space-y-6">
                {/* Main Summary */}
                <div className="p-6 rounded-xl bg-gradient-to-br from-card/80 to-card/60 border border-border/50" data-testid="ai-summary-text">
                  <p className="text-base leading-relaxed text-foreground">
                    {trendSummary.summary}
                  </p>
                </div>

                {/* Key Insights Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="key-insights-grid">
                  {/* Key Points */}
                  <div className="p-5 rounded-xl bg-card/50 border border-border/30" data-testid="key-points-section">
                    <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                      <span>✨</span>
                      Key Points
                    </h4>
                    <ul className="space-y-2" data-testid="key-points-list">
                      {trendSummary.key_points.map((point, idx) => (
                        <li
                          key={idx}
                          className="flex items-start gap-2 text-sm text-foreground animate-fade-in"
                          style={{ animationDelay: `${idx * 100}ms` }}
                          data-testid={`key-point-${idx}`}
                        >
                          <span className="text-primary mt-0.5">▸</span>
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Trend Metrics */}
                  <div className="space-y-3" data-testid="trend-metrics-section">
                    {trendSummary.celebrity_affiliation && (
                      <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20" data-testid="celebrity-affiliation">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg">⭐</span>
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Celebrity Partnership
                          </span>
                        </div>
                        <p className="text-sm font-medium text-foreground">
                          {trendSummary.celebrity_affiliation}
                        </p>
                      </div>
                    )}

                    <div className="p-4 rounded-xl bg-card/50 border border-border/30" data-testid="trend-driver">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">🎯</span>
                        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Trend Driver
                        </span>
                      </div>
                      <p className="text-sm font-medium text-foreground capitalize">
                        {trendSummary.trend_driver.replace('_', ' ')}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-4 rounded-xl bg-card/50 border border-border/30" data-testid="days-active">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-base">📅</span>
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Active Days
                          </span>
                        </div>
                        <p className="text-lg font-bold text-foreground tabular-nums">
                          {trendSummary.days_active}
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-card/50 border border-border/30" data-testid="sources-count">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-base">📰</span>
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Sources
                          </span>
                        </div>
                        <p className="text-lg font-bold text-foreground tabular-nums">
                          {trendSummary.sources_count}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Component Breakdown Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="component-breakdown-section">
            {/* Radar Chart */}
            <Card data-testid="radar-chart-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">🎯</span>
                  Score Components
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="hsl(var(--border))" />
                    <PolarAngleAxis
                      dataKey="subject"
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                    />
                    <PolarRadiusAxis
                      angle={90}
                      domain={[0, 100]}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                    />
                    <Radar
                      name="Score"
                      dataKey="value"
                      stroke={tierColor}
                      fill={tierColor}
                      fillOpacity={0.3}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Component Bars */}
            <Card data-testid="breakdown-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">📋</span>
                  Detailed Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3" data-testid="component-bars">
                <ComponentBar
                  label="Media Mentions"
                  value={displayTrend.media_score}
                  color="#3b82f6"
                  icon="📰"
                  delay={0}
                />
                <ComponentBar
                  label="Social Velocity"
                  value={displayTrend.social_score}
                  color="#8b5cf6"
                  icon="💬"
                  delay={100}
                />
                <ComponentBar
                  label="Retailer Presence"
                  value={displayTrend.retailer_score}
                  color="#10b981"
                  icon="🏪"
                  delay={200}
                />
                <ComponentBar
                  label="Price Movement"
                  value={displayTrend.price_score}
                  color="#f59e0b"
                  icon="💰"
                  delay={300}
                />
                <ComponentBar
                  label="Search Interest"
                  value={displayTrend.search_score}
                  color="#ef4444"
                  icon="🔍"
                  delay={400}
                />
                <ComponentBar
                  label="Seasonal Alignment"
                  value={displayTrend.seasonal_score}
                  color="#06b6d4"
                  icon="📅"
                  delay={500}
                />
              </CardContent>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="charts-section">
            {/* History Chart */}
            <Card data-testid="history-chart-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">📉</span>
                  Score History (30 Days)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {historyData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={historyData}>
                      <defs>
                        <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={tierColor} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={tierColor} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        axisLine={{ stroke: 'hsl(var(--border))' }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        axisLine={{ stroke: 'hsl(var(--border))' }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="score"
                        stroke={tierColor}
                        strokeWidth={2}
                        fill="url(#scoreGradient)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[280px] flex items-center justify-center" data-testid="history-empty">
                    <div className="text-center">
                      <span className="text-4xl mb-2 block">📊</span>
                      <p className="text-muted-foreground">No history data available yet</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Forecast Chart */}
            <Card data-testid="forecast-chart-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">🔮</span>
                  7-Day Forecast
                </CardTitle>
              </CardHeader>
              <CardContent>
                {forecastData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={forecastData}>
                      <defs>
                        <linearGradient id="confidenceGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        axisLine={{ stroke: 'hsl(var(--border))' }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        axisLine={{ stroke: 'hsl(var(--border))' }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="lower"
                        stackId="1"
                        stroke="none"
                        fill="url(#confidenceGradient)"
                        name="Lower bound"
                      />
                      <Area
                        type="monotone"
                        dataKey="upper"
                        stackId="2"
                        stroke="none"
                        fill="url(#confidenceGradient)"
                        name="Upper bound"
                      />
                      <Line
                        type="monotone"
                        dataKey="predicted"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        dot={{ fill: '#f59e0b', strokeWidth: 0, r: 4 }}
                        name="Predicted"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[280px] flex items-center justify-center" data-testid="forecast-empty">
                    <div className="text-center">
                      <span className="text-4xl mb-2 block">🔮</span>
                      <p className="text-muted-foreground">Forecast data coming soon</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Distributor Data Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="distributor-section">
            {/* Distributor Availability */}
            <DistributorAvailabilityCard productId={productId} />

            {/* Price History Chart */}
            <PriceHistoryChart productId={productId} />
          </div>

          {/* Additional Info */}
          <Card data-testid="product-info-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="text-xl">ℹ️</span>
                Product Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6" data-testid="product-info-grid">
                <div data-testid="info-category">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Category</p>
                  <p className="text-lg font-medium capitalize">{product.category}</p>
                </div>
                <div data-testid="info-brand">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Brand</p>
                  <p className="text-lg font-medium">{product.brand || 'N/A'}</p>
                </div>
                <div data-testid="info-first-tracked">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">First Tracked</p>
                  <p className="text-lg font-medium">
                    {new Date(product.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div data-testid="info-status">
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Status</p>
                  <Badge variant={displayTrend.trend_tier as any} className="mt-1">
                    {hasTrendData ? displayTrend.trend_tier : 'new'}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
