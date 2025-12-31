/**
 * Shared TypeScript type definitions for RAGStack UI.
 * These types match the GraphQL schema and API responses.
 */

// Document types
export type DocumentStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'
  | 'DELETING';

export type DocumentType = 'document' | 'scrape' | 'image';

export interface Document {
  documentId: string;
  filename: string;
  status: DocumentStatus;
  totalPages?: number;
  isTextNative?: boolean;
  fileType?: string;
  createdAt?: string;
  updatedAt?: string;
  errorMessage?: string;
  inputS3Uri?: string;
  outputS3Uri?: string;
  metadata?: Record<string, unknown>;
  previewUrl?: string;
  type: DocumentType;
}

// Image types
export interface Image {
  imageId: string;
  filename: string;
  caption?: string;
  status: DocumentStatus;
  s3Uri?: string;
  thumbnailUrl?: string;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface TransformedImage extends Omit<Document, 'documentId'> {
  documentId: string; // imageId mapped to documentId
  caption?: string;
  thumbnailUrl?: string;
  s3Uri?: string;
  type: 'image';
}

// Scrape job types (matches GraphQL ScrapeStatus enum)
export type ScrapeStatus =
  | 'PENDING'
  | 'DISCOVERING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_ERRORS'
  | 'FAILED'
  | 'CANCELLED';

export interface ScrapeJob {
  jobId: string;
  baseUrl: string;
  title?: string;
  status: ScrapeStatus;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface TransformedScrapeJob extends Omit<Document, 'documentId'> {
  documentId: string; // jobId mapped to documentId
  processedCount?: number;
  failedCount?: number;
  baseUrl?: string;
  type: 'scrape';
}

// Chat types
export type MessageRole = 'user' | 'assistant';

export interface ChatSource {
  documentId?: string;
  title?: string;
  url?: string;
  excerpt?: string;
  pageNumber?: number;
  s3Uri?: string;
  downloadUrl?: string;
}

export interface ChatMessage {
  type: MessageRole;
  content: string;
  sources?: ChatSource[];
  timestamp: string;
}

export interface QueryResponse {
  answer: string;
  sources?: ChatSource[];
  sessionId?: string;
  error?: string;
}

// Search types
export interface SearchResult {
  content: string;
  source: string;
  score: number;
  documentId?: string;
  pageNumber?: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  error?: string;
}

// Upload types
export interface UploadState {
  file: File | null;
  progress: number;
  status: 'idle' | 'uploading' | 'processing' | 'complete' | 'error';
  error?: string;
}

export interface PresignedUrlResponse {
  uploadUrl: string;
  documentId: string;
  s3Uri: string;
}

// Configuration types
export interface AppConfiguration {
  chat_require_auth?: boolean;
  chat_primary_model?: string;
  chat_fallback_model?: string;
  chat_global_quota_daily?: number;
  chat_per_user_quota_daily?: number;
  chat_allow_document_access?: boolean;
}

// Auth types
export interface User {
  username: string;
  email?: string;
  groups?: string[];
  attributes?: Record<string, string>;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  loading: boolean;
}

// Hook return types
export interface UseDocumentsReturn {
  documents: (Document | TransformedImage | TransformedScrapeJob)[];
  loading: boolean;
  error: string | null;
  fetchDocuments: () => Promise<void>;
  refreshDocuments: () => void;
  fetchDocument: (documentId: string) => Promise<Document>;
  deleteDocuments: (documentIds: string[]) => Promise<DeleteResult>;
}

export interface DeleteResult {
  deletedCount: number;
  failedIds?: string[];
  errors?: string[];
}

export interface UseUploadReturn {
  uploadState: UploadState;
  uploadFile: (file: File) => Promise<void>;
  reset: () => void;
}

export interface UseSearchReturn {
  results: SearchResult[];
  loading: boolean;
  error: string | null;
  search: (query: string, maxResults?: number) => Promise<void>;
}

// Component prop types
export interface MessageBubbleProps {
  message: ChatMessage;
}

export interface SourceListProps {
  sources: ChatSource[];
}

export interface ImageSourceProps {
  source: ChatSource;
}

// GraphQL types (for API responses)
export interface GraphQLResponse<T> {
  data: T;
  errors?: GraphQLError[];
}

export interface GraphQLError {
  message: string;
  path?: string[];
  locations?: { line: number; column: number }[];
}

// Subscription update types
export interface DocumentUpdate {
  documentId: string;
  filename?: string;
  status?: DocumentStatus;
  totalPages?: number;
  errorMessage?: string;
  updatedAt?: string;
}

export interface ScrapeUpdate {
  jobId: string;
  baseUrl?: string;
  title?: string;
  status?: ScrapeStatus;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  updatedAt?: string;
}

export interface ImageUpdate {
  imageId: string;
  filename?: string;
  caption?: string;
  status?: DocumentStatus;
  s3Uri?: string;
  thumbnailUrl?: string;
  errorMessage?: string;
  updatedAt?: string;
}
