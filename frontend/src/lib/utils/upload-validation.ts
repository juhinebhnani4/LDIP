/**
 * Upload Validation Utility
 *
 * Validates files before upload with:
 * - File type validation (PDF, ZIP only)
 * - File size validation (50MB hard limit for Supabase free tier)
 * - File size warnings (40MB+ triggers compression)
 * - File count validation (100 files max per upload)
 */

import type {
  ValidationError,
  ValidationResult,
  ValidationWarning,
} from '@/types/document';
import {
  COMPRESSION_THRESHOLD_BYTES,
  SUPABASE_FILE_LIMIT_BYTES,
} from '@/lib/utils/pdf-compression';

/**
 * Maximum file size in bytes (50MB) - Supabase free tier limit
 * Files larger than this cannot be uploaded even after compression attempts.
 */
export const MAX_FILE_SIZE = SUPABASE_FILE_LIMIT_BYTES;

/** Maximum file size in bytes for Act uploads (100MB) - Acts are typically smaller */
export const MAX_ACT_FILE_SIZE = 100 * 1024 * 1024;

/**
 * Size threshold for compression warning (40MB)
 * Files above this will attempt compression before upload.
 */
export const COMPRESSION_WARNING_THRESHOLD = COMPRESSION_THRESHOLD_BYTES;

/** Maximum files per upload batch */
export const MAX_FILES_PER_UPLOAD = 100;

/** Allowed MIME types */
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/zip',
  'application/x-zip-compressed',
  'application/x-zip',
] as const;

/** Allowed file extensions */
const ALLOWED_EXTENSIONS = ['.pdf', '.zip'] as const;

/**
 * Check if a file has a valid MIME type
 */
function isValidMimeType(file: File): boolean {
  return ALLOWED_MIME_TYPES.includes(
    file.type as (typeof ALLOWED_MIME_TYPES)[number]
  );
}

/**
 * Check if a file has a valid extension (fallback for empty MIME types)
 */
function hasValidExtension(file: File): boolean {
  const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
  return ALLOWED_EXTENSIONS.includes(
    extension as (typeof ALLOWED_EXTENSIONS)[number]
  );
}

/**
 * Check if a file type is valid (MIME type or extension)
 */
function isValidFileType(file: File): boolean {
  // Check MIME type first, fall back to extension for browsers that don't set MIME
  if (file.type && isValidMimeType(file)) {
    return true;
  }
  return hasValidExtension(file);
}

/**
 * Check if a file will need compression (over 40MB threshold)
 */
export function willNeedCompression(file: File): boolean {
  return file.size > COMPRESSION_WARNING_THRESHOLD;
}

/**
 * Validate a single file for type and size
 */
function validateSingleFile(file: File): ValidationError | null {
  // Check file type
  if (!isValidFileType(file)) {
    return {
      file,
      code: 'INVALID_TYPE',
      message: `Only PDF and ZIP files are supported`,
    };
  }

  // Check file size against Supabase limit (50MB)
  // Note: Files between 40-50MB will attempt compression during upload
  if (file.size > MAX_FILE_SIZE) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    return {
      file,
      code: 'FILE_TOO_LARGE',
      message: `File "${file.name}" is ${sizeMB}MB which exceeds the 50MB upload limit. Please split this document into smaller parts.`,
    };
  }

  // Check for empty files
  if (file.size === 0) {
    return {
      file,
      code: 'EMPTY_FILE',
      message: `File is empty: ${file.name}`,
    };
  }

  return null;
}

/**
 * Validate files for upload
 *
 * @param files - Files to validate
 * @returns Validation result with errors and warnings
 */
export function validateFiles(files: File[]): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationWarning[] = [];

  // Check file count limit
  if (files.length > MAX_FILES_PER_UPLOAD) {
    warnings.push({
      code: 'MAX_FILES_EXCEEDED',
      message: `Maximum 100 files per upload. First 100 accepted.`,
      acceptedCount: MAX_FILES_PER_UPLOAD,
      rejectedCount: files.length - MAX_FILES_PER_UPLOAD,
    });
  }

  // Only validate first MAX_FILES_PER_UPLOAD files
  const filesToValidate = files.slice(0, MAX_FILES_PER_UPLOAD);

  // Validate each file
  const filesNeedingCompression: string[] = [];
  for (const file of filesToValidate) {
    const error = validateSingleFile(file);
    if (error) {
      errors.push(error);
    } else if (willNeedCompression(file)) {
      // Track files that will need compression
      filesNeedingCompression.push(file.name);
    }
  }

  // Add warning about compression if any files need it
  if (filesNeedingCompression.length > 0) {
    warnings.push({
      code: 'COMPRESSION_REQUIRED',
      message:
        filesNeedingCompression.length === 1
          ? `"${filesNeedingCompression[0]}" is over 40MB and will be compressed before upload.`
          : `${filesNeedingCompression.length} files are over 40MB and will be compressed before upload.`,
      acceptedCount: filesNeedingCompression.length,
      rejectedCount: 0,
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Get valid files from a list (filters out invalid files)
 *
 * @param files - Files to filter
 * @returns Array of valid files (max 100)
 */
export function getValidFiles(files: File[]): File[] {
  const filesToCheck = files.slice(0, MAX_FILES_PER_UPLOAD);
  return filesToCheck.filter((file) => validateSingleFile(file) === null);
}

/**
 * Format file size for display
 *
 * @param bytes - File size in bytes
 * @returns Human-readable file size string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
