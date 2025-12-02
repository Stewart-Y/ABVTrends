/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },

  // Image optimization
  images: {
    domains: [
      'localhost',
      'www.liquor.com',
      'vinepair.com',
      'punchdrink.com',
      'www.totalwine.com',
      'www.reservebar.com',
      'www.bevmo.com',
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // API rewrites for development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/:path*`,
      },
    ];
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
        ],
      },
    ];
  },

  // Webpack configuration
  webpack: (config, { isServer }) => {
    // Fix for recharts SSR
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }
    return config;
  },

  // Output configuration for production
  output: 'standalone',

  // Experimental features
  experimental: {
    // Enable server actions if needed
    // serverActions: true,
  },
};

module.exports = nextConfig;
