import React from 'react';
import { SideNavigation } from '@cloudscape-design/components';
import { useNavigate, useLocation } from 'react-router-dom';

export const Navigation = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    {
      type: 'link',
      text: 'Dashboard',
      href: '/'
    },
    {
      type: 'link',
      text: 'Upload',
      href: '/upload'
    },
    {
      type: 'link',
      text: 'Chat',
      href: '/chat'
    },
    {
      type: 'divider'
    },
    {
      type: 'link',
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
