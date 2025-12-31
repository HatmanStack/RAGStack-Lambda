import React, { useState } from 'react';
import {
  AppLayout as CloudscapeAppLayout,
  TopNavigation
} from '@cloudscape-design/components';
import type { AppLayoutProps } from '@cloudscape-design/components';
import { Navigation } from './Navigation';
import { useAuth } from '../Auth/AuthProvider';

interface LayoutProps {
  children: React.ReactNode;
  contentType?: AppLayoutProps['contentType'];
}

export const AppLayout = ({ children, contentType = 'default' }: LayoutProps) => {
  const [navigationOpen, setNavigationOpen] = useState(true);
  const { user, logout } = useAuth();

  return (
    <>
      <TopNavigation
        identity={{
          href: '/',
          title: 'Document Pipeline'
        }}
        utilities={[
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
