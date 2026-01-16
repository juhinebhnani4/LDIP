import { UploadWizard } from '@/components/features/upload';

/**
 * Upload Page
 *
 * Entry point for the multi-stage upload wizard flow.
 * Allows users to create a new matter by uploading case files.
 */

export const metadata = {
  title: 'Create New Matter - jaanch.ai',
  description: 'Upload case files to create a new matter',
};

export default function UploadPage() {
  return <UploadWizard />;
}
