import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Scrape } from './index';

// Mock the useScrape hook
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

describe('Scrape Component', () => {
  it('renders the scrape form header', () => {
    render(
      <MemoryRouter>
        <Scrape />
      </MemoryRouter>
    );
    expect(screen.getByText('Scrape Website')).toBeInTheDocument();
  });
});
