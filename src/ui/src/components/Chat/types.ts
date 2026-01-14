export interface ChatSource {
  documentId?: string;
  title?: string;
  pageNumber?: number;
  location?: string;
  snippet?: string;
  sourceUrl?: string;
  documentUrl?: string;
  thumbnailUrl?: string;
  caption?: string;
  isImage?: boolean;
  isMedia?: boolean;
  isScraped?: boolean;
  documentAccessAllowed?: boolean;
  // Media-specific fields
  mediaType?: 'video' | 'audio';
  contentType?: 'transcript' | 'visual';
  timestampStart?: number;
  timestampEnd?: number;
  timestampDisplay?: string;
  speaker?: string;
  segmentIndex?: number;
}

export interface ChatMessage {
  type: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
}
