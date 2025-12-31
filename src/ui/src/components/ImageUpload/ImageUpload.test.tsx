import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ImageUpload } from './index';
import { ImagePreview } from './ImagePreview';
import { CaptionInput } from './CaptionInput';

// Mock useImage hook
vi.mock('../../hooks/useImage', () => ({
  useImage: () => ({
    uploading: false,
    generating: false,
    error: null,
    clearError: vi.fn(),
    uploadImage: vi.fn().mockResolvedValue({ imageId: 'img-123', filename: 'test.png' }),
    generateCaption: vi.fn().mockResolvedValue('AI generated caption'),
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

  it('displays supported formats info', () => {
    render(<ImageUpload />);

    expect(screen.getByText(/Supported formats: PNG, JPG, GIF, WebP/i)).toBeInTheDocument();
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
        aiCaption=""
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={false}
        error={null}
      />
    );

    expect(screen.getByLabelText(/your caption/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter a description/i)).toBeInTheDocument();
  });

  it('displays generate caption button', () => {
    render(
      <CaptionInput
        userCaption=""
        aiCaption=""
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={false}
        error={null}
      />
    );

    expect(screen.getByRole('button', { name: /generate ai caption/i })).toBeInTheDocument();
  });

  it('shows loading state when generating', () => {
    render(
      <CaptionInput
        userCaption=""
        aiCaption=""
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={true}
        error={null}
      />
    );

    expect(screen.getByRole('button', { name: /generating/i })).toBeInTheDocument();
  });

  it('calls onUserCaptionChange when typing', async () => {
    const onUserCaptionChange = vi.fn();
    render(
      <CaptionInput
        userCaption=""
        aiCaption=""
        onUserCaptionChange={onUserCaptionChange}
        onGenerateCaption={vi.fn()}
        generating={false}
        error={null}
      />
    );

    const textarea = screen.getByPlaceholderText(/enter a description/i);
    fireEvent.change(textarea, { target: { value: 'My caption' } });

    expect(onUserCaptionChange).toHaveBeenCalled();
  });

  it('calls onGenerateCaption when button clicked', () => {
    const onGenerateCaption = vi.fn();
    render(
      <CaptionInput
        userCaption=""
        aiCaption=""
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={onGenerateCaption}
        generating={false}
        error={null}
      />
    );

    const button = screen.getByRole('button', { name: /generate ai caption/i });
    fireEvent.click(button);

    expect(onGenerateCaption).toHaveBeenCalled();
  });

  it('displays AI caption when provided', () => {
    render(
      <CaptionInput
        userCaption=""
        aiCaption="AI generated description"
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={false}
        error={null}
      />
    );

    // AI caption appears twice - once in AI section and once in final caption preview
    const aiCaptionTexts = screen.getAllByText('AI generated description');
    expect(aiCaptionTexts.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/ai-generated caption/i)).toBeInTheDocument();
  });

  it('displays combined caption preview', () => {
    render(
      <CaptionInput
        userCaption="User description"
        aiCaption="AI description"
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={false}
        error={null}
      />
    );

    expect(screen.getByText(/final caption/i)).toBeInTheDocument();
    expect(screen.getByText('User description. AI description')).toBeInTheDocument();
  });

  it('displays error when provided', () => {
    render(
      <CaptionInput
        userCaption=""
        aiCaption=""
        onUserCaptionChange={vi.fn()}
        onGenerateCaption={vi.fn()}
        generating={false}
        error="Failed to generate caption"
      />
    );

    expect(screen.getByText('Failed to generate caption')).toBeInTheDocument();
  });
});
