import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MediaPlayer } from './MediaPlayer';

// Mock HTMLMediaElement methods
beforeEach(() => {
  // Mock play/pause methods
  window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  window.HTMLMediaElement.prototype.pause = vi.fn();
  window.HTMLMediaElement.prototype.load = vi.fn();
});

describe('MediaPlayer', () => {
  const defaultProps = {
    src: 'https://example.com/video.mp4?sig=abc#t=60,90',
    mediaType: 'video' as const,
  };

  it('renders video element for video mediaType', () => {
    render(<MediaPlayer {...defaultProps} />);
    expect(document.querySelector('video')).toBeInTheDocument();
    expect(document.querySelector('audio')).not.toBeInTheDocument();
  });

  it('renders audio element for audio mediaType', () => {
    render(<MediaPlayer {...defaultProps} mediaType="audio" />);
    expect(document.querySelector('audio')).toBeInTheDocument();
  });

  it('displays title when provided', () => {
    render(<MediaPlayer {...defaultProps} title="Interview Recording" />);
    expect(screen.getByText('Interview Recording')).toBeInTheDocument();
  });

  it('shows timestamp range when both timestamps provided', () => {
    render(
      <MediaPlayer
        {...defaultProps}
        timestampStart={60}
        timestampEnd={90}
      />
    );
    expect(screen.getByText(/Playing: 1:00 - 1:30/)).toBeInTheDocument();
  });

  it('does not show timestamp range without timestamps', () => {
    render(<MediaPlayer {...defaultProps} />);
    expect(screen.queryByText(/Playing:/)).not.toBeInTheDocument();
  });

  it('sets correct src attribute', () => {
    render(<MediaPlayer {...defaultProps} />);
    const video = document.querySelector('video');
    expect(video?.src).toContain('video.mp4');
  });

  it('applies autoPlay attribute when specified', () => {
    render(<MediaPlayer {...defaultProps} autoPlay />);
    const video = document.querySelector('video');
    expect(video?.autoplay).toBe(true);
  });

  it('has controls enabled by default', () => {
    render(<MediaPlayer {...defaultProps} />);
    const video = document.querySelector('video');
    expect(video?.controls).toBe(true);
  });
});
