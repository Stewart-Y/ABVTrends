'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Layout } from '@/components/Layout';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getTrendingProducts } from '@/services/api';
import { cn, getTierColor } from '@/lib/utils';

type CategoryFilter = 'all' | 'spirits' | 'wine' | 'rtd' | 'beer';
type TierFilter = 'all' | 'viral' | 'trending' | 'emerging' | 'stable' | 'declining';

export default function TrendsExplorer() {
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [tier, setTier] = useState<TierFilter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [mounted, setMounted] = useState(false);
  const pageSize = 20;

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

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
      ? item.name.toLowerCase().includes(search.toLowerCase()) ||
        item.brand?.toLowerCase().includes(search.toLowerCase())
      : true
  );

  if (!mounted) return null;

  const headerActions = (
    <Button variant="outline" size="sm" data-testid="export-button" className="hidden sm:flex">
      <span className="mr-2">📤</span>
      Export
    </Button>
  );

  return (
    <Layout
      title="Trends Explorer"
      subtitle="Browse and filter all tracked products"
      headerActions={headerActions}
      testId="trends-page"
    >
      <div className="space-y-4 sm:space-y-6" data-testid="trends-header">
          {/* Filters */}
          <Card data-testid="trends-filters">
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                {/* Search */}
                <div className="sm:col-span-2 lg:col-span-1">
                  <label className="block text-xs sm:text-sm font-medium text-muted-foreground mb-1.5 sm:mb-2">
                    Search
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                      🔍
                    </span>
                    <input
                      type="text"
                      placeholder="Search products..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      data-testid="search-input"
                      className="w-full pl-9 sm:pl-10 pr-3 sm:pr-4 py-2 sm:py-2.5 text-sm bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-colors"
                    />
                  </div>
                </div>

                {/* Category Filter */}
                <div>
                  <label className="block text-xs sm:text-sm font-medium text-muted-foreground mb-1.5 sm:mb-2">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => {
                      setCategory(e.target.value as CategoryFilter);
                      setPage(1);
                    }}
                    data-testid="category-filter"
                    className="w-full px-3 sm:px-4 py-2 sm:py-2.5 text-sm bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-colors cursor-pointer"
                  >
                    <option value="all">All Categories</option>
                    <option value="spirits">🥃 Spirits</option>
                    <option value="wine">🍷 Wine</option>
                    <option value="rtd">🥤 RTD</option>
                    <option value="beer">🍺 Beer</option>
                  </select>
                </div>

                {/* Tier Filter */}
                <div>
                  <label className="block text-xs sm:text-sm font-medium text-muted-foreground mb-1.5 sm:mb-2">
                    Trend Tier
                  </label>
                  <select
                    value={tier}
                    onChange={(e) => {
                      setTier(e.target.value as TierFilter);
                      setPage(1);
                    }}
                    data-testid="tier-filter"
                    className="w-full px-3 sm:px-4 py-2 sm:py-2.5 text-sm bg-background border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-colors cursor-pointer"
                  >
                    <option value="all">All Tiers</option>
                    <option value="viral">🔥 Viral (90+)</option>
                    <option value="trending">📈 Trending (70-89)</option>
                    <option value="emerging">✨ Emerging (50-69)</option>
                    <option value="stable">📊 Stable (30-49)</option>
                    <option value="declining">📉 Declining (&lt;30)</option>
                  </select>
                </div>

                {/* Results count */}
                <div className="flex items-end sm:col-span-2 lg:col-span-1">
                  <div className="w-full p-2.5 sm:p-3 rounded-lg bg-primary/10 border border-primary/20" data-testid="results-count">
                    <p className="text-xs sm:text-sm text-muted-foreground">
                      <span className="text-xl sm:text-2xl font-bold text-primary mr-1.5 sm:mr-2">
                        {data?.meta?.total || data?.items?.length || 0}
                      </span>
                      products found
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Results Table */}
          <Card className="overflow-hidden" data-testid="trends-table">
            {isLoading ? (
              <div className="flex items-center justify-center h-64" data-testid="trends-loading">
                <div className="text-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
                  <p className="text-muted-foreground">Loading trends...</p>
                </div>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead data-testid="trends-table-header">
                      <tr className="border-b border-border bg-muted/30">
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Product
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Category
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Score
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Tier
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          Signals
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          24h Change
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border" data-testid="trends-table-body">
                      {filteredProducts?.map((item, index) => {
                        const tierColor = getTierColor(item.trend_tier);
                        return (
                          <tr
                            key={item.id}
                            data-testid={`trend-row-${item.id}`}
                            className="group hover:bg-muted/30 cursor-pointer transition-colors animate-fade-in"
                            style={{ animationDelay: `${index * 30}ms` }}
                            onClick={() =>
                              (window.location.href = `/product/${item.id}`)
                            }
                          >
                            <td className="px-6 py-4">
                              <div>
                                <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                                  {item.name}
                                </div>
                                {item.brand && (
                                  <div className="text-sm text-muted-foreground">
                                    {item.brand}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-sm text-muted-foreground capitalize">
                                {item.category === 'spirits' && '🥃 '}
                                {item.category === 'wine' && '🍷 '}
                                {item.category === 'beer' && '🍺 '}
                                {item.category === 'rtd' && '🥤 '}
                                {item.category}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-3">
                                <div className="w-20 h-2 bg-secondary rounded-full overflow-hidden">
                                  <div
                                    className="h-full rounded-full transition-all duration-500"
                                    style={{
                                      width: `${item.trend_score}%`,
                                      backgroundColor: tierColor,
                                    }}
                                  />
                                </div>
                                <span
                                  className="text-sm font-bold tabular-nums"
                                  style={{ color: tierColor }}
                                >
                                  {item.trend_score.toFixed(0)}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <Badge variant={item.trend_tier as any}>
                                {item.trend_tier}
                              </Badge>
                            </td>
                            <td className="px-6 py-4">
                              <span className="text-sm text-muted-foreground tabular-nums">
                                {item.component_breakdown?.media ?? '-'}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              {item.score_change_24h != null ? (
                                <span className={cn(
                                  "text-sm font-medium tabular-nums",
                                  item.score_change_24h > 0 ? "text-green-400" : item.score_change_24h < 0 ? "text-red-400" : "text-muted-foreground"
                                )}>
                                  {item.score_change_24h > 0 ? "+" : ""}{item.score_change_24h.toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-sm text-muted-foreground">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Empty State */}
                {filteredProducts?.length === 0 && (
                  <div className="flex items-center justify-center h-64" data-testid="trends-empty">
                    <div className="text-center">
                      <span className="text-5xl mb-4 block">🔍</span>
                      <h3 className="text-lg font-semibold mb-2">No products found</h3>
                      <p className="text-muted-foreground">
                        Try adjusting your filters or search term
                      </p>
                    </div>
                  </div>
                )}

                {/* Pagination */}
                {(data?.meta?.total || 0) > pageSize && (
                  <div className="border-t border-border px-4 sm:px-6 py-3 sm:py-4" data-testid="trends-pagination">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                      <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
                        Showing{' '}
                        <span className="font-medium text-foreground">
                          {(page - 1) * pageSize + 1}
                        </span>{' '}
                        to{' '}
                        <span className="font-medium text-foreground">
                          {Math.min(page * pageSize, data?.meta?.total || 0)}
                        </span>{' '}
                        of{' '}
                        <span className="font-medium text-foreground">{data?.meta?.total || 0}</span>{' '}
                        results
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage((p) => Math.max(1, p - 1))}
                          disabled={page === 1}
                          data-testid="pagination-prev"
                        >
                          <span className="sm:hidden">←</span>
                          <span className="hidden sm:inline">← Previous</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPage((p) => p + 1)}
                          disabled={page * pageSize >= (data?.meta?.total || 0)}
                          data-testid="pagination-next"
                        >
                          <span className="hidden sm:inline">Next →</span>
                          <span className="sm:hidden">→</span>
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
    </Layout>
  );
}
