/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './Jobflex/JFlex/templates/**/*.html',
    './Jobflex/JFlex/static/JS/**/*.js',
    './Jobflex/JFlex/**/*.py', 
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#8CA01A',
        'secondary': '#1A8CA0',
        'light-gray': '#D8D9DD',
        'dark': '#101208',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out forwards',
        'fade-out':'fadeOut 0.2s ease-out forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        }
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}