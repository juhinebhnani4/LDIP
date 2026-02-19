// PDF viewer components
// NOTE: PdfViewerPanel is NOT exported from this barrel to avoid pdfjs-dist
// being pulled into SSR bundles. Import it via next/dynamic with ssr: false:
//   const PdfViewerPanel = dynamic(() => import('./PdfViewerPanel').then(m => ({ default: m.PdfViewerPanel })), { ssr: false });
export { PdfErrorBoundary } from './PdfErrorBoundary';
export { PDFSplitView } from './PDFSplitView';
export { PDFSplitViewHeader } from './PDFSplitViewHeader';
export { PDFFullScreenModal } from './PDFFullScreenModal';
export { BboxOverlay } from './BboxOverlay';

// PDF Modal with pdf.js viewer (Story 2.3, BUG-LT3-G)
export { PdfViewerModal } from './PdfViewerModal';
