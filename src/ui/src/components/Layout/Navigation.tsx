import React from 'react';
import { SideNavigation } from '@cloudscape-design/components';
import { useNavigate, useLocation } from 'react-router-dom';

export const Navigation = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    {
      type: 'link' as const,
      text: 'Dashboard',
      href: '/'
    },
    {
      type: 'link' as const,
      text: 'Upload',
      href: '/upload'
    },
    {
      type: 'link' as const,
      text: 'Scrape',
      href: '/scrape'
    },
    {
      type: 'link' as const,
      text: 'Search',
      href: '/search'
    },
    {
      type: 'link' as const,
      text: 'Chat',
      href: '/chat'
    },
    {
      type: 'divider' as const
    },
    {
      type: 'link' as const,
      text: 'Settings',
      href: '/settings'
    }
  ];

  return (
    <SideNavigation
      activeHref={location.pathname}
      header={{ text: 'Document Pipeline', href: '/' }}
      items={navItems}
      onFollow={(event) => {
        if (!event.detail.external) {
          event.preventDefault();
          navigate(event.detail.href);
        }
      }}
    />
  );
};
