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
  timestampStart?: number;
}

export interface ChatMessage {
  type: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
}
