/**
 * SourcesDisplay Component
 *
 * Renders a list of sources/citations from the knowledge base.
 * Displays document title, location, and snippet for each source.
 *
 * This component is embeddable and works in any React application.
 */

import React, { useState } from 'react';
import { SourcesDisplayProps } from '../types';
import styles from '../styles/ChatWithSources.module.css';

/**
 * SourcesDisplay Component
 *
 * Memoized to prevent unnecessary re-renders when parent component updates
 * but sources array hasn't changed.
 *
 * @param sources - Array of sources to display
 * @param className - Optional custom CSS class
 * @returns React component rendering the sources
 */
const SourcesDisplayComponent: React.FC<SourcesDisplayProps> = ({
  sources,
  className,
}) => {
  // State to track whether sources are expanded or collapsed
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if no sources
  if (!sources || sources.length === 0) {
    return null;
  }

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={`${styles.sourcesContainer} ${className || ''}`}>
      {/* Header with collapsible toggle */}
      <div
        className={styles.sourcesHeader}
        onClick={toggleExpanded}
        role="button"
        aria-expanded={isExpanded}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleExpanded();
          }
        }}
        style={{ cursor: 'pointer' }}
      >
        <span className={styles.sourcesIcon}>
          {isExpanded ? '▼' : '▶'}
        </span>
        <span className={styles.sourcesIcon}>📄</span>
        <span className={styles.sourcesLabel}>Sources</span>
        <span className={styles.sourceCount}>({sources.length})</span>
      </div>

      {/* Collapsible List of sources */}
      {isExpanded && (
        <div className={styles.sourcesList}>
          {sources.map((source, index) => (
            <div key={`source-${index}`} className={styles.sourceItem}>
              {/* Document title */}
              <div className={styles.sourceTitle}>{source.title}</div>

              {/* Location (page number or character offset) */}
              {source.location && (
                <div className={styles.sourceLocation}>
                  📍 {source.location}
                </div>
              )}

              {/* Text snippet with quote styling */}
              {source.snippet && (
                <div className={styles.sourceSnippet}>
                  <span className={styles.quoteIcon}>❝</span>
                  {source.snippet}
                  <span className={styles.quoteIcon}>❞</span>
                </div>
              )}

              {/* Document download link (when available) */}
              {source.documentUrl && (
                <a
                  href={source.documentUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.documentLink}
                  aria-label={`View source document: ${source.title}`}
                >
                  View Document →
                </a>
              )}

              {/* Disabled state (when access explicitly disabled) */}
              {source.documentAccessAllowed === false && !source.documentUrl && (
                <span className={styles.documentLinkDisabled}>
                  Document access disabled
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const SourcesDisplay = React.memo(SourcesDisplayComponent);

export default SourcesDisplay;
