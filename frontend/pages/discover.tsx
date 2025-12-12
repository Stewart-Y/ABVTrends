'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getNewArrivals, getCelebrityBottles, getEarlyMovers, getDistributorArrivals, DiscoverProduct, DistributorArrival } from '@/services/api';
import { cn, getTierColor } from '@/lib/utils';

export default function DiscoverPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

  const { data: newArrivals, isLoading: loadingNew } = useQuery({
    queryKey: ['newArrivals'],
    queryFn: () => getNewArrivals(12),
  });

  const { data: celebrityBottles, isLoading: loadingCelebs } = useQuery({
    queryKey: ['celebrityBottles'],
    queryFn: () => getCelebrityBottles(12),
  });

  const { data: earlyMovers, isLoading: loadingEarly } = useQuery({
    queryKey: ['earlyMovers'],
    queryFn: () => getEarlyMovers(12),
  });

  const { data: distributorArrivals, isLoading: loadingArrivals } = useQuery({
    queryKey: ['distributorArrivals'],
    queryFn: () => getDistributorArrivals(7, 12),
  });

  if (!mounted) return null;

  return (
    <div className="flex min-h-screen bg-background" data-testid="discover-page">
      <Sidebar />

      <main className="flex-1 ml-64">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl" data-testid="discover-header">
          <div className="flex items-center justify-between px-8 py-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight" data-testid="discover-title">Discover</h1>
              <p className="text-muted-foreground mt-1">
                Explore curated collections and find your next opportunity
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-xs" data-testid="ai-curated-badge">
                <span className="mr-1.5">✨</span>
                AI-Curated
              </Badge>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-10">
          {/* New to ABVTrends Section */}
          <section className="animate-fade-in" style={{ animationDelay: '0ms' }} data-testid="new-arrivals-section">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="new-arrivals-title">
                  <span className="text-2xl">🆕</span>
                  New to ABVTrends
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Recently added products and emerging trends
                </p>
              </div>
            </div>

            {loadingNew ? (
              <div className="flex items-center justify-center h-64" data-testid="new-arrivals-loading">
                <div className="text-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                  <p className="text-muted-foreground">Loading new arrivals...</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="new-arrivals-grid">
                {newArrivals?.items?.map((product, idx) => (
                  <ProductCard key={product.id} product={product} index={idx} showNewBadge />
                ))}
              </div>
            )}

            {newArrivals?.items?.length === 0 && (
              <EmptyState
                emoji="🔍"
                title="No new products yet"
                description="Check back soon for the latest additions"
                testId="new-arrivals-empty"
              />
            )}
          </section>

          {/* Celebrity Bottles Section */}
          <section className="animate-fade-in" style={{ animationDelay: '100ms' }} data-testid="celebrity-section">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="celebrity-title">
                  <span className="text-2xl">⭐</span>
                  Celebrity Bottles
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Products with celebrity partnerships and affiliations
                </p>
              </div>
            </div>

            {loadingCelebs ? (
              <div className="flex items-center justify-center h-64" data-testid="celebrity-loading">
                <div className="text-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                  <p className="text-muted-foreground">Loading celebrity bottles...</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="celebrity-grid">
                {celebrityBottles?.items?.map((product, idx) => (
                  <ProductCard key={product.id} product={product} index={idx} showCelebrity />
                ))}
              </div>
            )}

            {celebrityBottles?.items?.length === 0 && (
              <EmptyState
                emoji="⭐"
                title="No celebrity bottles found"
                description="We're tracking celebrity partnerships. Check back soon!"
                testId="celebrity-empty"
              />
            )}
          </section>

          {/* Distributor Arrivals Section */}
          <section className="animate-fade-in" style={{ animationDelay: '200ms' }} data-testid="distributor-arrivals-section">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="distributor-arrivals-title">
                  <span className="text-2xl">📦</span>
                  New to Distributors
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Products recently added to distributor catalogs
                </p>
              </div>
            </div>

            {loadingArrivals ? (
              <div className="flex items-center justify-center h-64" data-testid="distributor-arrivals-loading">
                <div className="text-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                  <p className="text-muted-foreground">Loading distributor arrivals...</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="distributor-arrivals-grid">
                {distributorArrivals?.items?.map((arrival, idx) => (
                  <DistributorArrivalCard key={`${arrival.product_id}-${arrival.distributor}`} arrival={arrival} index={idx} />
                ))}
              </div>
            )}

            {distributorArrivals?.items?.length === 0 && (
              <EmptyState
                emoji="📦"
                title="No new distributor arrivals"
                description="We're monitoring distributor catalogs. Check back soon!"
                testId="distributor-arrivals-empty"
              />
            )}
          </section>

          {/* Early Movers Section */}
          <section className="animate-fade-in" style={{ animationDelay: '300ms' }} data-testid="early-movers-section">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-3" data-testid="early-movers-title">
                  <span className="text-2xl">🚀</span>
                  Early Movers
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Emerging products with high recent momentum
                </p>
              </div>
            </div>

            {loadingEarly ? (
              <div className="flex items-center justify-center h-64" data-testid="early-movers-loading">
                <div className="text-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                  <p className="text-muted-foreground">Loading early movers...</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="early-movers-grid">
                {earlyMovers?.items?.map((product, idx) => (
                  <ProductCard key={product.id} product={product} index={idx} showVelocity />
                ))}
              </div>
            )}

            {earlyMovers?.items?.length === 0 && (
              <EmptyState
                emoji="🚀"
                title="No early movers detected"
                description="We're monitoring emerging trends. Check back soon!"
                testId="early-movers-empty"
              />
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

// Product Card Component
function ProductCard({
  product,
  index,
  showNewBadge = false,
  showCelebrity = false,
  showVelocity = false,
}: {
  product: DiscoverProduct;
  index: number;
  showNewBadge?: boolean;
  showCelebrity?: boolean;
  showVelocity?: boolean;
}) {
  const tierColor = product.trend_tier ? getTierColor(product.trend_tier) : '#888';

  return (
    <Link href={`/product/${product.id}`}>
      <Card
        data-testid={`discover-product-${product.id}`}
        className="group hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10 cursor-pointer overflow-hidden animate-fade-in"
        style={{ animationDelay: `${index * 50}ms` }}
      >
        {/* Image */}
        <div className="relative aspect-square bg-muted/30 overflow-hidden">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="w-full h-full object-cover hover-rotate-3d"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center hover-rotate-3d">
              <span className="text-6xl opacity-20">
                {product.category === 'spirits' && '🥃'}
                {product.category === 'wine' && '🍷'}
                {product.category === 'beer' && '🍺'}
                {product.category === 'rtd' && '🥤'}
              </span>
            </div>
          )}

          {/* Overlay badges */}
          <div className="absolute top-3 right-3 flex flex-col gap-2">
            {showNewBadge && (
              <Badge className="bg-green-500/90 text-white border-0 backdrop-blur-sm">
                New
              </Badge>
            )}
            {product.trend_tier && (
              <Badge variant={product.trend_tier as any} className="backdrop-blur-sm">
                {product.trend_tier}
              </Badge>
            )}
          </div>
        </div>

        <CardContent className="p-5">
          {/* Product Info */}
          <div className="mb-4">
            <h3 className="font-semibold text-base group-hover:text-primary transition-colors line-clamp-2 mb-1">
              {product.name}
            </h3>
            {product.brand && (
              <p className="text-sm text-muted-foreground">{product.brand}</p>
            )}
          </div>

          {/* Score Bar */}
          {product.score !== null && product.score !== undefined && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">Trend Score</span>
                <span
                  className="text-sm font-bold tabular-nums"
                  style={{ color: tierColor }}
                >
                  {product.score.toFixed(0)}
                </span>
              </div>
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${product.score}%`,
                    backgroundColor: tierColor,
                  }}
                />
              </div>
            </div>
          )}

          {/* Celebrity Info */}
          {showCelebrity && product.celebrity_affiliation && (
            <div className="p-3 rounded-lg bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 mb-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">⭐</span>
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Celebrity
                </span>
              </div>
              <p className="text-sm font-medium text-foreground line-clamp-1">
                {product.celebrity_affiliation}
              </p>
            </div>
          )}

          {/* Velocity Indicator */}
          {showVelocity && product.recent_signal_count !== undefined && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>🔥</span>
              <span>{product.recent_signal_count} signals in last 7 days</span>
            </div>
          )}

          {/* Category */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground capitalize">
            <span>
              {product.category === 'spirits' && '🥃'}
              {product.category === 'wine' && '🍷'}
              {product.category === 'beer' && '🍺'}
              {product.category === 'rtd' && '🥤'}
            </span>
            <span>{product.category}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

// Distributor Arrival Card Component
function DistributorArrivalCard({
  arrival,
  index,
}: {
  arrival: DistributorArrival;
  index: number;
}) {
  const tierColor = arrival.tier ? getTierColor(arrival.tier) : '#888';

  return (
    <Link href={`/product/${arrival.product_id}`}>
      <Card
        data-testid={`distributor-arrival-${arrival.product_id}`}
        className="group hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10 cursor-pointer overflow-hidden animate-fade-in"
        style={{ animationDelay: `${index * 50}ms` }}
      >
        {/* Image */}
        <div className="relative aspect-square bg-muted/30 overflow-hidden">
          {arrival.image_url ? (
            <img
              src={arrival.image_url}
              alt={arrival.product_name}
              className="w-full h-full object-cover hover-rotate-3d"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center hover-rotate-3d">
              <span className="text-6xl opacity-20">
                {arrival.category === 'spirits' && '🥃'}
                {arrival.category === 'wine' && '🍷'}
                {arrival.category === 'beer' && '🍺'}
                {arrival.category === 'rtd' && '🥤'}
              </span>
            </div>
          )}

          {/* Overlay badges */}
          <div className="absolute top-3 right-3 flex flex-col gap-2">
            <Badge className="bg-blue-500/90 text-white border-0 backdrop-blur-sm">
              New Listing
            </Badge>
            {arrival.tier && (
              <Badge variant={arrival.tier as any} className="backdrop-blur-sm">
                {arrival.tier}
              </Badge>
            )}
          </div>
        </div>

        <CardContent className="p-5">
          {/* Product Info */}
          <div className="mb-4">
            <h3 className="font-semibold text-base group-hover:text-primary transition-colors line-clamp-2 mb-1">
              {arrival.product_name}
            </h3>
            {arrival.brand && (
              <p className="text-sm text-muted-foreground">{arrival.brand}</p>
            )}
          </div>

          {/* Score Bar */}
          {arrival.score !== null && arrival.score !== undefined && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">Trend Score</span>
                <span
                  className="text-sm font-bold tabular-nums"
                  style={{ color: tierColor }}
                >
                  {arrival.score.toFixed(0)}
                </span>
              </div>
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${arrival.score}%`,
                    backgroundColor: tierColor,
                  }}
                />
              </div>
            </div>
          )}

          {/* Distributor Info */}
          <div className="p-3 rounded-lg bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">📦</span>
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Distributor
              </span>
            </div>
            <p className="text-sm font-medium text-foreground">
              {arrival.distributor}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Added {new Date(arrival.added_at).toLocaleDateString()}
            </p>
          </div>

          {/* Category */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground capitalize">
            <span>
              {arrival.category === 'spirits' && '🥃'}
              {arrival.category === 'wine' && '🍷'}
              {arrival.category === 'beer' && '🍺'}
              {arrival.category === 'rtd' && '🥤'}
            </span>
            <span>{arrival.category}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

// Empty State Component
function EmptyState({
  emoji,
  title,
  description,
  testId,
}: {
  emoji: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div className="flex items-center justify-center h-64" data-testid={testId}>
      <div className="text-center">
        <span className="text-5xl mb-4 block">{emoji}</span>
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        <p className="text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
