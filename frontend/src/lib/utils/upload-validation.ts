/**
 * Upload Validation Utility
 *
 * Validates files before upload with:
 * - File type validation (PDF, ZIP only)
 * - File size validation (500MB max)
 * - File count validation (100 files max per upload)
 */

import type {
  ValidationError,
  ValidationResult,
  ValidationWarning,
} from '@/types/document';

/** Maximum file size in bytes (500MB) */
export const MAX_FILE_SIZE = 500 * 1024 * 1024;

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

  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    return {
      file,
      code: 'FILE_TOO_LARGE',
      message: `File exceeds 500MB limit: ${file.name}`,
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
  for (const file of filesToValidate) {
    const error = validateSingleFile(file);
    if (error) {
      errors.push(error);
    }
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
