'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Layout } from '@/components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from 'recharts';
import { getTopTrends, getTrendingProducts } from '@/services/api';
import { cn } from '@/lib/utils';

// Color palette for charts
const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#6b7280'];
const TIER_COLORS: Record<string, string> = {
  viral: '#ef4444',
  trending: '#f97316',
  emerging: '#eab308',
  stable: '#22c55e',
  declining: '#6b7280',
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card/95 backdrop-blur-xl border border-border rounded-lg p-3 shadow-xl">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function AnalyticsPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.documentElement.classList.add('dark');
    setMounted(true);
  }, []);

  const { data: topTrends, isLoading: trendsLoading } = useQuery({
    queryKey: ['topTrends'],
    queryFn: getTopTrends,
  });

  const { data: allTrends, isLoading: allLoading } = useQuery({
    queryKey: ['allTrends'],
    queryFn: () => getTrendingProducts({ limit: 1000 }),
  });

  if (!mounted) return null;

  // Calculate tier distribution
  const tierDistribution = allTrends?.items?.reduce(
    (acc, product) => {
      const tier = product.trend_tier || 'stable';
      acc[tier] = (acc[tier] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  ) || {};

  const tierChartData = Object.entries(tierDistribution).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    color: TIER_COLORS[name] || '#6b7280',
  }));

  // Calculate category distribution
  const categoryDistribution = allTrends?.items?.reduce(
    (acc, product) => {
      const category = product.category || 'other';
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  ) || {};

  const categoryChartData = Object.entries(categoryDistribution).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }));

  // Calculate average scores by tier
  const tierAverages = allTrends?.items?.reduce(
    (acc, product) => {
      const tier = product.trend_tier || 'stable';
      if (!acc[tier]) {
        acc[tier] = { total: 0, count: 0 };
      }
      acc[tier].total += product.trend_score;
      acc[tier].count += 1;
      return acc;
    },
    {} as Record<string, { total: number; count: number }>
  ) || {};

  const tierAvgData = Object.entries(tierAverages).map(([tier, data]) => ({
    tier: tier.charAt(0).toUpperCase() + tier.slice(1),
    avgScore: Math.round(data.total / data.count),
    color: TIER_COLORS[tier],
  }));

  // Summary statistics
  const totalProducts = allTrends?.items?.length || 0;
  const avgScore = totalProducts > 0
    ? Math.round((allTrends?.items?.reduce((sum, p) => sum + p.trend_score, 0) || 0) / totalProducts)
    : 0;
  const viralCount = tierDistribution['viral'] || 0;
  const trendingCount = tierDistribution['trending'] || 0;

  const isLoading = trendsLoading || allLoading;

  return (
    <Layout
      title="Analytics"
      subtitle="Platform insights and trend analysis"
      testId="analytics-page"
    >
      <div className="space-y-6" data-testid="analytics-header">
        {isLoading ? (
          <div className="flex items-center justify-center h-64" data-testid="analytics-loading">
            <div className="text-center">
              <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent mb-4" />
              <p className="text-muted-foreground">Loading analytics...</p>
            </div>
          </div>
        ) : (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="summary-stats">
              <Card className="bg-gradient-to-br from-card to-card/80">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">📦</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Total Products</span>
                  </div>
                  <p className="text-3xl font-bold">{totalProducts}</p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-card to-card/80">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">📊</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Avg Score</span>
                  </div>
                  <p className="text-3xl font-bold">{avgScore}</p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-card to-card/80">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">🔥</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Viral</span>
                  </div>
                  <p className="text-3xl font-bold text-red-400">{viralCount}</p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-card to-card/80">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">📈</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Trending</span>
                  </div>
                  <p className="text-3xl font-bold text-orange-400">{trendingCount}</p>
                </CardContent>
              </Card>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Tier Distribution Pie Chart */}
              <Card data-testid="tier-distribution-chart">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">🎯</span>
                    Tier Distribution
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {tierChartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={tierChartData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          outerRadius={100}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {tierChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                      No data available
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Category Distribution Bar Chart */}
              <Card data-testid="category-distribution-chart">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">📊</span>
                    Products by Category
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {categoryChartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={categoryChartData} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis type="number" tick={{ fill: 'hsl(var(--muted-foreground))' }} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          tick={{ fill: 'hsl(var(--muted-foreground))' }}
                          width={80}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="value" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} name="Products" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                      No data available
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Average Score by Tier */}
            <Card data-testid="avg-score-by-tier">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">📈</span>
                  Average Score by Tier
                </CardTitle>
              </CardHeader>
              <CardContent>
                {tierAvgData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={tierAvgData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="tier" tick={{ fill: 'hsl(var(--muted-foreground))' }} />
                      <YAxis domain={[0, 100]} tick={{ fill: 'hsl(var(--muted-foreground))' }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="avgScore" name="Average Score" radius={[4, 4, 0, 0]}>
                        {tierAvgData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                    No data available
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Tier Breakdown Table */}
            <Card data-testid="tier-breakdown">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-xl">📋</span>
                  Tier Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  {['viral', 'trending', 'emerging', 'stable', 'declining'].map((tier) => {
                    const count = tierDistribution[tier] || 0;
                    const percentage = totalProducts > 0 ? ((count / totalProducts) * 100).toFixed(1) : '0';
                    return (
                      <div
                        key={tier}
                        className="p-4 rounded-lg bg-card/50 border border-border/30 hover:border-primary/30 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <Badge variant={tier as any}>{tier}</Badge>
                          <span className="text-xs text-muted-foreground">{percentage}%</span>
                        </div>
                        <p className="text-2xl font-bold" style={{ color: TIER_COLORS[tier] }}>
                          {count}
                        </p>
                        <p className="text-xs text-muted-foreground">products</p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </Layout>
  );
}
