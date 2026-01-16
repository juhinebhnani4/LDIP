import type { Config } from "tailwindcss"

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        // Legal document font for export preview (Story 12.2)
        serif: ['"Times New Roman"', 'Times', 'serif'],
      },
    },
  },
  plugins: [],
} satisfies Config







