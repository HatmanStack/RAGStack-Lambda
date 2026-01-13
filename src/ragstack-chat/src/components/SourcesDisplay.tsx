/**
 * SourcesDisplay Component
 *
 * Renders a list of sources/citations from the knowledge base.
 * Displays document title, location, and snippet for each source.
 * Supports media sources with inline video/audio playback.
 *
 * This component is embeddable and works in any React application.
 */

import React, { useState, useRef, useEffect } from 'react';
import { SourcesDisplayProps, Source } from '../types';
import styles from '../styles/ChatWithSources.module.css';

/**
 * MediaSourceItem Component
 *
 * Displays a media source with expandable player.
 */
const MediaSourceItem: React.FC<{
  source: Source;
  index: number;
}> = ({ source, index }) => {
  const [showPlayer, setShowPlayer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);

  const mediaIcon = source.mediaType === 'video' ? '🎬' : '🎵';
  const contentTypeLabel = source.contentType === 'transcript' ? 'Speech' : 'Visual';

  // Handle media errors
  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;

    const handleError = () => {
      setError('Unable to play media. URL may have expired.');
    };

    const handleLoadedMetadata = () => {
      // Seek to timestamp if specified
      if (source.timestampStart !== undefined && media.currentTime < source.timestampStart) {
        media.currentTime = source.timestampStart;
      }
    };

    const handleTimeUpdate = () => {
      // Stop at end timestamp
      if (source.timestampEnd !== undefined && media.currentTime >= source.timestampEnd) {
        media.pause();
      }
    };

    media.addEventListener('error', handleError);
    media.addEventListener('loadedmetadata', handleLoadedMetadata);
    media.addEventListener('timeupdate', handleTimeUpdate);

    return () => {
      media.removeEventListener('error', handleError);
      media.removeEventListener('loadedmetadata', handleLoadedMetadata);
      media.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [source.timestampStart, source.timestampEnd]);

  return (
    <div key={`source-${index}`} className={styles.sourceItem}>
      {/* Media header with icon, timestamp, and badges */}
      <div className={styles.mediaHeader}>
        <span className={styles.mediaIcon}>{mediaIcon}</span>
        <button
          className={styles.timestampButton}
          onClick={() => setShowPlayer(!showPlayer)}
          aria-label={`Play from ${source.timestampDisplay || 'beginning'}`}
        >
          {source.timestampDisplay || 'Play'}
        </button>
        <span className={`${styles.badge} ${styles.badgeBlue}`}>
          {contentTypeLabel}
        </span>
        {source.speaker && (
          <span className={`${styles.badge} ${styles.badgeGray}`}>
            {source.speaker.replace('_', ' ')}
          </span>
        )}
      </div>

      {/* Snippet preview */}
      {source.snippet && (
        <div className={styles.sourceSnippet}>
          <span className={styles.quoteIcon}>❝</span>
          {source.snippet.length > 150 ? `${source.snippet.slice(0, 150)}...` : source.snippet}
          <span className={styles.quoteIcon}>❞</span>
        </div>
      )}

      {/* Expandable player */}
      {showPlayer && source.documentUrl && !error && (
        <div className={styles.mediaPlayerContainer}>
          {source.mediaType === 'video' ? (
            <video
              ref={mediaRef as React.RefObject<HTMLVideoElement>}
              src={source.documentUrl}
              controls
              autoPlay
              className={styles.mediaPlayer}
              playsInline
            >
              Your browser does not support video playback.
            </video>
          ) : (
            <audio
              ref={mediaRef as React.RefObject<HTMLAudioElement>}
              src={source.documentUrl}
              controls
              autoPlay
              className={styles.audioPlayer}
            >
              Your browser does not support audio playback.
            </audio>
          )}
        </div>
      )}

      {/* Error state */}
      {showPlayer && error && (
        <div className={styles.mediaError}>{error}</div>
      )}

      {/* No URL available */}
      {showPlayer && !source.documentUrl && !error && (
        <div className={styles.documentLinkDisabled}>
          Media playback not available
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
            source.isMedia ? (
              <MediaSourceItem key={`source-${index}`} source={source} index={index} />
            ) : (
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
                {source.documentUrl && !source.isMedia && (
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
            )
          ))}
        </div>
      )}
    </div>
  );
};

export const SourcesDisplay = React.memo(SourcesDisplayComponent);
