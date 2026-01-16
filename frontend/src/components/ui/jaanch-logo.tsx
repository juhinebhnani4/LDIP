/**
 * JaanchLogo Component
 *
 * Brand logo component for jaanch.ai with multiple variants:
 * - full: Icon + text displayed as separate images (allows independent sizing)
 * - icon: Icon only (the "ज" character)
 *
 * Usage:
 * - Full logo: Dashboard header, login/signup pages
 * - Icon only: Favicon, Q&A panel, collapsed sidebar, loading states
 */

import Image from 'next/image';
import { cn } from '@/lib/utils';

export type LogoVariant = 'full' | 'icon';
export type LogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface JaanchLogoProps {
  /** Logo variant - 'full' for icon+text, 'icon' for icon only */
  variant?: LogoVariant;
  /** Predefined size */
  size?: LogoSize;
  /** Custom className for additional styling */
  className?: string;
  /** Alt text for accessibility */
  alt?: string;
  /** Whether to show text alongside icon (only for 'icon' variant) */
  showText?: boolean;
}

// Size config with separate icon and text dimensions for proper proportions
// Icon is intentionally smaller relative to text to maintain visual balance
const sizeConfig: Record<LogoSize, { icon: number; text: { width: number; height: number } }> = {
  xs: { icon: 20, text: { width: 56, height: 20 } },
  sm: { icon: 28, text: { width: 80, height: 29 } },
  md: { icon: 36, text: { width: 100, height: 36 } },
  lg: { icon: 44, text: { width: 130, height: 47 } },
  xl: { icon: 56, text: { width: 160, height: 58 } },
};

/**
 * JaanchLogo - Main brand logo component
 * Uses separate icon and text images for better proportion control
 */
export function JaanchLogo({
  variant = 'full',
  size = 'md',
  className,
  alt = 'jaanch.ai',
}: JaanchLogoProps) {
  const config = sizeConfig[size];

  if (variant === 'full') {
    // Composite logo: icon + text as separate images
    return (
      <span className={cn('inline-flex items-center gap-1', className)}>
        <Image
          src="/logo-icon.png"
          alt=""
          width={config.icon}
          height={config.icon}
          className="object-contain"
          priority
          aria-hidden="true"
        />
        <Image
          src="/logo-text.png"
          alt={alt}
          width={config.text.width}
          height={config.text.height}
          className="object-contain"
          priority
        />
      </span>
    );
  }

  // Icon variant
  return (
    <Image
      src="/logo-icon.png"
      alt={alt}
      width={config.icon}
      height={config.icon}
      className={cn('object-contain', className)}
      priority
    />
  );
}

/**
 * JaanchIcon - Standalone icon component for tight spaces
 */
export function JaanchIcon({
  size = 'md',
  className,
}: {
  size?: LogoSize;
  className?: string;
}) {
  const iconSize = sizeConfig[size].icon;

  return (
    <Image
      src="/logo-icon.png"
      alt="jaanch.ai"
      width={iconSize}
      height={iconSize}
      className={cn('object-contain', className)}
      priority
    />
  );
}

export default JaanchLogo;
