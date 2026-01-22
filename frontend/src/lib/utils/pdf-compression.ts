/**
 * PDF Compression Utility
 *
 * Compresses PDF files that exceed the upload size limit (50MB for Supabase Free tier).
 * Uses pdf-lib to optimize PDFs by removing unnecessary metadata and compressing streams.
 */

import { PDFDocument } from 'pdf-lib';

/** Size threshold for compression (50MB) */
export const COMPRESSION_THRESHOLD_BYTES = 50 * 1024 * 1024;

/** Target size after compression (45MB to have some buffer) */
const TARGET_SIZE_BYTES = 45 * 1024 * 1024;

/** Maximum compression attempts */
const MAX_COMPRESSION_ATTEMPTS = 3;

export interface CompressionResult {
  /** The compressed file (or original if no compression needed) */
  file: File;
  /** Whether compression was performed */
  wasCompressed: boolean;
  /** Original file size in bytes */
  originalSize: number;
  /** Final file size in bytes */
  finalSize: number;
  /** Compression ratio (e.g., 0.7 means 70% of original size) */
  compressionRatio: number;
  /** Warning message if compression couldn't reach target */
  warning?: string;
}

export interface CompressionProgress {
  stage: 'reading' | 'processing' | 'saving' | 'complete';
  message: string;
}

/**
 * Compress a PDF file if it exceeds the size threshold.
 *
 * Uses pdf-lib to:
 * 1. Remove unnecessary metadata
 * 2. Remove unused objects
 * 3. Optimize object streams
 *
 * Note: This performs lossless compression. For lossy compression
 * (reducing image quality), a server-side solution would be needed.
 *
 * @param file - The PDF file to potentially compress
 * @param onProgress - Optional callback for progress updates
 * @returns Compression result with the file and metadata
 */
export async function compressPdfIfNeeded(
  file: File,
  onProgress?: (progress: CompressionProgress) => void
): Promise<CompressionResult> {
  const originalSize = file.size;

  // Skip if file is under threshold
  if (originalSize <= COMPRESSION_THRESHOLD_BYTES) {
    return {
      file,
      wasCompressed: false,
      originalSize,
      finalSize: originalSize,
      compressionRatio: 1,
    };
  }

  // Only process PDFs
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return {
      file,
      wasCompressed: false,
      originalSize,
      finalSize: originalSize,
      compressionRatio: 1,
      warning: 'File is not a PDF, cannot compress',
    };
  }

  onProgress?.({ stage: 'reading', message: 'Reading PDF file...' });

  try {
    // Read the file as ArrayBuffer
    const arrayBuffer = await file.arrayBuffer();

    onProgress?.({ stage: 'processing', message: 'Optimizing PDF structure...' });

    // Load the PDF document
    const pdfDoc = await PDFDocument.load(arrayBuffer, {
      // Ignore encryption for read-only operations
      ignoreEncryption: true,
    });

    // Remove metadata to reduce size
    pdfDoc.setTitle('');
    pdfDoc.setAuthor('');
    pdfDoc.setSubject('');
    pdfDoc.setKeywords([]);
    pdfDoc.setProducer('');
    pdfDoc.setCreator('');

    onProgress?.({ stage: 'saving', message: 'Saving optimized PDF...' });

    // Save with optimization options
    const compressedBytes = await pdfDoc.save({
      // Use object streams for better compression
      useObjectStreams: true,
      // Add default metadata
      addDefaultPage: false,
      // Preserve form field values
      updateFieldAppearances: false,
    });

    const compressedSize = compressedBytes.length;
    const compressionRatio = compressedSize / originalSize;

    onProgress?.({ stage: 'complete', message: 'Compression complete' });

    // Create a new File object with the compressed data
    // Create a standard ArrayBuffer to ensure compatibility
    const buffer = new ArrayBuffer(compressedBytes.length);
    new Uint8Array(buffer).set(compressedBytes);
    const compressedFile = new File(
      [buffer],
      file.name,
      { type: 'application/pdf', lastModified: Date.now() }
    );

    // Check if we achieved meaningful compression
    if (compressedSize >= originalSize) {
      return {
        file,
        wasCompressed: false,
        originalSize,
        finalSize: originalSize,
        compressionRatio: 1,
        warning: 'PDF could not be compressed further (already optimized)',
      };
    }

    // Warn if still over threshold
    const warning = compressedSize > COMPRESSION_THRESHOLD_BYTES
      ? `File is still ${formatBytes(compressedSize)} after compression (limit: ${formatBytes(COMPRESSION_THRESHOLD_BYTES)}). Consider splitting the document.`
      : undefined;

    return {
      file: compressedFile,
      wasCompressed: true,
      originalSize,
      finalSize: compressedSize,
      compressionRatio,
      warning,
    };
  } catch (error) {
    console.error('PDF compression failed:', error);

    // Return original file if compression fails
    return {
      file,
      wasCompressed: false,
      originalSize,
      finalSize: originalSize,
      compressionRatio: 1,
      warning: `Compression failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
    };
  }
}

/**
 * Compress multiple PDF files, processing large files first.
 *
 * @param files - Array of files to potentially compress
 * @param onFileProgress - Callback for per-file progress
 * @returns Array of compression results
 */
export async function compressFilesIfNeeded(
  files: File[],
  onFileProgress?: (filename: string, progress: CompressionProgress) => void
): Promise<CompressionResult[]> {
  // Sort by size (largest first) to show progress for big files first
  const sortedFiles = [...files].sort((a, b) => b.size - a.size);

  const results: CompressionResult[] = [];

  for (const file of sortedFiles) {
    const result = await compressPdfIfNeeded(file, (progress) => {
      onFileProgress?.(file.name, progress);
    });
    results.push(result);
  }

  // Return in original order
  return files.map((file) =>
    results.find((r) => r.file.name === file.name || r.originalSize === file.size) ?? {
      file,
      wasCompressed: false,
      originalSize: file.size,
      finalSize: file.size,
      compressionRatio: 1,
    }
  );
}

/**
 * Check if a file needs compression based on size.
 */
export function needsCompression(file: File): boolean {
  return file.size > COMPRESSION_THRESHOLD_BYTES;
}

/**
 * Format bytes to human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Get compression statistics for display.
 */
export function getCompressionStats(result: CompressionResult): string {
  if (!result.wasCompressed) {
    return result.warning ?? 'No compression needed';
  }

  const savedBytes = result.originalSize - result.finalSize;
  const savedPercent = ((1 - result.compressionRatio) * 100).toFixed(1);

  return `Reduced from ${formatBytes(result.originalSize)} to ${formatBytes(result.finalSize)} (${savedPercent}% smaller, saved ${formatBytes(savedBytes)})`;
}
