import React, { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
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

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<FlashbarProps.MessageDefinition[]>([]);
  const counterRef = useRef(0);

  const removeItem = useCallback((id: string) => {
    setItems(prev => prev.filter(item => item.id !== id));
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
        item.action = (
          <span
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
            onClick={options.action.onClick}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') options.action!.onClick();
            }}
          >
            {options.action.text}
          </span>
        );
      }

      setItems(prev => [...prev, item]);

      // Auto-dismiss success and info after timeout
      if (type === 'success' || type === 'info') {
        setTimeout(() => removeItem(id), AUTO_DISMISS_MS);
      }
    },
    [removeItem],
  );

  const clearNotifications = useCallback(() => {
    setItems([]);
  }, []);

  return (
    <NotificationContext.Provider value={{ addNotification, clearNotifications }}>
      {items.length > 0 && <Flashbar items={items} />}
      {children}
    </NotificationContext.Provider>
  );
}
