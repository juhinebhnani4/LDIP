/**
 * Landing page layout - forces light mode for consistent branding
 * Uses data-theme attribute + CSS to override dark mode
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div data-theme="light" className="landing-light min-h-screen">
      {children}
    </div>
  )
}
