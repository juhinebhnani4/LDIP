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
  const lightModeVars = {
    colorScheme: 'light',
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
  } as React.CSSProperties

  return (
    <div className="light min-h-screen bg-[#f8f6f1]" style={lightModeVars}>
      {children}
    </div>
  )
}
