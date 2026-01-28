import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FilterKeyInput } from './FilterKeyInput';

vi.mock('../../hooks/useKeyLibrary', () => ({
  useKeyLibrary: () => ({
    keys: [
      { keyName: 'location', dataType: 'string', occurrenceCount: 10, status: 'active' },
      { keyName: 'year', dataType: 'number', occurrenceCount: 5, status: 'active' },
      { keyName: 'old_key', dataType: 'string', occurrenceCount: 0, status: 'inactive' },
    ],
    loading: false,
  }),
}));

describe('FilterKeyInput', () => {
  it('renders placeholder when empty', () => {
    render(<FilterKeyInput value={[]} onChange={() => {}} />);
    // Cloudscape Multiselect renders placeholder as text inside a button
    expect(screen.getByText('Select keys to use for filter generation')).toBeInTheDocument();
  });

  it('renders with disabled state', () => {
    render(<FilterKeyInput value={[]} onChange={() => {}} disabled />);
    const trigger = screen.getByRole('button');
    expect(trigger).toBeDisabled();
  });

  it('displays selected keys as tokens', () => {
    render(<FilterKeyInput value={['location']} onChange={() => {}} />);
    expect(screen.getByText('location')).toBeInTheDocument();
  });

  it('displays multiple selected keys', () => {
    render(<FilterKeyInput value={['location', 'year']} onChange={() => {}} />);
    expect(screen.getByText('location')).toBeInTheDocument();
    expect(screen.getByText('year')).toBeInTheDocument();
  });
});
