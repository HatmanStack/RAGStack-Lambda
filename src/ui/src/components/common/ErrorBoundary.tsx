import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { Alert, Button, SpaceBetween } from '@cloudscape-design/components';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return typeof this.props.fallback === 'function'
          ? this.props.fallback(this.handleReset)
          : this.props.fallback;
      }

      return (
        <Alert
          type="error"
          header="Something went wrong"
          action={
            <Button onClick={this.handleReset}>Try again</Button>
          }
        >
          <SpaceBetween size="xs">
            <span>An unexpected error occurred. You can try again or refresh the page.</span>
            {this.state.error && import.meta.env.DEV && (
              <code style={{ fontSize: '12px', opacity: 0.7 }}>
                {this.state.error.message}
              </code>
            )}
          </SpaceBetween>
        </Alert>
      );
    }

    return this.props.children;
  }
}
