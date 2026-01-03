/**
 * Zustand Store Exports
 *
 * Store usage pattern (from project-context.md):
 *
 * CORRECT - Selector pattern:
 * const currentMatter = useMatterStore((state) => state.currentMatter);
 * const setCurrentMatter = useMatterStore((state) => state.setCurrentMatter);
 *
 * WRONG - Full store subscription (causes unnecessary re-renders):
 * const { currentMatter, setCurrentMatter } = useMatterStore();
 */

// Stores will be added here as they are created
// Example: export { useMatterStore } from './matterStore';
// Example: export { useSessionStore } from './sessionStore';
// Example: export { useChatStore } from './chatStore';
