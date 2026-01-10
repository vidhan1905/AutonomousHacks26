/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Classic medical theme - softer blues and teals
        medical: {
          50: '#f0f7fa',
          100: '#e1eef5',
          200: '#c3ddeb',
          300: '#a5cce1',
          400: '#87bbd7',
          500: '#69aacd', // Soft medical blue
          600: '#4a8bb3', // Main action color
          700: '#3a6d8c',
          800: '#2a4f66',
          900: '#1a3140',
        },
        teal: {
          50: '#f0f9f8',
          100: '#d1ede9',
          200: '#a3dbd3',
          300: '#75c9bd',
          400: '#47b7a7',
          500: '#19a591', // Soft medical teal
          600: '#148473',
          700: '#0f6355',
          800: '#0a4238',
          900: '#05211a',
        },
        health: {
          50: '#f0f9f5',
          100: '#d1ede0',
          200: '#a3dbc1',
          300: '#75c9a2',
          400: '#47b783',
          500: '#19a564', // Soft health green
          600: '#14844f',
          700: '#0f633b',
          800: '#0a4227',
          900: '#052114',
        },
      },
    },
  },
  plugins: [],
}
