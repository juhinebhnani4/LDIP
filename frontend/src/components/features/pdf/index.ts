/**
 * PDF Feature Components
 *
 * Story 3-4: Split-View Citation Highlighting
 * Story 11.5: PDF Viewer Split-View Mode
 * Story 11.6: PDF Viewer Full Modal Mode
 *
 * Components for PDF viewing with bounding box highlighting.
 */

export { PdfViewerPanel } from './PdfViewerPanel';
export type { PdfViewerPanelProps } from './PdfViewerPanel';

export { BboxOverlay } from './BboxOverlay';
export type { BboxOverlayProps } from './BboxOverlay';

export { PdfErrorBoundary } from './PdfErrorBoundary';

// Story 11.5: PDF Split View for source references
export { PDFSplitView } from './PDFSplitView';
export type { PDFSplitViewProps } from './PDFSplitView';

export { PDFSplitViewHeader } from './PDFSplitViewHeader';
export type { PDFSplitViewHeaderProps } from './PDFSplitViewHeader';

// Story 11.6: PDF Full Screen Modal
export { PDFFullScreenModal } from './PDFFullScreenModal';
