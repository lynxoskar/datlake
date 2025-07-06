import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Synthwave color palette
        synthwave: {
          // Dark backgrounds
          'deep': '#0a0a0f',
          'dark': '#1a0b2e',
          'darker': '#16213e',
          'purple': '#240046',
          'indigo': '#3c096c',
          // Bright neons
          'pink': '#ff006e',
          'cyan': '#00f5ff',
          'green': '#39ff14',
          'orange': '#ff9500',
          'yellow': '#ffff00',
          // Mid-tones
          'violet': '#7209b7',
          'blue': '#560bad',
          'teal': '#277da1',
        },
        background: 'var(--background)',
        foreground: 'var(--foreground)',
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace'],
        'cyber': ['Orbitron', 'Exo 2', 'system-ui', 'sans-serif'],
      },
      animation: {
        'glow': 'glow 2s ease-in-out infinite alternate',
        'flicker': 'flicker 3s linear infinite',
        'pulse-neon': 'pulse-neon 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scan-line 2s linear infinite',
      },
      keyframes: {
        glow: {
          'from': { 
            textShadow: '0 0 20px #00f5ff, 0 0 30px #00f5ff, 0 0 40px #00f5ff',
            boxShadow: '0 0 20px #00f5ff, 0 0 30px #00f5ff, 0 0 40px #00f5ff',
          },
          'to': { 
            textShadow: '0 0 5px #00f5ff, 0 0 10px #00f5ff, 0 0 15px #00f5ff',
            boxShadow: '0 0 5px #00f5ff, 0 0 10px #00f5ff, 0 0 15px #00f5ff',
          },
        },
        flicker: {
          '0%, 19%, 21%, 23%, 25%, 54%, 56%, 100%': { opacity: '1' },
          '20%, 24%, 55%': { opacity: '0.4' },
        },
        'pulse-neon': {
          '0%, 100%': { 
            opacity: '1',
            textShadow: '0 0 5px currentColor, 0 0 10px currentColor, 0 0 20px currentColor',
          },
          '50%': { 
            opacity: '0.8',
            textShadow: '0 0 2px currentColor, 0 0 5px currentColor, 0 0 10px currentColor',
          },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
      },
      boxShadow: {
        'neon-cyan': '0 0 5px #00f5ff, 0 0 20px #00f5ff, 0 0 35px #00f5ff',
        'neon-pink': '0 0 5px #ff006e, 0 0 20px #ff006e, 0 0 35px #ff006e',
        'neon-green': '0 0 5px #39ff14, 0 0 20px #39ff14, 0 0 35px #39ff14',
        'terminal': 'inset 0 0 0 1px #00f5ff, 0 0 20px rgba(0, 245, 255, 0.3)',
      },
      backdropBlur: {
        'terminal': '10px',
      },
    },
  },
  plugins: [],
}
export default config 