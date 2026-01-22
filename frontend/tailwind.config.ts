import type { Config } from "tailwindcss"
import typography from "@tailwindcss/typography"

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        // Jaanch "Intelligent Legal" typography system (UX Design v1.2)
        sans: ['var(--font-sans)', 'Inter', 'system-ui', 'sans-serif'],
        serif: ['var(--font-serif)', 'Fraunces', 'Georgia', 'serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
        // Legal document export font (Story 12.2)
        'legal-export': ['"Times New Roman"', 'Times', 'serif'],
      },
      colors: {
        // Extended semantic colors from UX design
        'seal-red': 'var(--seal-red)',
        'legal-pad': 'var(--legal-pad)',
        'success': 'var(--success)',
        'warning': 'var(--warning)',
        'info': 'var(--info)',
        // Landing page brand colors
        'indigo': 'var(--indigo)',
        'gold': 'var(--gold)',
        'burgundy': 'var(--burgundy)',
        'forest': 'var(--forest)',
      },
    },
  },
  plugins: [typography],
} satisfies Config







