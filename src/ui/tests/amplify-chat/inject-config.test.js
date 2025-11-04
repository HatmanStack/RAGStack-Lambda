/**
 * Tests for config injection script.
 */
import { describe, it, beforeEach, afterEach, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('inject-amplify-config', () => {
  const testOutputsPath = path.join(__dirname, '../../../../../amplify_outputs.json');
  const generatedConfigPath = path.join(__dirname, '../../../amplify-chat/src/amplify-config.generated.ts');

  beforeEach(() => {
    // Clean up before each test
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  afterEach(() => {
    // Clean up after tests
    if (fs.existsSync(testOutputsPath)) {
      fs.unlinkSync(testOutputsPath);
    }
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  it('should generate config file when amplify_outputs.json exists', () => {
    // Create mock amplify_outputs.json
    const mockOutputs = {
      data: { url: 'https://test.appsync-api.us-east-1.amazonaws.com/graphql' },
      auth: { aws_region: 'us-east-1' }
    };
    fs.writeFileSync(testOutputsPath, JSON.stringify(mockOutputs, null, 2));

    // Run script
    execSync('node scripts/inject-amplify-config.js', {
      cwd: path.join(__dirname, '../../../amplify-chat'),
      stdio: 'inherit'
    });

    // Verify generated file
    expect(fs.existsSync(generatedConfigPath)).toBe(true);

    const content = fs.readFileSync(generatedConfigPath, 'utf-8');
    expect(content).toContain('AMPLIFY_OUTPUTS');
    expect(content).toContain('test.appsync-api');
  });

  it('should fail if amplify_outputs.json missing', () => {
    expect(() => {
      execSync('node scripts/inject-amplify-config.js', {
        cwd: path.join(__dirname, '../../../amplify-chat'),
        stdio: 'pipe'
      });
    }).toThrow();
  });

  it('should generate valid TypeScript with correct structure', () => {
    // Create mock amplify_outputs.json
    const mockOutputs = {
      data: { url: 'https://test.appsync-api.us-east-1.amazonaws.com/graphql' },
      auth: {
        aws_region: 'us-east-1',
        user_pool_id: 'us-east-1_TEST',
        user_pool_client_id: 'test-client-id'
      }
    };
    fs.writeFileSync(testOutputsPath, JSON.stringify(mockOutputs, null, 2));

    // Run script
    execSync('node scripts/inject-amplify-config.js', {
      cwd: path.join(__dirname, '../../../amplify-chat'),
      stdio: 'inherit'
    });

    // Verify generated file structure
    const content = fs.readFileSync(generatedConfigPath, 'utf-8');
    expect(content).toContain('export const AMPLIFY_OUTPUTS');
    expect(content).toContain('as const');
    expect(content).toContain('Auto-generated');
    expect(content).toContain('DO NOT EDIT MANUALLY');
  });
});
