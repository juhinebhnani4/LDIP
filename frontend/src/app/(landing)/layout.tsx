/**
 * Landing page layout - forces light mode for consistent branding
 * The landing page always displays in light mode regardless of system preference
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="light" style={{ colorScheme: 'light' }}>
      {children}
    </div>
  )
}
