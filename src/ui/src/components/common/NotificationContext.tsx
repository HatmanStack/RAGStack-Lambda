import React, { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Flashbar, type FlashbarProps } from '@cloudscape-design/components';

type NotificationType = 'success' | 'error' | 'warning' | 'info';

interface NotificationOptions {
  dismissible?: boolean;
  action?: {
    text: string;
    onClick: () => void;
  };
}

interface NotificationContextValue {
  addNotification: (type: NotificationType, content: string, options?: NotificationOptions) => void;
  clearNotifications: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function useNotifications(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return ctx;
}

// Auto-dismiss delay for transient notifications (ms)
const AUTO_DISMISS_MS = 10_000;
// Maximum number of notifications displayed at once
const MAX_NOTIFICATIONS = 10;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<FlashbarProps.MessageDefinition[]>([]);
  const counterRef = useRef(0);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Clean up all timers on unmount
  useEffect(() => {
    return () => {
      timersRef.current.forEach(timer => clearTimeout(timer));
      timersRef.current.clear();
    };
  }, []);

  const removeItem = useCallback((id: string) => {
    setItems(prev => prev.filter(item => item.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const addNotification = useCallback(
    (type: NotificationType, content: string, options?: NotificationOptions) => {
      const id = String(++counterRef.current);

      const item: FlashbarProps.MessageDefinition = {
        id,
        type,
        content,
        dismissible: options?.dismissible ?? true,
        onDismiss: () => removeItem(id),
      };

      if (options?.action) {
        const handleClick = options.action.onClick;
        item.action = (
          <button
            type="button"
            style={{ cursor: 'pointer', textDecoration: 'underline', background: 'none', border: 'none', padding: 0, font: 'inherit', color: 'inherit' }}
            onClick={handleClick}
          >
            {options.action.text}
          </button>
        );
      }

      setItems(prev => {
        const next = [...prev, item];
        // Drop oldest notifications when exceeding max
        return next.length > MAX_NOTIFICATIONS ? next.slice(next.length - MAX_NOTIFICATIONS) : next;
      });

      // Auto-dismiss success and info after timeout
      if (type === 'success' || type === 'info') {
        const timer = setTimeout(() => removeItem(id), AUTO_DISMISS_MS);
        timersRef.current.set(id, timer);
      }
    },
    [removeItem],
  );

  const clearNotifications = useCallback(() => {
    setItems([]);
    timersRef.current.forEach(timer => clearTimeout(timer));
    timersRef.current.clear();
  }, []);

  return (
    <NotificationContext.Provider value={{ addNotification, clearNotifications }}>
      {items.length > 0 && <Flashbar items={items} />}
      {children}
    </NotificationContext.Provider>
  );
}
