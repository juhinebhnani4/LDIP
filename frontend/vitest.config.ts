import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'vitest.setup.ts'],
    },
  },
  resolve: {
    alias: [
      // Mock Dialog component to avoid Radix presence infinite loop in jsdom
      // This must come BEFORE the @ alias to take precedence
      {
        find: '@/components/ui/dialog',
        replacement: path.resolve(__dirname, './src/__mocks__/components/ui/dialog.tsx'),
      },
      {
        find: '@/components/ui/alert-dialog',
        replacement: path.resolve(__dirname, './src/__mocks__/components/ui/alert-dialog.tsx'),
      },
      {
        find: '@/components/ui/tabs',
        replacement: path.resolve(__dirname, './src/__mocks__/components/ui/tabs.tsx'),
      },
      {
        find: '@/components/ui/resizable',
        replacement: path.resolve(__dirname, './src/__mocks__/components/ui/resizable.tsx'),
      },
      // Mock Radix UI packages that cause infinite loops in jsdom
      {
        find: '@radix-ui/react-presence',
        replacement: path.resolve(__dirname, './src/__mocks__/@radix-ui/react-presence.tsx'),
      },
      {
        find: '@radix-ui/react-compose-refs',
        replacement: path.resolve(__dirname, './src/__mocks__/@radix-ui/react-compose-refs.tsx'),
      },
      // General @ alias for src directory
      {
        find: '@',
        replacement: path.resolve(__dirname, './src'),
      },
    ],
  },
});
