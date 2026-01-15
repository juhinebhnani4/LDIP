'use client';

import { useRef, useState } from 'react';
import { CheckCircle2, AlertCircle, Upload, Info, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { validateFiles } from '@/lib/utils/upload-validation';
import type { DetectedAct } from '@/types/upload';
import { cn } from '@/lib/utils';

/**
 * ActDiscoveryModal Component
 *
 * Stage 2.5 modal showing detected Acts from uploaded documents.
 * Displays found and missing Acts with options to upload missing ones.
 *
 * For MVP: Uses mock data until backend citation extraction is available.
 */

interface ActDiscoveryModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Detected Acts to display */
  detectedActs: DetectedAct[];
  /** Callback when user chooses to upload missing Acts */
  onUploadMissingActs: (files: File[]) => void;
  /** Callback when user wants to continue with upload */
  onContinue: () => void;
  /** Callback when user wants to skip */
  onSkip: () => void;
}

/** Act list item display */
function ActItem({ act }: { act: DetectedAct }) {
  const isFound = act.status === 'found';

  return (
    <li
      className={cn(
        'flex items-center justify-between py-2 px-3 rounded-md',
        isFound ? 'bg-green-50' : 'bg-muted/50'
      )}
    >
      <div className="flex items-center gap-2">
        {isFound ? (
          <CheckCircle2 className="size-4 text-green-600" />
        ) : (
          <span className="size-4 rounded-full border-2 border-muted-foreground/40" />
        )}
        <span className="text-sm font-medium">{act.actName}</span>
      </div>
      <span className="text-sm text-muted-foreground">
        {isFound ? (
          <>Found in: {act.sourceFile}</>
        ) : (
          <>Cited {act.citationCount} {act.citationCount === 1 ? 'time' : 'times'}</>
        )}
      </span>
    </li>
  );
}

export function ActDiscoveryModal({
  isOpen,
  onClose,
  detectedActs,
  onUploadMissingActs,
  onContinue,
  onSkip,
}: ActDiscoveryModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedActFiles, setUploadedActFiles] = useState<string[]>([]);

  const foundActs = detectedActs.filter((act) => act.status === 'found');
  const missingActs = detectedActs.filter((act) => act.status === 'missing');

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    const result = validateFiles(fileArray);

    // Filter out invalid files
    const validFiles = fileArray.filter(
      (file) => !result.errors.some((err) => err.file.name === file.name && err.file.size === file.size)
    );

    if (validFiles.length > 0) {
      onUploadMissingActs(validFiles);
      // Track uploaded file names for feedback
      setUploadedActFiles((prev) => [
        ...prev,
        ...validFiles.map((f) => f.name),
      ]);
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Don't render if no detected acts
  if (detectedActs.length === 0) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Act References Detected</DialogTitle>
          <DialogDescription>
            Your case files reference {detectedActs.length}{' '}
            {detectedActs.length === 1 ? 'Act' : 'Acts'}. We found {foundActs.length} in your files.
            For accurate citation verification, upload missing Acts.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Found Acts Section */}
          {foundActs.length > 0 && (
            <div>
              <h4 className="flex items-center gap-2 text-sm font-medium text-green-700 mb-2">
                <CheckCircle2 className="size-4" />
                Detected in Your Files ({foundActs.length})
              </h4>
              <ul className="space-y-1" role="list" aria-label="Found Acts">
                {foundActs.map((act) => (
                  <ActItem key={act.id} act={act} />
                ))}
              </ul>
            </div>
          )}

          {/* Missing Acts Section */}
          {missingActs.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="flex items-center gap-2 text-sm font-medium text-amber-700">
                  <AlertCircle className="size-4" />
                  Missing Acts ({missingActs.length})
                </h4>
                <Button variant="outline" size="sm" onClick={handleUploadClick}>
                  <Upload className="size-4 mr-2" />
                  Upload Missing Acts
                </Button>
              </div>
              <ul className="space-y-1" role="list" aria-label="Missing Acts">
                {missingActs.map((act) => (
                  <ActItem key={act.id} act={act} />
                ))}
              </ul>
            </div>
          )}

          {/* Uploaded Acts Feedback */}
          {uploadedActFiles.length > 0 && (
            <div className="flex items-start gap-2 p-3 rounded-md bg-green-50 border border-green-200 text-green-800">
              <CheckCircle2 className="size-4 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium">
                  {uploadedActFiles.length} Act {uploadedActFiles.length === 1 ? 'file' : 'files'} added
                </p>
                <ul className="mt-1 space-y-0.5">
                  {uploadedActFiles.map((name, i) => (
                    <li key={i} className="flex items-center gap-1 text-green-700">
                      <FileText className="size-3" />
                      <span className="truncate">{name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Info note */}
          <div className="flex items-start gap-2 p-3 rounded-md bg-blue-50 border border-blue-100 text-blue-800">
            <Info className="size-4 mt-0.5 flex-shrink-0" />
            <p className="text-sm">
              Citations to missing Acts will show as &quot;Unverified&quot;. You can upload Acts
              later from the Documents Tab.
            </p>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="ghost" onClick={onSkip}>
            Skip for Now
          </Button>
          <Button onClick={onContinue}>Continue with Upload</Button>
        </DialogFooter>

        {/* Hidden file input for uploading missing Acts */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,application/pdf"
          onChange={handleFileInputChange}
          className="hidden"
          aria-hidden="true"
        />
      </DialogContent>
    </Dialog>
  );
}
