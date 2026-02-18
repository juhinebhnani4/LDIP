'use client';

/**
 * AppearanceSection Component
 *
 * Displays current theme (light mode only).
 *
 * Story 14.14: Settings Page Implementation
 * Task 7: Create AppearanceSection component
 */

import { Palette, Sun } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';

export function AppearanceSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Palette className="size-5" />
          Appearance
        </CardTitle>
        <CardDescription>
          Customize how Jaanch looks on your device
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Theme</Label>
          <div className="flex items-center gap-3 p-4 rounded-lg border-2 border-primary bg-primary/5">
            <Sun className="size-6 text-primary" />
            <span className="text-sm font-medium text-primary">Light Mode</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
