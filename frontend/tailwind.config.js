/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#f0fbfe',
          100: '#dff6fc',
          200: '#b8edf8',
          300: '#9fe7f5',
          400: '#56d0ec',
          500: '#2db9d8',
          600: '#1799b8',
          700: '#157a96',
          800: '#18647c',
          900: '#195469',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
