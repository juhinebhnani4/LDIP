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

// Upload store for document upload management
export { useUploadStore } from './uploadStore';

// Future stores (to be added in later stories):
// export { useMatterStore } from './matterStore';
// export { useSessionStore } from './sessionStore';
// export { useChatStore } from './chatStore';
