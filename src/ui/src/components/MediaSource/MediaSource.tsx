import React, { useState } from 'react';
import { Box, Link, SpaceBetween, Badge } from '@cloudscape-design/components';
import { MediaPlayer } from '../MediaPlayer';
import './MediaSource.css';

export interface MediaSourceProps {
  source: {
    documentId: string;
    documentUrl?: string;
    isMedia?: boolean;
    mediaType?: 'video' | 'audio';
    contentType?: 'transcript' | 'visual';
    timestampStart?: number;
    timestampEnd?: number;
    timestampDisplay?: string;
    speaker?: string;
    snippet?: string;
    segmentIndex?: number;
  };
  onPlay?: () => void;
}

/**
 * MediaSource component for displaying media sources with expandable player.
 *
 * Shows timestamp badge that expands to inline video/audio player when clicked.
 * Displays speaker labels and snippet for transcript sources.
 */
export const MediaSource: React.FC<MediaSourceProps> = ({ source, onPlay }) => {
  const [showPlayer, setShowPlayer] = useState(false);

  const handleTimestampClick = () => {
    setShowPlayer(!showPlayer);
    if (!showPlayer && onPlay) {
      onPlay();
    }
  };

  const mediaIcon = source.mediaType === 'video' ? '🎬' : '🎵';
  const contentTypeLabel = source.contentType === 'transcript' ? 'Speech' : 'Visual';

  return (
    <Box className="media-source" padding={{ bottom: 's' }}>
      <SpaceBetween size="xs">
        {/* Header with media icon, timestamp, and badges */}
        <SpaceBetween direction="horizontal" size="xs">
          <Box fontSize="heading-s">{mediaIcon}</Box>

          {/* Clickable timestamp */}
          <Link onFollow={handleTimestampClick} fontSize="body-s">
            {source.timestampDisplay || 'Play'}
          </Link>

          {/* Content type badge */}
          <Badge color={source.contentType === 'transcript' ? 'blue' : 'green'}>
            {contentTypeLabel}
          </Badge>

          {/* Speaker label if available */}
          {source.speaker && (
            <Badge color="grey">
              {source.speaker.replace('_', ' ')}
            </Badge>
          )}
        </SpaceBetween>

        {/* Snippet preview */}
        {source.snippet && (
          <Box variant="small" color="text-body-secondary" className="media-source-snippet">
            "{source.snippet.length > 150 ? `${source.snippet.slice(0, 150)}...` : source.snippet}"
          </Box>
        )}

        {/* Expandable player */}
        {showPlayer && source.documentUrl && (
          <Box padding={{ top: 'xs' }}>
            <MediaPlayer
              src={source.documentUrl}
              mediaType={source.mediaType || 'video'}
              timestampStart={source.timestampStart}
              timestampEnd={source.timestampEnd}
              autoPlay
            />
          </Box>
        )}

        {/* No URL available */}
        {showPlayer && !source.documentUrl && (
          <Box variant="small" color="text-body-secondary">
            <em>Media playback not available</em>
          </Box>
        )}
      </SpaceBetween>
    </Box>
  );
};

export default MediaSource;
