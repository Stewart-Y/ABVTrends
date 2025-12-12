'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getProductPrices, ProductPricesResponse } from '@/services/api';

interface PriceHistoryChartProps {
  productId: string;
}

const DISTRIBUTOR_COLORS = [
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#06b6d4', // cyan
];

export function PriceHistoryChart({ productId }: PriceHistoryChartProps) {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery({
    queryKey: ['productPrices', productId, days],
    queryFn: () => getProductPrices(productId, days),
    enabled: !!productId,
  });

  if (isLoading) {
    return (
      <Card data-testid="price-history-loading">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">💰</span>
            Price History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card data-testid="price-history-error">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">💰</span>
            Price History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <span className="text-3xl mb-2 block">📊</span>
            <p>Price data not available</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (data.total_records === 0) {
    return (
      <Card data-testid="price-history-empty">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">💰</span>
            Price History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <span className="text-3xl mb-2 block">📈</span>
            <p>No price history available</p>
            <p className="text-sm mt-1">Price data will appear once distributors report prices</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Transform data for chart
  const chartData = transformPriceData(data);

  return (
    <Card data-testid="price-history-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">💰</span>
            Price History
          </CardTitle>
          <div className="flex items-center gap-2">
            {[7, 30, 90].map((d) => (
              <Button
                key={d}
                variant={days === d ? 'default' : 'outline'}
                size="sm"
                onClick={() => setDays(d)}
              >
                {d}d
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Price Stats */}
        {data.stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <PriceStat label="Current" value={data.stats.current} />
            <PriceStat label="Min" value={data.stats.min} />
            <PriceStat label="Max" value={data.stats.max} />
            <PriceStat label="Average" value={data.stats.avg} />
            <PriceStat
              label="Change"
              value={data.stats.change_pct}
              isPercent
              showColor
            />
          </div>
        )}

        {/* Chart */}
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
              axisLine={{ stroke: 'hsl(var(--border))' }}
            />
            <YAxis
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip content={<PriceTooltip />} />
            <Legend />
            {data.distributors.map((dist, idx) => (
              <Line
                key={dist.slug}
                type="monotone"
                dataKey={dist.slug}
                name={dist.distributor}
                stroke={DISTRIBUTOR_COLORS[idx % DISTRIBUTOR_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>

        {/* Distributor Legend */}
        <div className="flex flex-wrap gap-3 mt-4">
          {data.distributors.map((dist, idx) => (
            <Badge
              key={dist.slug}
              variant="outline"
              className="text-xs"
              style={{ borderColor: DISTRIBUTOR_COLORS[idx % DISTRIBUTOR_COLORS.length] }}
            >
              <span
                className="w-2 h-2 rounded-full mr-2"
                style={{ backgroundColor: DISTRIBUTOR_COLORS[idx % DISTRIBUTOR_COLORS.length] }}
              />
              {dist.distributor} ({dist.prices.length} records)
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PriceStat({
  label,
  value,
  isPercent = false,
  showColor = false,
}: {
  label: string;
  value: number;
  isPercent?: boolean;
  showColor?: boolean;
}) {
  const displayValue = isPercent
    ? `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
    : `$${value.toFixed(2)}`;

  const colorClass = showColor
    ? value >= 0
      ? 'text-green-400'
      : 'text-red-400'
    : 'text-foreground';

  return (
    <div className="p-3 rounded-lg bg-card/50 border border-border/30">
      <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${colorClass}`}>{displayValue}</p>
    </div>
  );
}

function PriceTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card/95 backdrop-blur-xl border border-border rounded-lg p-3 shadow-xl">
        <p className="text-xs text-muted-foreground mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
            {entry.name}: ${entry.value?.toFixed(2)}
          </p>
        ))}
      </div>
    );
  }
  return null;
}

function transformPriceData(data: ProductPricesResponse): any[] {
  // Get all unique dates across all distributors
  const allDates = new Set<string>();
  data.distributors.forEach((dist) => {
    dist.prices.forEach((p) => {
      const date = new Date(p.recorded_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      allDates.add(date);
    });
  });

  // Sort dates
  const sortedDates = Array.from(allDates).sort((a, b) => {
    return new Date(a).getTime() - new Date(b).getTime();
  });

  // Create chart data with each distributor as a column
  return sortedDates.map((date) => {
    const point: any = { date };
    data.distributors.forEach((dist) => {
      const priceRecord = dist.prices.find((p) => {
        const recordDate = new Date(p.recorded_at).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        });
        return recordDate === date;
      });
      point[dist.slug] = priceRecord ? priceRecord.price : null;
    });
    return point;
  });
}
