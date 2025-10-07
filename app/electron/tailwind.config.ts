import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#38bdf8',
        surface: '#111827',
      },
    },
  },
  plugins: [],
};

export default config;
