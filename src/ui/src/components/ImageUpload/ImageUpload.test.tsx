import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ImageUpload } from './index';
import { ImagePreview } from './ImagePreview';
import { CaptionInput } from './CaptionInput';

// Mock useImage hook
vi.mock('../../hooks/useImage', () => ({
  useImage: () => ({
    uploading: false,
    error: null,
    clearError: vi.fn(),
    uploadImage: vi.fn().mockResolvedValue({ imageId: 'img-123', filename: 'test.png' }),
    submitImage: vi.fn().mockResolvedValue({ imageId: 'img-123' })
  })
}));

describe('ImageUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the upload zone', () => {
    render(<ImageUpload />);

    expect(screen.getByText('Upload Image')).toBeInTheDocument();
    expect(screen.getByText(/Drag and drop an image here/i)).toBeInTheDocument();
    expect(screen.getByText(/or click to browse/i)).toBeInTheDocument();
  });

  it('has info button for supported formats', () => {
    render(<ImageUpload />);

    // Info is now in a Popover triggered by info button
    expect(screen.getByRole('button', { name: /how it works/i })).toBeInTheDocument();
  });

  it('has file input with correct accept attribute', () => {
    render(<ImageUpload />);

    const input = document.querySelector('input[type="file"]');
    expect(input).toHaveAttribute('accept', 'image/png,image/jpeg,image/gif,image/webp');
  });
});

describe('ImagePreview', () => {
  const mockFile = new File(['test'], 'test.png', { type: 'image/png' });
  Object.defineProperty(mockFile, 'size', { value: 1024 * 500 }); // 500 KB

  it('displays image thumbnail when previewUrl is provided', () => {
    render(
      <ImagePreview
        file={mockFile}
        previewUrl="data:image/png;base64,test"
        onRemove={vi.fn()}
      />
    );

    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', 'data:image/png;base64,test');
    expect(img).toHaveAttribute('alt', 'test.png');
  });

  it('displays placeholder when no previewUrl', () => {
    render(
      <ImagePreview
        file={mockFile}
        previewUrl={null}
        onRemove={vi.fn()}
      />
    );

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('displays file name and metadata', () => {
    render(
      <ImagePreview
        file={mockFile}
        previewUrl="data:image/png;base64,test"
        onRemove={vi.fn()}
      />
    );

    expect(screen.getByText('test.png')).toBeInTheDocument();
    expect(screen.getByText(/500.0 KB/i)).toBeInTheDocument();
    expect(screen.getByText(/image\/png/i)).toBeInTheDocument();
  });

  it('shows remove button when onRemove is provided', () => {
    const onRemove = vi.fn();
    render(
      <ImagePreview
        file={mockFile}
        previewUrl="data:image/png;base64,test"
        onRemove={onRemove}
      />
    );

    const removeButton = screen.getByRole('button', { name: /remove image/i });
    expect(removeButton).toBeInTheDocument();

    fireEvent.click(removeButton);
    expect(onRemove).toHaveBeenCalled();
  });

  it('does not show remove button when onRemove is not provided', () => {
    render(
      <ImagePreview
        file={mockFile}
        previewUrl="data:image/png;base64,test"
        onRemove={undefined}
      />
    );

    expect(screen.queryByRole('button', { name: /remove image/i })).not.toBeInTheDocument();
  });
});

describe('CaptionInput', () => {
  it('renders user caption textarea', () => {
    render(
      <CaptionInput
        userCaption=""
        extractText={false}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={vi.fn()}
        error={null}
      />
    );

    expect(screen.getByLabelText(/caption/i)).toBeInTheDocument();
  });

  it('displays extract text checkbox', () => {
    render(
      <CaptionInput
        userCaption=""
        extractText={false}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={vi.fn()}
        error={null}
      />
    );

    expect(screen.getByText(/extract text from image/i)).toBeInTheDocument();
  });

  it('checkbox reflects extractText state', () => {
    render(
      <CaptionInput
        userCaption=""
        extractText={true}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={vi.fn()}
        error={null}
      />
    );

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeChecked();
  });

  it('calls onUserCaptionChange when typing', () => {
    const onUserCaptionChange = vi.fn();
    render(
      <CaptionInput
        userCaption=""
        extractText={false}
        onUserCaptionChange={onUserCaptionChange}
        onExtractTextChange={vi.fn()}
        error={null}
      />
    );

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'My caption' } });

    expect(onUserCaptionChange).toHaveBeenCalled();
  });

  it('calls onExtractTextChange when checkbox clicked', () => {
    const onExtractTextChange = vi.fn();
    render(
      <CaptionInput
        userCaption=""
        extractText={false}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={onExtractTextChange}
        error={null}
      />
    );

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    expect(onExtractTextChange).toHaveBeenCalledWith(true);
  });

  it('displays caption preview when caption provided', () => {
    render(
      <CaptionInput
        userCaption="User description"
        extractText={false}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={vi.fn()}
        error={null}
      />
    );

    expect(screen.getByText(/caption preview/i)).toBeInTheDocument();
    // Caption appears in both textarea and preview - check at least one exists
    expect(screen.getAllByText('User description').length).toBeGreaterThanOrEqual(1);
  });

  it('displays error when provided', () => {
    render(
      <CaptionInput
        userCaption=""
        extractText={false}
        onUserCaptionChange={vi.fn()}
        onExtractTextChange={vi.fn()}
        error="Something went wrong"
      />
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });
});
