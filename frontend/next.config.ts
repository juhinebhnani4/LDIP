import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Production builds should not ignore TypeScript errors
  // Set to true only for local development if needed
  typescript: {
    // In production (Vercel), this defaults to false
    // Explicit configuration for clarity
    ignoreBuildErrors: process.env.NODE_ENV === 'development',
  },
  // Note: Next.js 16 removed eslint config - linting is now done via npm scripts
  // See: https://nextjs.org/docs/app/guides/upgrading/version-16
  // Optimize images from Supabase Storage
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.supabase.co',
        pathname: '/storage/v1/object/**',
      },
    ],
  },
  // Standalone output for containerized deployments
  output: process.env.STANDALONE_OUTPUT === 'true' ? 'standalone' : undefined,
}

export default nextConfig
