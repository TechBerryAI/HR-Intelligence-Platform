/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Sora', 'Plus Jakarta Sans', 'sans-serif'],
      },
      colors: {
        primary: {
          DEFAULT: '#0F172A',
          light: '#1E293B',
          dark: '#020617',
        },
        secondary: {
          DEFAULT: '#1E293B',
          light: '#334155',
          dark: '#0F172A',
        },
        accent: {
          gold: '#C9A227',
          'gold-light': '#E5C158',
          'gold-dark': '#A68520',
          blue: '#8FA3B8',
          'blue-light': '#A8B8C8',
          'blue-dark': '#6B7F94',
        },
        surface: {
          DEFAULT: '#F8FAFC',
          card: '#FFFFFF',
          muted: '#F1F5F9',
        },
        glass: {
          light: 'rgba(255, 255, 255, 0.7)',
          medium: 'rgba(255, 255, 255, 0.5)',
          dark: 'rgba(15, 23, 42, 0.8)',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'premium-hero': 'linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 50%, #F1F5F9 100%)',
        'premium-hero-dark': 'linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.1)',
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 10px 40px -10px rgba(0 0 0 / 0.15), 0 4px 6px -2px rgba(0 0 0 / 0.05)',
        'premium': '0 20px 60px -15px rgba(0 0 0 / 0.1), 0 0 1px rgba(0 0 0 / 0.05)',
        'premium-dark': '0 20px 60px rgba(0 0 0, 0.3), 0 0 1px rgba(255, 255, 255, 0.05)',
        'inner-soft': 'inset 0 1px 2px 0 rgb(0 0 0 / 0.05)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'hologram': 'hologramPulse 3s ease-in-out infinite',
        'coreGlow': 'coreGlow 2.5s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        hologramPulse: {
          '0%, 100%': { opacity: '0.6', filter: 'blur(0px)' },
          '50%': { opacity: '1', filter: 'blur(1px)' },
        },
        coreGlow: {
          '0%, 100%': { boxShadow: '0 0 40px rgba(59,130,246,0.3)' },
          '50%': { boxShadow: '0 0 80px rgba(34,211,238,0.5)' },
        },
      },
    },
  },
  plugins: [],
}
