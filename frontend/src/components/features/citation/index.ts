/**
 * Citation Feature Components
 *
 * Story 3-2: Act Discovery Report UI
 * Story 3-4: Split-View Citation Highlighting
 *
 * Components for displaying Act Discovery Report, managing
 * Act document uploads, and split-view citation verification.
 */

// Act Discovery (Story 3-2)
export { ActDiscoveryModal } from './ActDiscoveryModal';
export type { ActDiscoveryModalProps } from './ActDiscoveryModal';

export { ActDiscoveryItem } from './ActDiscoveryItem';
export type { ActDiscoveryItemProps } from './ActDiscoveryItem';

export { ActUploadDropzone } from './ActUploadDropzone';
export type { ActUploadDropzoneProps } from './ActUploadDropzone';

export { ActDiscoveryTrigger, useActDiscoveryControl } from './ActDiscoveryTrigger';
export type { ActDiscoveryTriggerProps } from './ActDiscoveryTrigger';

// Split View (Story 3-4)
export { SplitViewCitationPanel } from './SplitViewCitationPanel';
export type { SplitViewCitationPanelProps } from './SplitViewCitationPanel';

export { SplitViewHeader } from './SplitViewHeader';
export type { SplitViewHeaderProps } from './SplitViewHeader';

export { SplitViewModal } from './SplitViewModal';
export type { SplitViewModalProps } from './SplitViewModal';

export { MismatchExplanation } from './MismatchExplanation';
export type { MismatchExplanationProps } from './MismatchExplanation';

// Citations Tab Integration (Story 3-4)
export { CitationsList } from './CitationsList';
export type { CitationsListProps } from './CitationsList';

export { CitationsTab } from './CitationsTab';
export type { CitationsTabProps } from './CitationsTab';
