import Script from "next/script"

/**
 * Landing page layout - forces light mode for consistent branding
 * The landing page always displays in light mode regardless of system preference
 *
 * Uses an inline script to set light mode BEFORE React hydration to avoid flash
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      {/* Force light mode before hydration - runs immediately */}
      <Script id="force-light-mode" strategy="beforeInteractive">
        {`document.documentElement.classList.remove('dark');
          document.documentElement.classList.add('light');
          document.documentElement.style.colorScheme = 'light';`}
      </Script>
      <div className="min-h-screen bg-[#f8f6f1]">
        {children}
      </div>
    </>
  )
}
