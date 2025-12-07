'use client';

import { cn, formatNumber, formatPercentage } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  className?: string;
  delay?: number;
}

export function StatCard({
  title,
  value,
  change,
  changeLabel = 'vs last week',
  icon,
  className,
  delay = 0,
}: StatCardProps) {
  const isPositive = change && change >= 0;

  return (
    <div
      className={cn(
        'stat-card group cursor-pointer opacity-0 animate-fade-in',
        className
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Background glow effect */}
      <div className="absolute -top-20 -right-20 w-40 h-40 bg-primary/5 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <div className="relative">
        <div className="flex items-start justify-between mb-4">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          {icon && (
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              {icon}
            </div>
          )}
        </div>

        <div className="flex items-end justify-between">
          <div>
            <p className="text-3xl font-bold text-foreground tracking-tight">
              {typeof value === 'number' ? formatNumber(value) : value}
            </p>
            {change !== undefined && (
              <div className="flex items-center gap-1.5 mt-2">
                <span
                  className={cn(
                    'inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-semibold',
                    isPositive
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  )}
                >
                  <svg
                    className={cn('w-3 h-3', !isPositive && 'rotate-180')}
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
                  {formatPercentage(Math.abs(change))}
                </span>
                <span className="text-xs text-muted-foreground">
                  {changeLabel}
                </span>
              </div>
            )}
          </div>

          {/* Mini sparkline placeholder */}
          <div className="w-20 h-10 opacity-50">
            <svg viewBox="0 0 80 40" className="w-full h-full">
              <path
                d="M0 35 L10 30 L20 32 L30 25 L40 28 L50 15 L60 18 L70 8 L80 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={isPositive ? 'text-green-500' : 'text-red-500'}
              />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
