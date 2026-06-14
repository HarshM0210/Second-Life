/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Amazon-inspired palette
        amz: {
          navy: "#131921",      // primary header bar
          slate: "#232F3E",     // secondary nav bar
          orange: "#FF9900",    // primary accent / CTA
          yellow: "#FEBD69",    // hover / buy button
          yellowDark: "#F3A847",
          link: "#007185",      // link blue
          price: "#B12704",     // price red
          bg: "#EAEDED",        // page background
          green: "#067D62",     // "renewed"/eco accent
        },
      },
      fontFamily: {
        sans: ['"Amazon Ember"', "Arial", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};
