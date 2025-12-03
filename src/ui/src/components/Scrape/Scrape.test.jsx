/* global global */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock ResizeObserver (required by Cloudscape)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock the useScrape hook before importing Scrape component
vi.mock('../../hooks/useScrape', () => ({
  useScrape: () => ({
    loading: false,
    error: null,
    jobs: [],
    startScrape: vi.fn(),
    checkDuplicate: vi.fn().mockResolvedValue({ exists: false }),
    clearError: vi.fn()
  })
}));

// Import after mocking
import { Scrape } from './index';

describe('Scrape Component', () => {
  it('renders the scrape form header', { timeout: 10000 }, () => {
    render(
      <MemoryRouter>
        <Scrape />
      </MemoryRouter>
    );
    expect(screen.getByText('Scrape Website')).toBeInTheDocument();
  });
});
