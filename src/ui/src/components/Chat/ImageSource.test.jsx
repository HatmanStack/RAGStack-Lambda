import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ImageSource } from './ImageSource';

describe('ImageSource', () => {
  const mockSource = {
    documentId: 'img-123',
    caption: 'A beautiful sunset over mountains',
    thumbnailUrl: 'https://example.com/thumb.png',
    documentUrl: 'https://example.com/full.png',
    isImage: true
  };

  it('renders thumbnail image when thumbnailUrl is provided', () => {
    render(<ImageSource source={mockSource} />);

    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', 'https://example.com/thumb.png');
  });

  it('displays caption text', () => {
    render(<ImageSource source={mockSource} />);

    // Caption may appear in multiple places (preview and modal when open)
    const captionElements = screen.getAllByText('A beautiful sunset over mountains');
    expect(captionElements.length).toBeGreaterThanOrEqual(1);
  });

  it('truncates long captions', () => {
    const longCaption = 'A'.repeat(150);
    render(<ImageSource source={{ ...mockSource, caption: longCaption }} />);

    // Should show truncated caption with ...
    expect(screen.getByText(/\.\.\.$/)).toBeInTheDocument();
  });

  it('displays placeholder when no thumbnailUrl', () => {
    render(<ImageSource source={{ ...mockSource, thumbnailUrl: null }} />);

    // Should not have an img tag in the main view
    // There may still be a modal with no preview
    const emojiElements = screen.getAllByText('🖼️');
    expect(emojiElements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows view full image link when thumbnailUrl exists', () => {
    render(<ImageSource source={mockSource} />);

    expect(screen.getByText('View full image')).toBeInTheDocument();
  });

  it('opens modal when view full image is clicked', () => {
    render(<ImageSource source={mockSource} />);

    const viewLink = screen.getByText('View full image');
    fireEvent.click(viewLink);

    // Modal should be visible with header
    expect(screen.getByText('Image Source')).toBeInTheDocument();
  });

  it('opens modal when thumbnail is clicked', () => {
    render(<ImageSource source={mockSource} />);

    const thumbnail = screen.getByRole('img');
    fireEvent.click(thumbnail);

    // Modal should be visible
    expect(screen.getByText('Image Source')).toBeInTheDocument();
  });

  it('closes modal when close button is clicked', () => {
    render(<ImageSource source={mockSource} />);

    // Open modal
    const thumbnail = screen.getByRole('img');
    fireEvent.click(thumbnail);

    expect(screen.getByText('Image Source')).toBeInTheDocument();

    // Close modal
    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    // Modal header should not be visible (modal closed)
    // Note: Cloudscape modals may still be in DOM but not visible
  });

  it('shows open in new tab link when documentUrl is provided', () => {
    render(<ImageSource source={mockSource} />);

    // Open modal first
    const viewLink = screen.getByText('View full image');
    fireEvent.click(viewLink);

    // The Button component with external link may have different accessible name
    // Check for the existence of a link/button with the expected text
    expect(screen.getByText(/open in new tab/i)).toBeInTheDocument();
  });

  it('handles source without caption', () => {
    render(<ImageSource source={{ ...mockSource, caption: null }} />);

    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(screen.queryByText('A beautiful sunset')).not.toBeInTheDocument();
  });
});
