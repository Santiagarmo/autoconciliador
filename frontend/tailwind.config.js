/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#FAF7F0",
          raised: "#FDFBF6",
          sunk: "#F2ECE0",
        },
        rule: {
          DEFAULT: "#E2DACA",
          strong: "#C9BFA9",
        },
        ink: {
          DEFAULT: "#16150F",
          muted: "#6B665A",
          faint: "#9C9585",
        },
        ochre: {
          DEFAULT: "#A8571C",
          deep: "#7E3F12",
          tint: "#F3E6D5",
        },
        moss: "#3F6B3A",
        oxide: "#A3301E",
        "amber-deep": "#99701A",
        "indigo-slate": "#34506E",
      },
      fontFamily: {
        display: ["'Fraunces'", "ui-serif", "serif"],
        sans: ["'Archivo'", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
