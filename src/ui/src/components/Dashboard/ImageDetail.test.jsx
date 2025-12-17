import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImageDetail } from './ImageDetail';

// Mock useImage hook
const mockGetImage = vi.fn();
const mockDeleteImage = vi.fn();

vi.mock('../../hooks/useImage', () => ({
  useImage: () => ({
    getImage: mockGetImage,
    deleteImage: mockDeleteImage
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
    mockDeleteImage.mockResolvedValue(true);
  });

  it('renders nothing when not visible', () => {
    const { container } = render(
      <ImageDetail imageId="img-123" visible={false} onDismiss={vi.fn()} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('shows loading state while fetching', async () => {
    let resolvePromise;
    mockGetImage.mockReturnValue(new Promise(resolve => {
      resolvePromise = resolve;
    }));

    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    // Modal should be visible with loading state
    expect(screen.getByText('Image Details')).toBeInTheDocument();

    // Resolve the promise
    resolvePromise(mockImage);
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

  it('calls onDismiss when close button clicked', async () => {
    const onDismiss = vi.fn();
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={onDismiss} />
    );

    await waitFor(() => {
      expect(screen.getByText('test.png')).toBeInTheDocument();
    });

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    expect(onDismiss).toHaveBeenCalled();
  });

  it('displays delete button', async () => {
    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete image/i })).toBeInTheDocument();
    });
  });

  it('handles delete with confirmation', { timeout: 10000 }, async () => {
    const onDismiss = vi.fn();
    const onDelete = vi.fn();

    // Mock window.confirm to return true
    const originalConfirm = window.confirm;
    window.confirm = vi.fn().mockReturnValue(true);

    render(
      <ImageDetail
        imageId="img-123"
        visible={true}
        onDismiss={onDismiss}
        onDelete={onDelete}
      />
    );

    // Wait for image to load and delete button to appear
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete image/i })).toBeInTheDocument();
    });

    // Click delete button
    const deleteButton = screen.getByRole('button', { name: /delete image/i });
    fireEvent.click(deleteButton);

    // Wait for delete to complete and callbacks to be called
    await waitFor(() => {
      expect(mockDeleteImage).toHaveBeenCalledWith('img-123');
    });

    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledWith('img-123');
      expect(onDismiss).toHaveBeenCalled();
    });

    window.confirm = originalConfirm;
  });

  it('does not delete when confirmation is cancelled', { timeout: 10000 }, async () => {
    // Mock window.confirm to return false
    const originalConfirm = window.confirm;
    window.confirm = vi.fn().mockReturnValue(false);

    render(
      <ImageDetail imageId="img-123" visible={true} onDismiss={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete image/i })).toBeInTheDocument();
    });

    const deleteButton = screen.getByRole('button', { name: /delete image/i });
    fireEvent.click(deleteButton);

    expect(mockDeleteImage).not.toHaveBeenCalled();

    window.confirm = originalConfirm;
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
