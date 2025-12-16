import React, { useState } from 'react';
import {
  Form,
  FormField,
  Input,
  Select,
  SpaceBetween,
  Button,
  ExpandableSection,
  Textarea,
  Alert
} from '@cloudscape-design/components';
import { CookieHelp } from './CookieHelp';

export const ScrapeForm = ({ onSubmit, onProceedAnyway, loading, duplicateWarning, onDismissWarning }) => {
  const [url, setUrl] = useState('');
  const [maxPages, setMaxPages] = useState('100');
  const [maxDepth, setMaxDepth] = useState('3');
  const [scope, setScope] = useState({ value: 'SUBPAGES', label: 'Subpages only' });
  const [includePatterns, setIncludePatterns] = useState('');
  const [excludePatterns, setExcludePatterns] = useState('');
  const [scrapeMode, setScrapeMode] = useState({ value: 'AUTO', label: 'Auto-detect' });
  const [cookies, setCookies] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // GraphQL enum values must be uppercase
  const scopeOptions = [
    { value: 'SUBPAGES', label: 'Subpages only', description: 'Only URLs under the starting path' },
    { value: 'HOSTNAME', label: 'Entire hostname', description: 'All pages on the same subdomain' },
    { value: 'DOMAIN', label: 'Entire domain', description: 'All subdomains of the domain' }
  ];

  const modeOptions = [
    { value: 'AUTO', label: 'Auto-detect', description: 'Try fast mode, fall back to full for SPAs' },
    { value: 'FAST', label: 'Fast (HTTP only)', description: 'Faster, but may miss JavaScript content' },
    { value: 'FULL', label: 'Full (with browser)', description: 'Slower, but handles all JavaScript' }
  ];

  const getFormData = () => ({
    url,
    maxPages: parseInt(maxPages, 10),
    maxDepth: parseInt(maxDepth, 10),
    scope: scope.value,
    includePatterns: includePatterns.split('\n').filter(Boolean),
    excludePatterns: excludePatterns.split('\n').filter(Boolean),
    scrapeMode: scrapeMode.value,
    cookies: cookies || null
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(getFormData());
  };

  const handleProceedAnyway = () => {
    onProceedAnyway?.();
  };

  return (
    <form onSubmit={handleSubmit}>
      <Form
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="primary" loading={loading}>
              Start Scrape
            </Button>
          </SpaceBetween>
        }
      >
        <SpaceBetween size="l">
          {duplicateWarning && (
            <Alert
              type="warning"
              dismissible
              onDismiss={onDismissWarning}
              header="This URL was scraped before"
            >
              Last scraped on {duplicateWarning.date}. Scraping again will check for
              content changes and only process updated pages.
              <Button variant="link" onClick={handleProceedAnyway}>
                Proceed anyway
              </Button>
            </Alert>
          )}

          <FormField label="Website URL" description="Starting URL to scrape">
            <Input
              value={url}
              onChange={({ detail }) => setUrl(detail.value)}
              placeholder="https://docs.example.com"
              type="url"
            />
          </FormField>

          <FormField label="Maximum pages" description="Limit total pages to scrape">
            <Input
              value={maxPages}
              onChange={({ detail }) => setMaxPages(detail.value)}
              type="number"
            />
          </FormField>

          <FormField label="Maximum depth" description="How deep to follow links (0 = starting page only)">
            <Input
              value={maxDepth}
              onChange={({ detail }) => setMaxDepth(detail.value)}
              type="number"
            />
          </FormField>

          <FormField label="Scope" description="Which URLs to include">
            <Select
              selectedOption={scope}
              onChange={({ detail }) => setScope(detail.selectedOption)}
              options={scopeOptions}
            />
          </FormField>

          <ExpandableSection
            headerText="Advanced options"
            expanded={showAdvanced}
            onChange={({ detail }) => setShowAdvanced(detail.expanded)}
          >
            <SpaceBetween size="l">
              <FormField
                label="Include patterns"
                description="Only scrape URLs matching these patterns (one per line, glob syntax)"
              >
                <Textarea
                  value={includePatterns}
                  onChange={({ detail }) => setIncludePatterns(detail.value)}
                  placeholder={"/docs/*\n/api/*"}
                  rows={3}
                />
              </FormField>

              <FormField
                label="Exclude patterns"
                description="Skip URLs matching these patterns (one per line, glob syntax)"
              >
                <Textarea
                  value={excludePatterns}
                  onChange={({ detail }) => setExcludePatterns(detail.value)}
                  placeholder={"/blog/*\n/changelog/*"}
                  rows={3}
                />
              </FormField>

              <FormField label="Scrape mode">
                <Select
                  selectedOption={scrapeMode}
                  onChange={({ detail }) => setScrapeMode(detail.selectedOption)}
                  options={modeOptions}
                />
              </FormField>

              <FormField
                label="Cookies"
                description="For authenticated sites. See guide below."
              >
                <Textarea
                  value={cookies}
                  onChange={({ detail }) => setCookies(detail.value)}
                  placeholder="session=abc123; auth_token=xyz789"
                  rows={2}
                />
              </FormField>

              <CookieHelp />
            </SpaceBetween>
          </ExpandableSection>
        </SpaceBetween>
      </Form>
    </form>
  );
};
