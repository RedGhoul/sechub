import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0f17",
        panel: "#121826",
        edge: "#1f2937",
        muted: "#8b95a7",
        accent: "#4f8cff",
        pos: "#22c55e",
        neg: "#ef4444",
      },
    },
  },
  plugins: [],
};
export default config;
