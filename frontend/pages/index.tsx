import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { StatCard } from '@/components/StatCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getTopTrends, getRecentSignals, TrendingProduct, Signal } from '@/services/api';
import { cn } from '@/lib/utils';

function TrendCard({ product, index }: { product: TrendingProduct; index: number }) {
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-red-400';
    if (score >= 70) return 'text-orange-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-green-400';
  };

  const getScoreGradient = (score: number) => {
    if (score >= 90) return 'from-red-500/20 to-red-600/20';
    if (score >= 70) return 'from-orange-500/20 to-orange-600/20';
    if (score >= 50) return 'from-yellow-500/20 to-yellow-600/20';
    return 'from-green-500/20 to-green-600/20';
  };

  return (
    <Link href={`/product/${product.id}`}>
      <Card
        data-testid={`trend-card-${product.id}`}
        className={cn(
          "group cursor-pointer overflow-hidden hover-lift",
          "hover:border-primary/50",
          "animate-fade-in",
          `animation-delay-${Math.min(index * 100, 500)}`
        )}
      >
        {/* Gradient overlay on hover */}
        <div className={cn(
          "absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity duration-300",
          getScoreGradient(product.trend_score)
        )} />

        <CardContent className="p-6 relative z-10">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg mb-1 truncate group-hover:text-primary transition-colors">
                {product.name}
              </h3>
              {product.brand && (
                <p className="text-sm text-muted-foreground">{product.brand}</p>
              )}
              <div className="flex items-center gap-2 mt-2">
                <Badge variant={product.trend_tier as any}>
                  {product.trend_tier}
                </Badge>
                <span className="text-xs text-muted-foreground capitalize">
                  {product.category}
                </span>
              </div>
            </div>

            {/* Score indicator */}
            <div className="text-right ml-4">
              <div className={cn(
                "text-4xl font-bold tabular-nums transition-colors",
                getScoreColor(product.trend_score)
              )}>
                {product.trend_score.toFixed(0)}
              </div>
              {product.score_change_24h && (
                <div className={cn(
                  "text-xs font-medium mt-1 flex items-center justify-end gap-0.5",
                  product.score_change_24h > 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  <span className={cn(
                    Math.abs(product.score_change_24h) > 5 && 'pulse-glow'
                  )}>
                    {product.score_change_24h > 0 ? '↑' : '↓'}
                  </span>
                  {Math.abs(product.score_change_24h).toFixed(1)}%
                </div>
              )}
            </div>
          </div>

          {/* Mini component bars */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Components</span>
              <span className="text-muted-foreground">Score</span>
            </div>
            {Object.entries({
              Media: product.component_breakdown.media,
              Social: product.component_breakdown.social,
              Retail: product.component_breakdown.retailer,
            }).map(([key, value]) => (
              <div key={key} className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-12">{key}</span>
                <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary to-primary/80 rounded-full transition-all duration-500"
                    style={{ width: `${value}%` }}
                  />
                </div>
                <span className="text-xs font-medium w-8 text-right">{value.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['topTrends'],
    queryFn: getTopTrends,
  });

  const { data: signalsData } = useQuery({
    queryKey: ['recentSignals'],
    queryFn: () => getRecentSignals(15),
  });

  const totalProducts = (data?.viral.length || 0) + (data?.trending.length || 0) + (data?.emerging.length || 0);
  const avgScore = data ?
    ([...data.viral, ...data.trending, ...data.emerging].reduce((acc, p) => acc + p.trend_score, 0) / totalProducts) : 0;

  const signalCount = signalsData?.data?.length || 0;

  return (
    <div className="flex min-h-screen bg-background" data-testid="dashboard-page">
      <Sidebar />

      <main className="flex-1 ml-64">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl" data-testid="dashboard-header">
          <div className="flex items-center justify-between px-8 py-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight" data-testid="dashboard-title">Dashboard</h1>
              <p className="text-muted-foreground mt-1">
                {totalProducts > 0 ? 'Real-time alcohol trend analytics powered by AI' : 'Collecting data from media sources...'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/>
                </svg>
              </Button>
              <Button variant="ghost" size="icon">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                </svg>
              </Button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-8">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" data-testid="kpi-cards-grid">
            {totalProducts > 0 ? (
              <>
                <StatCard
                  title="Total Products"
                  value={totalProducts}
                  change={12.5}
                  iconPath="M20 6h-2.18c.11-.31.18-.65.18-1a2.996 2.996 0 0 0-5.5-1.65l-.5.67-.5-.68C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-5-2c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM9 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm11 15H4v-2h16v2zm0-5H4V8h5.08L7 10.83 8.62 12 11 8.76l1-1.36 1 1.36L15.38 12 17 10.83 14.92 8H20v6z"
                  trend="up"
                  delay={0}
                />
                <StatCard
                  title="Viral Products"
                  value={data?.viral.length || 0}
                  change={8.2}
                  iconPath="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"
                  trend="up"
                  delay={100}
                />
                <StatCard
                  title="Avg Trend Score"
                  value={avgScore.toFixed(1)}
                  change={-2.1}
                  iconPath="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"
                  trend="down"
                  delay={200}
                />
                <StatCard
                  title="New This Week"
                  value={data?.emerging.length || 0}
                  change={15.3}
                  iconPath="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"
                  trend="up"
                  delay={300}
                />
              </>
            ) : (
              <>
                <StatCard
                  title="Signals Collected"
                  value={signalCount}
                  change={100}
                  iconPath="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"
                  trend="up"
                  delay={0}
                />
                <StatCard
                  title="Media Sources"
                  value={1}
                  change={0}
                  iconPath="M20 6h-2.18c.11-.31.18-.65.18-1a2.996 2.996 0 0 0-5.5-1.65l-.5.67-.5-.68C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-5-2c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM9 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm11 15H4v-2h16v2zm0-5H4V8h5.08L7 10.83 8.62 12 11 8.76l1-1.36 1 1.36L15.38 12 17 10.83 14.92 8H20v6z"
                  trend="up"
                  delay={100}
                />
                <StatCard
                  title="Products Identified"
                  value={0}
                  change={0}
                  iconPath="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"
                  trend="up"
                  delay={200}
                />
                <StatCard
                  title="Active Today"
                  value={signalCount}
                  change={100}
                  iconPath="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"
                  trend="up"
                  delay={300}
                />
              </>
            )}
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center h-64" data-testid="dashboard-loading">
              <div className="text-center">
                <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                <p className="text-muted-foreground">Loading trends...</p>
              </div>
            </div>
          )}

          {/* Viral Products */}
          {!isLoading && data && data.viral.length > 0 && (
            <div className="space-y-4" data-testid="viral-section">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="viral-section-title">
                    <svg className="w-8 h-8 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"/>
                    </svg>
                    Viral Products
                  </h2>
                  <p className="text-muted-foreground mt-1">Score 90+ • Explosive growth</p>
                </div>
                <Link href="/trends?tier=viral">
                  <Button variant="ghost">
                    View all
                    <span className="ml-2">→</span>
                  </Button>
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="viral-products-grid">
                {data.viral.map((product, index) => (
                  <TrendCard key={product.id} product={product} index={index} />
                ))}
              </div>
            </div>
          )}

          {/* Trending Products */}
          {!isLoading && data && data.trending.length > 0 && (
            <div className="space-y-4" data-testid="trending-section">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="trending-section-title">
                    <svg className="w-8 h-8 text-orange-400" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/>
                    </svg>
                    Trending Products
                  </h2>
                  <p className="text-muted-foreground mt-1">Score 70-89 • Strong momentum</p>
                </div>
                <Link href="/trends?tier=trending">
                  <Button variant="ghost">
                    View all
                    <span className="ml-2">→</span>
                  </Button>
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="trending-products-grid">
                {data.trending.slice(0, 6).map((product, index) => (
                  <TrendCard key={product.id} product={product} index={index} />
                ))}
              </div>
            </div>
          )}

          {/* Emerging Products */}
          {!isLoading && data && data.emerging.length > 0 && (
            <div className="space-y-4" data-testid="emerging-section">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="emerging-section-title">
                    <svg className="w-8 h-8 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                    </svg>
                    Emerging Products
                  </h2>
                  <p className="text-muted-foreground mt-1">Score 50-69 • Watch closely</p>
                </div>
                <Link href="/trends?tier=emerging">
                  <Button variant="ghost">
                    View all
                    <span className="ml-2">→</span>
                  </Button>
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="emerging-products-grid">
                {data.emerging.slice(0, 6).map((product, index) => (
                  <TrendCard key={product.id} product={product} index={index} />
                ))}
              </div>
            </div>
          )}

          {/* Recent Activity - show when no products */}
          {!isLoading && totalProducts === 0 && signalsData?.data && (
            <div className="space-y-4" data-testid="recent-activity-section">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="recent-activity-title">
                    <svg className="w-8 h-8 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                    </svg>
                    Recent Activity
                  </h2>
                  <p className="text-muted-foreground mt-1">Latest mentions from media sources</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="recent-activity-grid">
                {signalsData.data.map((signal: Signal) => (
                  <Card key={signal.id} data-testid={`signal-card-${signal.id}`} className="group hover:border-primary/50 hover:shadow-glow-sm transition-all">
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        {signal.raw_data?.image_url && (
                          <img
                            src={signal.raw_data.image_url}
                            alt={signal.title}
                            className="w-16 h-16 rounded object-cover flex-shrink-0"
                          />
                        )}
                        <div className="flex-1 min-w-0">
                          <a href={signal.url} target="_blank" rel="noopener noreferrer" className="block">
                            <h3 className="font-medium text-sm mb-1 line-clamp-2 group-hover:text-primary transition-colors">
                              {signal.title}
                            </h3>
                          </a>
                          {signal.raw_data?.excerpt && (
                            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                              {signal.raw_data.excerpt}
                            </p>
                          )}
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Badge variant="outline" className="text-xs">
                              {signal.raw_data?.source || 'Media'}
                            </Badge>
                            <span>•</span>
                            <span>{new Date(signal.captured_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
