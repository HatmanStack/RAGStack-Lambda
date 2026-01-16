import type { DocumentItem } from '../../hooks/useDocuments';

// Document detail from API (extended version)
export interface DocumentDetailData {
  documentId: string;
  filename: string;
  inputS3Uri?: string;
  outputS3Uri?: string;
  status: string;
  fileType?: string;
  isTextNative?: boolean;
  totalPages?: number;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
  metadata?: string | Record<string, unknown>;
  previewUrl?: string;
}

// Image detail from API
export interface ImageDetailData {
  imageId: string;
  filename: string;
  status: string;
  caption?: string;
  userCaption?: string;
  aiCaption?: string;
  s3Uri?: string;
  thumbnailUrl?: string;
  contentType?: string;
  fileSize?: number;
  createdAt?: string;
  errorMessage?: string;
  // OCR extracted text
  extractedText?: string;
  // Extracted metadata from image analysis
  extractedMetadata?: string | Record<string, unknown>;
  // Presigned URL to caption.txt
  captionUrl?: string;
}

// Scrape job detail
export interface ScrapeJobDetailData {
  jobId: string;
  baseUrl?: string;
  title?: string;
  status: string;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  createdAt?: string;
  updatedAt?: string;
  urls?: ScrapeUrlItem[];
}

export interface ScrapeUrlItem {
  url: string;
  status: string;
  title?: string;
  contentLength?: number;
  error?: string;
}

// Status config for status indicators
export interface StatusConfig {
  type: string;
  label: string;
}

// Table preferences
export interface TablePreferences {
  pageSize: number;
  visibleContent: string[];
  dateRange: string;
}

// Component props
export interface DocumentDetailProps {
  documentId: string;
  visible: boolean;
  onDismiss: () => void;
}

export interface DocumentTableProps {
  documents: DocumentItem[];
  loading: boolean;
  onRefresh: () => void;
  onSelectDocument: (id: string, type: string) => void;
  onDelete?: (documentIds: string[]) => Promise<unknown>;
}

export interface ImageDetailProps {
  imageId: string;
  visible: boolean;
  onDismiss: () => void;
  onDelete?: (imageId: string) => Promise<void>;
}

export interface ScrapeJobDetailProps {
  job: ScrapeJobDetailData | Record<string, unknown> | null;
  visible: boolean;
  onDismiss: () => void;
  onCancel?: (jobId: string) => Promise<void>;
}
