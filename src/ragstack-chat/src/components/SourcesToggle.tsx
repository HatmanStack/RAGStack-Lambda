/**
 * SourcesToggle Component
 *
 * Collapsible wrapper for sources display. Provides user control over
 * source visibility with smooth animations and state persistence.
 *
 * Features:
 * - Default collapsed state (cleaner UI)
 * - Expand/collapse on button click
 * - State persists in sessionStorage
 * - Keyboard accessible (Enter/Space)
 * - Screen reader compatible
 */

import React, { useState, useEffect } from 'react';
import { Source } from '../types';
import { SourcesDisplay } from './SourcesDisplay';
import styles from './SourcesToggle.module.css';

const STORAGE_KEY = 'amplify-chat-sources-expanded';

export interface SourcesToggleProps {
  /**
   * Array of sources to display
   */
  sources: Source[];

  /**
   * Default expanded state (optional, defaults to false)
   */
  defaultExpanded?: boolean;

  /**
   * Callback when toggle state changes (optional)
   */
  onToggle?: (expanded: boolean) => void;
}

/**
 * SourcesToggle Component
 *
 * Wraps SourcesDisplay with collapsible functionality
 */
const SourcesToggleComponent: React.FC<SourcesToggleProps> = ({
  sources,
  defaultExpanded = false,
  onToggle,
}) => {
  // Initialize state from sessionStorage or defaultExpanded
  const [expanded, setExpanded] = useState<boolean>(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored !== null) {
        return stored === 'true';
      }
    } catch (error) {
      // Handle environments without sessionStorage (SSR, private browsing)
    }
    return defaultExpanded;
  });

  // Don't render if no sources
  if (!sources || sources.length === 0) {
    return null;
  }

  // Handle toggle button click
  const handleToggle = () => {
    const newExpanded = !expanded;
    setExpanded(newExpanded);

    // Save to sessionStorage
    try {
      sessionStorage.setItem(STORAGE_KEY, String(newExpanded));
    } catch (error) {
      // Handle storage errors (quota exceeded, etc.)
    }

    // Call callback if provided
    if (onToggle) {
      onToggle(newExpanded);
    }

    // Log toggle event at debug level
  };

  return (
    <div className={styles.container}>
      {/* Toggle Button */}
      <button
        onClick={handleToggle}
        className={styles.toggleButton}
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Hide' : 'Show'} ${sources.length} source${sources.length === 1 ? '' : 's'}`}
        type="button"
      >
        <span className={styles.buttonIcon}>📄</span>
        <span className={styles.buttonText}>
          Sources ({sources.length})
        </span>
        <span className={styles.buttonToggleIcon}>
          {expanded ? '▼ Hide' : '▶ Show'}
        </span>
      </button>

      {/* Collapsible Sources Content */}
      {expanded && (
        <div className={styles.sourcesContent}>
          <SourcesDisplay sources={sources} />
        </div>
      )}
    </div>
  );
};

export const SourcesToggle = React.memo(SourcesToggleComponent);

export default SourcesToggle;
