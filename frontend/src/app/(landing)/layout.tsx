"use client"

import { useEffect } from "react"
import { useTheme } from "next-themes"

/**
 * Landing page layout - forces light mode for consistent branding
 * The landing page always displays in light mode regardless of system preference
 *
 * Uses useTheme hook to force light mode on mount and restore on unmount
 */
export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { setTheme, theme } = useTheme()

  useEffect(() => {
    // Store previous theme to restore on unmount
    const previousTheme = theme

    // Force light mode for landing page
    setTheme("light")

    // Restore previous theme when leaving landing page
    return () => {
      if (previousTheme && previousTheme !== "light") {
        setTheme(previousTheme)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen">
      {children}
    </div>
  )
}
