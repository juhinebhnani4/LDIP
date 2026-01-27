/**
 * Landing page layout - forces light mode for consistent branding
 * The landing page always displays in light mode regardless of system preference
 *
 * Uses inline CSS variables to override any dark mode settings from next-themes
 * because the ThemeProvider adds .dark to <html> based on system preference
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Force light mode CSS variables inline to override dark mode from system preference
  // Must set BOTH base variables (--background) AND Tailwind theme variables (--color-background)
  // because Tailwind 4's @theme inline resolves --color-* at :root level
  const lightModeVars = {
    colorScheme: 'light',
    // Base variables
    '--background': '#f8f6f1',
    '--foreground': '#1a1a1a',
    '--card': '#ffffff',
    '--card-foreground': '#1a1a1a',
    '--popover': '#ffffff',
    '--popover-foreground': '#1a1a1a',
    '--primary': '#0d1b5e',
    '--primary-foreground': '#ffffff',
    '--secondary': '#f8f6f1',
    '--secondary-foreground': '#1a1a1a',
    '--muted': '#e8e4dc',
    '--muted-foreground': '#64748b',
    '--accent': '#b8973b',
    '--accent-foreground': '#0d1b5e',
    '--destructive': '#8b2635',
    '--destructive-foreground': '#ffffff',
    '--border': '#e8e4dc',
    '--input': '#e8e4dc',
    '--ring': '#0d1b5e',
    // Tailwind theme variables (--color-* used by bg-*, text-*, etc.)
    '--color-background': '#f8f6f1',
    '--color-foreground': '#1a1a1a',
    '--color-card': '#ffffff',
    '--color-card-foreground': '#1a1a1a',
    '--color-popover': '#ffffff',
    '--color-popover-foreground': '#1a1a1a',
    '--color-primary': '#0d1b5e',
    '--color-primary-foreground': '#ffffff',
    '--color-secondary': '#f8f6f1',
    '--color-secondary-foreground': '#1a1a1a',
    '--color-muted': '#e8e4dc',
    '--color-muted-foreground': '#64748b',
    '--color-accent': '#b8973b',
    '--color-accent-foreground': '#0d1b5e',
    '--color-destructive': '#8b2635',
    '--color-destructive-foreground': '#ffffff',
    '--color-border': '#e8e4dc',
    '--color-input': '#e8e4dc',
    '--color-ring': '#0d1b5e',
  } as React.CSSProperties

  return (
    <div className="light min-h-screen bg-[#f8f6f1]" style={lightModeVars}>
      {children}
    </div>
  )
}
