import React, { useRef, useEffect, useState } from 'react';
import { Box, SpaceBetween, Alert } from '@cloudscape-design/components';
import './MediaPlayer.css';

export interface MediaPlayerProps {
  /** Presigned URL with optional #t= fragment */
  src: string;
  /** Media type - determines which element to render */
  mediaType: 'video' | 'audio';
  /** Start timestamp in seconds (for manual seeking if fragment not supported) */
  timestampStart?: number;
  /** End timestamp in seconds */
  timestampEnd?: number;
  /** Optional title for the media */
  title?: string;
  /** Auto-play when loaded */
  autoPlay?: boolean;
}

/**
 * MediaPlayer component for inline video/audio playback.
 *
 * Supports HTML5 media fragments (#t=start,end) for timestamp seeking.
 * Gracefully handles browser differences in fragment support.
 */
export const MediaPlayer: React.FC<MediaPlayerProps> = ({
  src,
  mediaType,
  timestampStart,
  timestampEnd,
  title,
  autoPlay = false,
}) => {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);

  // Manual seek to timestamp if fragment not supported by browser
  useEffect(() => {
    // Clear error state when source changes (e.g., refreshed presigned URL)
    setError(null);

    const media = mediaRef.current;
    if (!media) return;

    const handleLoadedMetadata = () => {
      // If browser didn't honor #t= fragment, manually seek
      if (timestampStart !== undefined && media.currentTime < timestampStart) {
        media.currentTime = timestampStart;
      }
    };

    const handleTimeUpdate = () => {
      setCurrentTime(media.currentTime);

      // Stop at end timestamp if specified
      if (timestampEnd !== undefined && media.currentTime >= timestampEnd) {
        media.pause();
      }
    };

    const handleError = () => {
      const mediaError = media.error;
      if (mediaError) {
        switch (mediaError.code) {
          case MediaError.MEDIA_ERR_ABORTED:
            setError('Playback was aborted');
            break;
          case MediaError.MEDIA_ERR_NETWORK:
            setError('Network error - URL may have expired');
            break;
          case MediaError.MEDIA_ERR_DECODE:
            setError('Media file is corrupted or format not supported');
            break;
          case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
            setError('Media format not supported by this browser');
            break;
          default:
            setError('An error occurred during playback');
        }
      }
    };

    media.addEventListener('loadedmetadata', handleLoadedMetadata);
    media.addEventListener('timeupdate', handleTimeUpdate);
    media.addEventListener('error', handleError);

    return () => {
      media.removeEventListener('loadedmetadata', handleLoadedMetadata);
      media.removeEventListener('timeupdate', handleTimeUpdate);
      media.removeEventListener('error', handleError);
    };
  }, [src, mediaType, timestampStart, timestampEnd]);

  // Format time for display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (error) {
    return (
      <Alert type="error" header="Playback Error">
        {error}
      </Alert>
    );
  }

  return (
    <Box className="media-player">
      <SpaceBetween size="xs">
        {title && (
          <Box variant="small" fontWeight="bold">
            {title}
          </Box>
        )}

        {mediaType === 'video' ? (
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={src}
            controls
            autoPlay={autoPlay}
            className="media-player-video"
            playsInline
          >
            Your browser does not support video playback.
          </video>
        ) : (
          <audio
            ref={mediaRef as React.RefObject<HTMLAudioElement>}
            src={src}
            controls
            autoPlay={autoPlay}
            className="media-player-audio"
          >
            Your browser does not support audio playback.
          </audio>
        )}

        {/* Timestamp range indicator */}
        {timestampStart !== undefined && timestampEnd !== undefined && (
          <Box variant="small" color="text-body-secondary" className="media-player-timestamp">
            Playing: {formatTime(timestampStart)} - {formatTime(timestampEnd)}
            {' | '}Current: {formatTime(currentTime)}
          </Box>
        )}
      </SpaceBetween>
    </Box>
  );
};

export default MediaPlayer;
