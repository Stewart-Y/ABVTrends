'use client';

import { useEffect, useState } from 'react';
import { cn, getTierColor } from '@/lib/utils';

interface ScoreGaugeProps {
  score: number;
  tier: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  animated?: boolean;
  className?: string;
}

const sizes = {
  sm: { width: 80, strokeWidth: 6, fontSize: 'text-lg' },
  md: { width: 120, strokeWidth: 8, fontSize: 'text-2xl' },
  lg: { width: 160, strokeWidth: 10, fontSize: 'text-4xl' },
};

export function ScoreGauge({
  score,
  tier,
  size = 'md',
  showLabel = true,
  animated = true,
  className,
}: ScoreGaugeProps) {
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score);
  const config = sizes[size];
  const tierColor = getTierColor(tier);

  const radius = (config.width - config.strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const scorePercentage = displayScore / 100;
  const strokeDashoffset = circumference * (1 - scorePercentage);

  useEffect(() => {
    if (!animated) return;

    const duration = 2000; // 2 seconds for smoother animation
    const startTime = Date.now();

    // Easing function for smooth acceleration and deceleration
    const easeOutCubic = (t: number): number => {
      return 1 - Math.pow(1 - t, 3);
    };

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeOutCubic(progress);

      setDisplayScore(score * easedProgress);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setDisplayScore(score);
      }
    };

    requestAnimationFrame(animate);
  }, [score, animated]);

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      {/* Glow effect */}
      <div
        className="absolute inset-0 blur-2xl opacity-30"
        style={{
          background: `radial-gradient(circle, ${tierColor} 0%, transparent 70%)`,
        }}
      />

      <svg
        width={config.width}
        height={config.width}
        className="transform -rotate-90"
      >
        {/* Background circle */}
        <circle
          cx={config.width / 2}
          cy={config.width / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={config.strokeWidth}
          className="text-secondary"
        />

        {/* Gradient definition */}
        <defs>
          <linearGradient id={`gauge-gradient-${tier}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={tierColor} />
            <stop offset="100%" stopColor={tierColor} stopOpacity="0.6" />
          </linearGradient>
        </defs>

        {/* Progress circle */}
        <circle
          cx={config.width / 2}
          cy={config.width / 2}
          r={radius}
          fill="none"
          stroke={`url(#gauge-gradient-${tier})`}
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000 ease-out"
          style={{
            filter: `drop-shadow(0 0 6px ${tierColor}50)`,
          }}
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn('font-bold', config.fontSize)}
          style={{ color: tierColor }}
        >
          {displayScore.toFixed(0)}
        </span>
        {showLabel && (
          <span
            className="text-xs font-semibold uppercase tracking-wider mt-0.5"
            style={{ color: tierColor }}
          >
            {tier}
          </span>
        )}
      </div>
    </div>
  );
}
