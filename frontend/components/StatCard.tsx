import { Card } from './ui/card';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  iconPath: string;
  trend?: 'up' | 'down' | 'neutral';
  delay?: number;
}

export function StatCard({ title, value, change, iconPath, trend = 'neutral', delay = 0 }: StatCardProps) {
  return (
    <Card
      className={cn(
        'stat-card animate-fade-in group p-3 sm:p-4 lg:p-6',
        `animation-delay-${delay}`
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-1 sm:mb-2 truncate">{title}</p>
          <div className="flex items-baseline gap-1 sm:gap-2 flex-wrap">
            <h3 className="text-xl sm:text-2xl lg:text-3xl font-bold tracking-tight">{value}</h3>
            {change !== undefined && (
              <span
                className={cn(
                  'text-xs sm:text-sm font-semibold flex items-center gap-0.5',
                  trend === 'up' && 'text-green-400',
                  trend === 'down' && 'text-red-400',
                  trend === 'neutral' && 'text-muted-foreground'
                )}
              >
                {trend === 'up' && <span>↑</span>}
                {trend === 'down' && <span>↓</span>}
                {Math.abs(change)}%
              </span>
            )}
          </div>
        </div>
        <div className="flex h-8 w-8 sm:h-10 sm:w-10 lg:h-12 lg:w-12 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20 flex-shrink-0">
          <svg className="w-4 h-4 sm:w-5 sm:h-5 lg:w-6 lg:h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d={iconPath} />
          </svg>
        </div>
      </div>

      {/* Subtle bottom gradient */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-primary/0 via-primary/50 to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity" />
    </Card>
  );
}
