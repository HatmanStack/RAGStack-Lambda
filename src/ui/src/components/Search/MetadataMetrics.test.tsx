import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetadataMetrics } from './MetadataMetrics';
import type { MetadataKeyStats } from '../../hooks/useMetadata';

const mockStats: MetadataKeyStats[] = [
  {
    keyName: 'topic',
    dataType: 'string',
    occurrenceCount: 150,
    sampleValues: ['genealogy', 'immigration', 'census'],
    lastAnalyzed: '2025-01-06T10:00:00Z',
    status: 'active',
  },
  {
    keyName: 'document_type',
    dataType: 'string',
    occurrenceCount: 120,
    sampleValues: ['pdf', 'docx'],
    lastAnalyzed: '2025-01-06T10:00:00Z',
    status: 'active',
  },
  {
    keyName: 'year',
    dataType: 'number',
    occurrenceCount: 80,
    sampleValues: ['1940', '1950', '1960'],
    lastAnalyzed: '2025-01-06T10:00:00Z',
    status: 'active',
  },
];

describe('MetadataMetrics', () => {
  it('renders with mock data', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Metadata Key Statistics')).toBeInTheDocument();
  });

  it('displays key names in table', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('topic')).toBeInTheDocument();
    expect(screen.getByText('document_type')).toBeInTheDocument();
    expect(screen.getByText('year')).toBeInTheDocument();
  });

  it('displays occurrence counts', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
  });

  it('displays data type badges', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    // Two string type badges and one number badge
    const stringBadges = screen.getAllByText('string');
    expect(stringBadges.length).toBe(2);
    expect(screen.getByText('number')).toBeInTheDocument();
  });

  it('displays sample values', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText(/genealogy, immigration, census/)).toBeInTheDocument();
    expect(screen.getByText(/pdf, docx/)).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(
      <MetadataMetrics
        stats={[]}
        totalKeys={0}
        lastAnalyzed={null}
        loading={true}
        error={null}
      />
    );

    expect(screen.getByText('Loading metadata keys...')).toBeInTheDocument();
  });

  it('shows error state', () => {
    render(
      <MetadataMetrics
        stats={[]}
        totalKeys={0}
        lastAnalyzed={null}
        loading={false}
        error="Failed to load metadata stats"
      />
    );

    expect(screen.getByText('Failed to load metadata stats')).toBeInTheDocument();
  });

  it('shows empty state when no keys', () => {
    render(
      <MetadataMetrics
        stats={[]}
        totalKeys={0}
        lastAnalyzed={null}
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('No metadata keys')).toBeInTheDocument();
    expect(
      screen.getByText('Run the analyzer to discover metadata keys from your documents.')
    ).toBeInTheDocument();
  });

  it('displays total keys count', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Total Keys')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays last analyzed timestamp', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Last Analyzed')).toBeInTheDocument();
    // The formatted date depends on locale, just check it's not "Never"
    expect(screen.queryByText('Never')).not.toBeInTheDocument();
  });

  it('shows "Never" when lastAnalyzed is null', () => {
    render(
      <MetadataMetrics
        stats={[]}
        totalKeys={0}
        lastAnalyzed={null}
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Never')).toBeInTheDocument();
  });

  it('displays status indicators for keys', () => {
    render(
      <MetadataMetrics
        stats={mockStats}
        totalKeys={3}
        lastAnalyzed="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    // All keys have 'active' status
    const activeIndicators = screen.getAllByText('active');
    expect(activeIndicators.length).toBe(3);
  });
});
