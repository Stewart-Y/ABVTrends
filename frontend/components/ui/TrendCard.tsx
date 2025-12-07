'use client';

import Link from 'next/link';
import { cn, getTierColor, formatPercentage } from '@/lib/utils';

interface TrendCardProps {
  id: string;
  name: string;
  brand?: string;
  category: string;
  score: number;
  tier: string;
  change24h?: number;
  signalCount?: number;
  rank?: number;
  delay?: number;
}

export function TrendCard({
  id,
  name,
  brand,
  category,
  score,
  tier,
  change24h,
  signalCount,
  rank,
  delay = 0,
}: TrendCardProps) {
  const tierColor = getTierColor(tier);
  const scorePercentage = score / 100;

  return (
    <Link
      href={`/product/${id}`}
      className={cn(
        'group relative block p-5 rounded-xl bg-card border border-border',
        'hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5',
        'transition-all duration-300 opacity-0 animate-fade-in',
        'cursor-pointer overflow-hidden'
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Glow effect on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background: `radial-gradient(circle at 50% 0%, ${tierColor}15, transparent 70%)`,
        }}
      />

      {/* Rank badge */}
      {rank && (
        <div className="absolute top-3 right-3 w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
          <span className="text-xs font-bold text-muted-foreground">#{rank}</span>
        </div>
      )}

      <div className="relative flex items-start gap-4">
        {/* Score Circle */}
        <div className="relative flex-shrink-0">
          <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
            {/* Background circle */}
            <circle
              cx="32"
              cy="32"
              r="28"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
              className="text-secondary"
            />
            {/* Progress circle */}
            <circle
              cx="32"
              cy="32"
              r="28"
              fill="none"
              stroke={tierColor}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${scorePercentage * 176} 176`}
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-lg font-bold" style={{ color: tierColor }}>
              {score.toFixed(0)}
            </span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={cn('badge', `badge-${tier}`)}
            >
              {tier}
            </span>
            <span className="text-xs text-muted-foreground capitalize">
              {category}
            </span>
          </div>

          <h3 className="text-base font-semibold text-foreground truncate group-hover:text-primary transition-colors">
            {name}
          </h3>

          {brand && (
            <p className="text-sm text-muted-foreground truncate">{brand}</p>
          )}

          <div className="flex items-center gap-4 mt-3">
            {change24h !== undefined && (
              <div className="flex items-center gap-1">
                <svg
                  className={cn(
                    'w-3 h-3',
                    change24h >= 0 ? 'text-green-500' : 'text-red-500 rotate-180'
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 10l7-7m0 0l7 7m-7-7v18"
                  />
                </svg>
                <span
                  className={cn(
                    'text-xs font-medium',
                    change24h >= 0 ? 'text-green-500' : 'text-red-500'
                  )}
                >
                  {formatPercentage(change24h)}
                </span>
                <span className="text-xs text-muted-foreground">24h</span>
              </div>
            )}

            {signalCount !== undefined && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                {signalCount} signals
              </div>
            )}
          </div>
        </div>

        {/* Arrow indicator */}
        <div className="self-center opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-x-2 group-hover:translate-x-0">
          <svg
            className="w-5 h-5 text-primary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </div>
    </Link>
  );
}
