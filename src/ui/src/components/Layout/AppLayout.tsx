import React, { useState } from 'react';
import {
  AppLayout as CloudscapeAppLayout,
  TopNavigation,
} from '@cloudscape-design/components';
import type { AppLayoutProps, TopNavigationProps } from '@cloudscape-design/components';
import { Navigation } from './Navigation';
import { useAuth } from '../Auth/AuthProvider';
import { useDemoMode } from '../../hooks/useDemoMode';

interface LayoutProps {
  children: React.ReactNode;
  contentType?: AppLayoutProps['contentType'];
}

export const AppLayout = ({ children, contentType = 'default' }: LayoutProps) => {
  const [navigationOpen, setNavigationOpen] = useState(true);
  const { user, logout } = useAuth();
  const { isEnabled: isDemoMode } = useDemoMode();

  // Build utilities - add demo badge as first utility when demo mode is enabled
  const utilities: TopNavigationProps.Utility[] = [];

  if (isDemoMode) {
    utilities.push({
      type: 'button',
      text: 'DEMO',
      disableUtilityCollapse: true,
      variant: 'primary-button',
    } as TopNavigationProps.Utility);
  }

  return (
    <>
      <TopNavigation
        identity={{
          href: '/',
          title: isDemoMode ? 'Document Pipeline (Demo)' : 'Document Pipeline'
        }}
        utilities={[
          ...utilities,
          {
            type: 'button',
            text: user?.username || 'User',
            iconName: 'user-profile',
            disableUtilityCollapse: true
          },
          {
            type: 'menu-dropdown',
            text: 'Settings',
            iconName: 'settings',
            items: [
              { id: 'profile', text: 'Profile' },
              { id: 'logout', text: 'Sign out' }
            ],
            onItemClick: ({ detail }) => {
              if (detail.id === 'logout') {
                logout();
              }
            }
          }
        ]}
      />

      <CloudscapeAppLayout
        navigation={<Navigation />}
        navigationOpen={navigationOpen}
        onNavigationChange={({ detail }) => setNavigationOpen(detail.open)}
        content={children}
        contentType={contentType}
        toolsHide
      />
    </>
  );
};
