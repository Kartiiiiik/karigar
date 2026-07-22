/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Simple, functional palette. Amber nods to gold without being loud.
        brand: {
          50: "#fffbeb",
          100: "#fef3c7",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
        },
        // Semantic accounting tokens — used instead of hardcoding amber/green/red
        // across the app. Dr = given out, Cr = received, danger = destructive.
        dr: { DEFAULT: "#b45309", soft: "#fef3c7", softer: "#fffbeb", ring: "#fcd34d" },
        cr: { DEFAULT: "#15803d", soft: "#dcfce7" },
        danger: { DEFAULT: "#dc2626", dark: "#b91c1c", soft: "#fef2f2", text: "#b91c1c" },
      },
    },
  },
  plugins: [],
};
