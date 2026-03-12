import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

// Suppress React error boundary console.error noise in tests
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

// Component that throws on render
const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test render error');
  }
  return <div>Normal content</div>;
};

describe('ErrorBoundary', () => {
  it('renders children normally when no error', () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Child content')).toBeTruthy();
  });

  it('shows fallback UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeTruthy();
    expect(screen.getByText('Test render error')).toBeTruthy();
    expect(screen.getByText('Try again')).toBeTruthy();
  });

  it('resets to children on Try again click', () => {
    let shouldThrow = true;

    const ToggleComponent = () => {
      if (shouldThrow) {
        throw new Error('Temporary error');
      }
      return <div>Recovered content</div>;
    };

    render(
      <ErrorBoundary>
        <ToggleComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeTruthy();

    // Fix the error before clicking retry
    shouldThrow = false;
    fireEvent.click(screen.getByText('Try again'));

    expect(screen.getByText('Recovered content')).toBeTruthy();
  });

  it('uses custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom error view</div>}>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom error view')).toBeTruthy();
    expect(screen.queryByText('Something went wrong')).toBeNull();
  });

  it('calls onError callback with error info', () => {
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    expect(onError.mock.calls[0][0].message).toBe('Test render error');
  });
});
