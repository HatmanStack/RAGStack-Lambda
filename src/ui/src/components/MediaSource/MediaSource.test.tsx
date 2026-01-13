import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MediaSource } from './MediaSource';

// Mock HTMLMediaElement methods
beforeEach(() => {
  window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  window.HTMLMediaElement.prototype.pause = vi.fn();
  window.HTMLMediaElement.prototype.load = vi.fn();
});

describe('MediaSource', () => {
  const defaultSource = {
    documentId: 'media123',
    documentUrl: 'https://example.com/video.mp4?sig=abc#t=60,90',
    isMedia: true,
    mediaType: 'video' as const,
    contentType: 'transcript' as const,
    timestampStart: 60,
    timestampEnd: 90,
    timestampDisplay: '1:00-1:30',
    speaker: 'speaker_0',
    snippet: 'This is a test snippet from the transcript.',
  };

  it('renders timestamp display', () => {
    render(<MediaSource source={defaultSource} />);
    expect(screen.getByText('1:00-1:30')).toBeInTheDocument();
  });

  it('shows video icon for video mediaType', () => {
    render(<MediaSource source={defaultSource} />);
    expect(screen.getByText('🎬')).toBeInTheDocument();
  });

  it('shows audio icon for audio mediaType', () => {
    render(<MediaSource source={{ ...defaultSource, mediaType: 'audio' }} />);
    expect(screen.getByText('🎵')).toBeInTheDocument();
  });

  it('shows content type badge', () => {
    render(<MediaSource source={defaultSource} />);
    expect(screen.getByText('Speech')).toBeInTheDocument();
  });

  it('shows Visual badge for visual content type', () => {
    render(<MediaSource source={{ ...defaultSource, contentType: 'visual' }} />);
    expect(screen.getByText('Visual')).toBeInTheDocument();
  });

  it('shows speaker label when provided', () => {
    render(<MediaSource source={defaultSource} />);
    expect(screen.getByText('speaker 0')).toBeInTheDocument();
  });

  it('shows snippet text', () => {
    render(<MediaSource source={defaultSource} />);
    expect(screen.getByText(/This is a test snippet/)).toBeInTheDocument();
  });

  it('truncates long snippets', () => {
    const longSnippet = 'A'.repeat(200);
    render(<MediaSource source={{ ...defaultSource, snippet: longSnippet }} />);
    expect(screen.getByText(/\.\.\."/)).toBeInTheDocument();
  });

  it('expands player on timestamp click', () => {
    render(<MediaSource source={defaultSource} />);

    // Player should not be visible initially
    expect(document.querySelector('video')).not.toBeInTheDocument();

    // Click timestamp
    fireEvent.click(screen.getByText('1:00-1:30'));

    // Player should now be visible
    expect(document.querySelector('video')).toBeInTheDocument();
  });

  it('collapses player on second click', () => {
    render(<MediaSource source={defaultSource} />);

    // Click to expand
    fireEvent.click(screen.getByText('1:00-1:30'));
    expect(document.querySelector('video')).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText('1:00-1:30'));
    expect(document.querySelector('video')).not.toBeInTheDocument();
  });

  it('calls onPlay callback when expanding', () => {
    const onPlay = vi.fn();
    render(<MediaSource source={defaultSource} onPlay={onPlay} />);

    fireEvent.click(screen.getByText('1:00-1:30'));
    expect(onPlay).toHaveBeenCalledTimes(1);
  });

  it('shows message when documentUrl not available', () => {
    render(<MediaSource source={{ ...defaultSource, documentUrl: undefined }} />);

    fireEvent.click(screen.getByText('1:00-1:30'));
    expect(screen.getByText('Media playback not available')).toBeInTheDocument();
  });
});
