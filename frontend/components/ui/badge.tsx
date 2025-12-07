import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'viral' | 'trending' | 'emerging' | 'stable' | 'declining' | 'default';
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold transition-all',
        {
          'bg-red-500/20 text-red-400 border border-red-500/30': variant === 'viral',
          'bg-orange-500/20 text-orange-400 border border-orange-500/30': variant === 'trending',
          'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30': variant === 'emerging',
          'bg-green-500/20 text-green-400 border border-green-500/30': variant === 'stable',
          'bg-gray-500/20 text-gray-400 border border-gray-500/30': variant === 'declining',
          'bg-primary/20 text-primary border border-primary/30': variant === 'default',
        },
        className
      )}
      {...props}
    />
  );
}

export { Badge };
