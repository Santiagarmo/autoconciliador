/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0B0E14",
          raised: "#10141C",
          sunk: "#070910",
        },
        line: {
          DEFAULT: "#1E2533",
          strong: "#2E3849",
        },
        fg: {
          DEFAULT: "#E6EAF2",
          muted: "#98A3B8",
          faint: "#5D6779",
        },
        steel: {
          DEFAULT: "#4C7DF0",
          deep: "#3562D4",
          tint: "#1A2338",
        },
        signal: {
          pos: "#2FA36B",
          warn: "#E8A73D",
          neg: "#E0524A",
          info: "#5B8DBD",
        },
      },
      fontFamily: {
        display: ["'Instrument Sans'", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["'Instrument Sans'", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      fontSize: {
        display: ["2.5rem", { lineHeight: "0.98", letterSpacing: "-0.03em", fontWeight: "600" }],
        title: ["1.625rem", { lineHeight: "1.15", letterSpacing: "-0.02em", fontWeight: "600" }],
        stat: ["1.875rem", { lineHeight: "1", letterSpacing: "-0.02em", fontWeight: "600" }],
        subtitle: ["1.0625rem", { lineHeight: "1.3", letterSpacing: "-0.01em", fontWeight: "600" }],
        body: ["0.875rem", { lineHeight: "1.55", fontWeight: "400" }],
        small: ["0.78125rem", { lineHeight: "1.5", fontWeight: "400" }],
        label: ["0.6875rem", { lineHeight: "1.2", letterSpacing: "0.14em", fontWeight: "500" }],
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "rise-lg": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "page-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "modal-in": {
          from: { opacity: "0", transform: "scale(0.98) translateY(4px)" },
          to: { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        "modal-out": {
          from: { opacity: "1", transform: "scale(1) translateY(0)" },
          to: { opacity: "0", transform: "scale(0.98) translateY(4px)" },
        },
        "scrim-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "rule-grow": {
          from: { transform: "scaleX(0)" },
          to: { transform: "scaleX(1)" },
        },
        "row-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "grid-drift": {
          from: { backgroundPosition: "0 0" },
          to: { backgroundPosition: "0 48px" },
        },
        scanline: {
          "0%": { transform: "translateY(-10%)", opacity: "0" },
          "8%": { opacity: "0.5" },
          "45%": { opacity: "0.5" },
          "55%": { opacity: "0" },
          "100%": { transform: "translateY(110%)", opacity: "0" },
        },
        "focus-pop": {
          "0%": { transform: "scale(1)" },
          "40%": { transform: "scale(1.012)" },
          "100%": { transform: "scale(1)" },
        },
        "cursor-expand": {
          "0%, 100%": { transform: "scaleY(0)", opacity: "0" },
          "50%": { transform: "scaleY(1)", opacity: "1" },
        },
      },
      animation: {
        rise: "rise 0.4s ease-out both",
        "rise-lg": "rise-lg 0.5s ease-out both",
        "page-in": "page-in 0.18s ease-out both",
        "modal-in": "modal-in 0.2s cubic-bezier(0.16, 1, 0.3, 1) both",
        "modal-out": "modal-out 0.15s ease-in both",
        "scrim-in": "scrim-in 0.2s ease-out both",
        "rule-grow": "rule-grow 0.4s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both",
        "row-in": "row-in 0.22s ease-out both",
        "grid-drift": "grid-drift 6s linear infinite",
        scanline: "scanline 7s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "focus-in": "focus-pop 0.25s ease-out both",
        "cursor-expand": "cursor-expand 1s ease-in-out infinite",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
