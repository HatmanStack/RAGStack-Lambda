import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ImageDetail } from './ImageDetail';

// Mock useImage hook
const mockGetImage = vi.fn();

vi.mock('../../hooks/useImage', () => ({
  useImage: () => ({
    getImage: mockGetImage
  })
}));

describe('ImageDetail', () => {
  const mockImage = {
    imageId: 'img-123',
    filename: 'test.png',
    caption: 'A test image caption',
    userCaption: 'User caption',
    aiCaption: 'AI caption',
    status: 'INDEXED',
    s3Uri: 's3://bucket/images/img-123/test.png',
    thumbnailUrl: 'https://example.com/thumb.png',
    contentType: 'image/png',
    fileSize: 1024000,
    createdAt: '2025-01-15T10:00:00Z'
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetImage.mockResolvedValue(mockImage);
  });

  it('renders nothing when not visible', () => {
    const { container } = render(
      <ImageDetail imageId="img-123" visible={false} onDismiss={vi.fn()} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('shows loading state while fetching', async () => {
    let resolvePromise: ((value: typeof mockImage) => void) | undefined;
    mockGetImage.mockReturnValue(new Promise(resolve => {
      resolvePromise = resolve;
    }));

    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    // Modal should be visible with loading state
    expect(screen.getByText('Image Details')).toBeInTheDocument();

    // Resolve the promise
    resolvePromise?.(mockImage);
  });

  it('displays image details when loaded', async () => {
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('test.png')).toBeInTheDocument();
    });

    expect(screen.getByText('A test image caption')).toBeInTheDocument();
    expect(screen.getByText('image/png')).toBeInTheDocument();
  });

  it('displays caption sections when available', async () => {
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('User Caption')).toBeInTheDocument();
    });

    expect(screen.getByText('AI Caption')).toBeInTheDocument();
    expect(screen.getByText('User caption')).toBeInTheDocument();
    expect(screen.getByText('AI caption')).toBeInTheDocument();
  });

  it('displays status indicator', async () => {
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Indexed')).toBeInTheDocument();
    });
  });

  it('displays error when fetch fails', async () => {
    mockGetImage.mockRejectedValue(new Error('Failed to load'));

    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Failed to load')).toBeInTheDocument();
    });
  });

  it('formats file size correctly', async () => {
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      // 1024000 bytes should be displayed as ~1000 KB or ~0.98 MB
      expect(screen.getByText(/KB|MB/i)).toBeInTheDocument();
    });
  });
});
