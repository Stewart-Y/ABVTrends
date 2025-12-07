import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
}

export function formatPercentage(num: number): string {
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(1)}%`;
}

export function getTierColor(tier: string): string {
  const colors: Record<string, string> = {
    viral: '#ef4444',
    trending: '#f97316',
    emerging: '#eab308',
    stable: '#22c55e',
    declining: '#6b7280',
  };
  return colors[tier] || colors.stable;
}

export function getTierGradient(tier: string): string {
  const gradients: Record<string, string> = {
    viral: 'from-red-500 to-orange-500',
    trending: 'from-orange-500 to-amber-500',
    emerging: 'from-yellow-500 to-lime-500',
    stable: 'from-green-500 to-emerald-500',
    declining: 'from-gray-500 to-slate-500',
  };
  return gradients[tier] || gradients.stable;
}
