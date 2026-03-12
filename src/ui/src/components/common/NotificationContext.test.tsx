import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { NotificationProvider, useNotifications } from './NotificationContext';

// Test helper component that triggers notifications
function TestConsumer({ type = 'info' as const, message = 'Test notification' }) {
  const { addNotification, clearNotifications } = useNotifications();
  return (
    <div>
      <button onClick={() => addNotification(type, message)}>Add</button>
      <button onClick={() => clearNotifications()}>Clear</button>
    </div>
  );
}

describe('NotificationContext', () => {
  it('addNotification adds a flash item', () => {
    render(
      <NotificationProvider>
        <TestConsumer />
      </NotificationProvider>
    );

    fireEvent.click(screen.getByText('Add'));
    expect(screen.getByText('Test notification')).toBeTruthy();
  });

  it('dismiss removes the item', () => {
    const { container } = render(
      <NotificationProvider>
        <TestConsumer type="error" message="Dismissible error" />
      </NotificationProvider>
    );

    fireEvent.click(screen.getByText('Add'));
    expect(screen.getByText('Dismissible error')).toBeTruthy();

    // Cloudscape Flashbar dismiss button has class containing "dismiss-button"
    const dismissButton = container.querySelector('button[class*="dismiss-button"]');
    expect(dismissButton).not.toBeNull();
    fireEvent.click(dismissButton!);

    expect(screen.queryByText('Dismissible error')).toBeNull();
  });

  it('multiple notifications stack', () => {
    function MultiAdder() {
      const { addNotification } = useNotifications();
      return (
        <div>
          <button onClick={() => addNotification('info', 'First')}>Add First</button>
          <button onClick={() => addNotification('warning', 'Second')}>Add Second</button>
        </div>
      );
    }

    render(
      <NotificationProvider>
        <MultiAdder />
      </NotificationProvider>
    );

    fireEvent.click(screen.getByText('Add First'));
    fireEvent.click(screen.getByText('Add Second'));

    expect(screen.getByText('First')).toBeTruthy();
    expect(screen.getByText('Second')).toBeTruthy();
  });

  it('clearNotifications removes all', () => {
    render(
      <NotificationProvider>
        <TestConsumer message="Will be cleared" />
      </NotificationProvider>
    );

    fireEvent.click(screen.getByText('Add'));
    expect(screen.getByText('Will be cleared')).toBeTruthy();

    fireEvent.click(screen.getByText('Clear'));
    expect(screen.queryByText('Will be cleared')).toBeNull();
  });

  it('auto-dismisses success notifications', () => {
    vi.useFakeTimers();

    render(
      <NotificationProvider>
        <TestConsumer type="success" message="Auto dismiss me" />
      </NotificationProvider>
    );

    fireEvent.click(screen.getByText('Add'));
    expect(screen.getByText('Auto dismiss me')).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(screen.queryByText('Auto dismiss me')).toBeNull();

    vi.useRealTimers();
  });

  it('throws when useNotifications used outside provider', () => {
    // Suppress React error console noise
    vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestConsumer />);
    }).toThrow('useNotifications must be used within a NotificationProvider');
  });
});
