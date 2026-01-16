import type { Metadata } from "next"
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google"
import { Toaster } from "@/components/ui/sonner"
import "./globals.css"
import { Providers } from "./providers"

// Body text - clean, professional sans-serif
const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
})

// Headlines - elegant serif with legal authority
const fraunces = Fraunces({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
})

// Code/monospace - for citations, document IDs
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "jaanch.ai",
  description: "Verify, don't trust - AI-powered legal document verification",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${fraunces.variable} ${jetbrainsMono.variable} antialiased paper-texture`}>
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
