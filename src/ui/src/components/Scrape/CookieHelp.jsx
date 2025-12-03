import React from 'react';
import { ExpandableSection, Box } from '@cloudscape-design/components';

export const CookieHelp = () => {
  return (
    <ExpandableSection headerText="How to get cookies from your browser">
      <Box variant="p">
        To scrape sites that require login:
      </Box>
      <ol>
        <li>Log in to the website in your browser</li>
        <li>Open Developer Tools (F12 or right-click &rarr; Inspect)</li>
        <li>Go to the <strong>Application</strong> tab (Chrome) or <strong>Storage</strong> tab (Firefox)</li>
        <li>Click <strong>Cookies</strong> in the sidebar, then the site domain</li>
        <li>Copy the cookie values you need (usually <code>session</code> or <code>auth</code> cookies)</li>
        <li>
          Format as: <code>name1=value1; name2=value2</code>
        </li>
      </ol>
      <Box variant="p" color="text-status-warning">
        Note: Cookies expire. If scraping fails with auth errors, get fresh cookies.
      </Box>
    </ExpandableSection>
  );
};
