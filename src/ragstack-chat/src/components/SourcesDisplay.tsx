/**
 * SourcesDisplay Component
 *
 * Renders a collapsible list of sources/citations from the knowledge base.
 * The entire sources section is collapsible, and each source is individually expandable.
 * Matches the search UI pattern for consistency.
 *
 * This component is embeddable and works in any React application.
 */

import React, { useState } from 'react';
import { SourcesDisplayProps, Source } from '../types';
import styles from '../styles/ChatWithSources.module.css';

/**
 * Format timestamp in MM:SS format
 */
const formatTimestamp = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
};

/**
 * Format timestamp range (start-end) in MM:SS format
 */
const formatTimestampRange = (start: number, end?: number): string => {
  const startFmt = formatTimestamp(start);
  if (end !== undefined && end > start) {
    return `${startFmt}-${formatTimestamp(end)}`;
  }
  return startFmt;
};

/**
 * Get relevance color based on score
 */
const getRelevanceClass = (score: number): string => {
  if (score >= 0.8) return styles.badgeGreen;
  if (score >= 0.6) return styles.badgeBlue;
  return styles.badgeGray;
};

/**
 * Individual Source Item Component
 * Expandable with relevance score, content, and source links
 */
const SourceItem: React.FC<{
  source: Source;
  index: number;
  defaultExpanded: boolean;
}> = ({ source, index, defaultExpanded }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Determine source type label
  const getSourceLabel = (): string => {
    if (source.isSegment || source.isMedia) {
      return source.contentType === 'transcript' ? 'Video Transcript' : 'Video Visual Match';
    }
    if (source.isImage) return 'Image';
    if (source.isScraped) return 'Web Page';
    return source.filename || source.title || `Document ${index + 1}`;
  };

  // Check if we have a valid score to display (> 0 and not null/undefined)
  const hasValidScore = source.score !== undefined && source.score !== null && source.score > 0;

  // Check if we should show timestamp (media sources with timestamp data)
  const hasTimestamp = (source.isSegment || source.isMedia) && source.timestampStart !== undefined;

  return (
    <div className={styles.sourceItem}>
      {/* Expandable Header */}
      <div
        className={styles.sourceHeader}
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        aria-expanded={isExpanded}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
      >
        <span className={styles.expandIcon}>{isExpanded ? '▼' : '▶'}</span>
        <span className={styles.sourceLabel}>{getSourceLabel()}</span>
        {hasValidScore && (
          <span className={`${styles.badge} ${getRelevanceClass(source.score!)}`}>
            {Math.round(source.score! * 100)}% relevant
          </span>
        )}
        {hasTimestamp && (
          <span className={`${styles.badge} ${styles.badgeBlue}`}>
            {formatTimestampRange(source.timestampStart!, source.timestampEnd)}
          </span>
        )}
      </div>

      {/* Expandable Content */}
      {isExpanded && (
        <div className={styles.sourceContent}>
          {/* Text/Snippet Content */}
          {source.snippet && (
            <div className={styles.sourceSnippet}>
              <span className={styles.quoteIcon}>❝</span>
              {source.snippet}
              <span className={styles.quoteIcon}>❞</span>
            </div>
          )}

          {/* Source Info and Links */}
          <div className={styles.sourceInfo}>
            <span className={styles.sourceInfoLabel}>Source:</span>
            <span className={styles.sourceInfoText}>
              {source.filename || source.title || `Document ${source.documentId || index + 1}`}
            </span>
          </div>

          {/* Links Section */}
          <div className={styles.sourceLinks}>
            {/* Video segment links */}
            {(source.isSegment || source.isMedia) && (
              <>
                {source.segmentUrl && (
                  <a
                    href={source.segmentUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.sourceLink}
                  >
                    Jump to Clip →
                  </a>
                )}
                {source.documentUrl && (
                  <a
                    href={source.documentUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.sourceLink}
                  >
                    Full Video →
                  </a>
                )}
              </>
            )}

            {/* Image link */}
            {source.isImage && source.documentUrl && (
              <a
                href={source.documentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.sourceLink}
              >
                View Image →
              </a>
            )}

            {/* Scraped content link */}
            {source.isScraped && source.sourceUrl && (
              <a
                href={source.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.sourceLink}
              >
                View Original →
              </a>
            )}

            {/* Regular document link */}
            {!source.isSegment && !source.isMedia && !source.isImage && !source.isScraped && source.documentUrl && (
              <a
                href={source.documentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.sourceLink}
              >
                Download →
              </a>
            )}

            {/* No access message */}
            {!source.documentUrl && !source.segmentUrl && source.documentAccessAllowed === false && (
              <span className={styles.sourceLinkDisabled}>
                Document access disabled
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * SourcesDisplay Component
 *
 * Memoized to prevent unnecessary re-renders when parent component updates
 * but sources array hasn't changed.
 *
 * The entire sources section is collapsible (collapsed by default),
 * and each individual source is also expandable.
 *
 * @param sources - Array of sources to display
 * @param className - Optional custom CSS class
 * @returns React component rendering the sources
 */
const SourcesDisplayComponent: React.FC<SourcesDisplayProps> = ({
  sources,
  className,
}) => {
  // Sources section is collapsed by default
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if no sources
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className={`${styles.sourcesContainer} ${className || ''}`}>
      {/* Expandable Header for entire sources section */}
      <div
        className={styles.sourcesHeader}
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        aria-expanded={isExpanded}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
      >
        <span className={styles.expandIcon}>{isExpanded ? '▼' : '▶'}</span>
        <span className={styles.sourcesIcon}>📄</span>
        <span className={styles.sourcesLabel}>Sources</span>
        <span className={styles.sourceCount}>({sources.length})</span>
      </div>

      {/* List of individually expandable sources (only shown when section is expanded) */}
      {isExpanded && (
        <div className={styles.sourcesList}>
          {sources.map((source, index) => (
            <SourceItem
              key={`source-${index}`}
              source={source}
              index={index}
              defaultExpanded={index === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const SourcesDisplay = React.memo(SourcesDisplayComponent);
