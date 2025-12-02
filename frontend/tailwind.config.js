/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // ABVTrends brand colors
        brand: {
          50: '#fdf4f3',
          100: '#fce8e6',
          200: '#f9d4d1',
          300: '#f4b3ac',
          400: '#eb8478',
          500: '#de5a4a',
          600: '#cb3f2e',
          700: '#aa3324',
          800: '#8c2e22',
          900: '#752b23',
        },
        // Trend tier colors
        trend: {
          viral: '#ef4444',
          trending: '#f97316',
          emerging: '#eab308',
          stable: '#22c55e',
          declining: '#6b7280',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
