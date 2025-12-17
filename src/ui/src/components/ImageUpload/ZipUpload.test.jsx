import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ZipUpload } from './ZipUpload';

// Mock useImage hook
const mockUploadZip = vi.fn();
const mockClearError = vi.fn();

vi.mock('../../hooks/useImage', () => ({
  useImage: () => ({
    uploading: false,
    error: null,
    clearError: mockClearError,
    uploadZip: mockUploadZip
  })
}));

describe('ZipUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUploadZip.mockResolvedValue({ uploadId: 'test-upload-123' });
  });

  it('renders the upload zone', () => {
    render(<ZipUpload />);

    expect(screen.getByText('Upload Image Archive')).toBeInTheDocument();
    expect(screen.getByText(/Drag and drop a ZIP file here/i)).toBeInTheDocument();
    expect(screen.getByText(/or click to browse/i)).toBeInTheDocument();
  });

  it('displays info about captions.json', () => {
    render(<ZipUpload />);

    // Multiple mentions of captions.json - just verify at least one exists
    const matches = screen.getAllByText(/captions\.json/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('has file input with correct accept attribute', () => {
    render(<ZipUpload />);

    const input = document.querySelector('input[type="file"]');
    expect(input).toHaveAttribute('accept', '.zip');
  });

  it('shows generate captions checkbox when file is selected', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });
  });

  it('shows file info when file is selected', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'my-images.zip', { type: 'application/zip' });
    Object.defineProperty(mockFile, 'size', { value: 1024 * 500 }); // 500 KB

    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByText('my-images.zip')).toBeInTheDocument();
      expect(screen.getByText(/500.0 KB/i)).toBeInTheDocument();
    });
  });

  it('shows upload button when file is selected', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /upload archive/i })).toBeInTheDocument();
    });
  });

  it('rejects non-ZIP files', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'image.png', { type: 'image/png' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByText(/Only ZIP files are accepted/i)).toBeInTheDocument();
    });
  });

  it('shows remove button for selected file', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument();
    });
  });

  it('removes file when remove button is clicked', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByText('images.zip')).toBeInTheDocument();
    });

    const removeButton = screen.getByRole('button', { name: /remove/i });
    fireEvent.click(removeButton);

    await waitFor(() => {
      expect(screen.getByText(/Drag and drop a ZIP file here/i)).toBeInTheDocument();
    });
  });

  it('calls uploadZip when upload button is clicked', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /upload archive/i })).toBeInTheDocument();
    });

    const uploadButton = screen.getByRole('button', { name: /upload archive/i });
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(mockUploadZip).toHaveBeenCalledWith(
        mockFile,
        true, // generateCaptions default is true
        expect.any(Function)
      );
    });
  });

  it('passes generateCaptions=false when unchecked', { timeout: 10000 }, async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    // Uncheck the checkbox - Cloudscape uses detail.checked in onChange
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    // Wait for checkbox state to update, then click upload
    await waitFor(() => {
      const uploadButton = screen.getByRole('button', { name: /upload archive/i });
      fireEvent.click(uploadButton);
    });

    await waitFor(() => {
      expect(mockUploadZip).toHaveBeenCalledWith(
        mockFile,
        false,
        expect.any(Function)
      );
    });
  });

  it('shows success message after upload', async () => {
    render(<ZipUpload />);

    const mockFile = new File(['test content'], 'images.zip', { type: 'application/zip' });
    const input = document.querySelector('input[type="file"]');

    fireEvent.change(input, { target: { files: [mockFile] } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /upload archive/i })).toBeInTheDocument();
    });

    const uploadButton = screen.getByRole('button', { name: /upload archive/i });
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(screen.getByText(/uploaded successfully/i)).toBeInTheDocument();
    });
  });

  it('shows expandable help section', () => {
    render(<ZipUpload />);

    expect(screen.getByText(/How to use captions.json/i)).toBeInTheDocument();
  });

  it('shows example JSON in help section', async () => {
    render(<ZipUpload />);

    // Click to expand the help section
    const helpButton = screen.getByText(/How to use captions.json/i);
    fireEvent.click(helpButton);

    await waitFor(() => {
      expect(screen.getByText(/sunset.jpg/)).toBeInTheDocument();
    });
  });
});
